import errno
import json
import logging
import os
import urllib

import gevent
from gevent.pool import Pool
from requests import ConnectionError, HTTPError

from lib.connector import AuditConnector
from lib.error import ConfigError

LOG = logging.getLogger("connectors/casper")  # pylint:disable=invalid-name


SyncTypes = {
    "computers": dict(
        all_ids_path="JSSResource/computers",
        group_ids_path="JSSResource/computergroups/name/{name}",
        array="computers",
        data="computer",
    ),
    "mobiledevices": dict(
        all_ids_path="JSSResource/mobiledevices",
        group_ids_path="JSSResource/mobiledevicegroups/name/{name}",
        array="mobile_devices",
        data="mobile_device",
    ),
}


class Connector(AuditConnector):
    MappingName = 'Casper'
    RetryCount = 10

    Settings = {
        'url':         {'order': 1, 'default': "https://jss.jamfcloud.com/example"},
        'username':    {'order': 2, 'example': "username@example.com"},
        'password':    {'order': 3, 'example': "change-me"},
        'sync_field':  {'order': 4, 'example': '24DCF85294E411E38A52066B556BA4EE'},
        'sync_type':   {'order': 5, 'default': "computers", 'choices': ("computers", "mobiledevices")},
        'update_only': {'order': 6, 'default': "False"},
        'group_name':  {'order': 7, 'default': ""},
    }
    DefaultConverters = {
        "general.report_date":         "date_format",
        "general.last_contact_time":   "date_format",
        "general.initial_entry_date":  "date_format",
        "purchasing.warranty_expires": "date_format",
        "purchasing.lease_expires":    "date_format",
        "purchasing.po_date":          "date_format",
    }

    def get_details_url(self, sync_type):
        # try to extract data subsets to make request more efficient and quick
        subsets = None
        try:
            subsets = set(map(str.capitalize, filter(bool, [str(_.get('source', '').split('.')[0]) for _ in self.field_mappings.values()])))
        except:
            pass

        if subsets:
            details_url = self.url_template.format(
                "JSSResource/%s/id/{}/subset/%s" % (sync_type, '&'.join(subsets))
            )
        else:
            details_url = self.url_template.format(
                "JSSResource/%s/id/{}" % sync_type
            )

        return details_url

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)

        # ensure URL does not end with a trailing '/'
        if self.settings['url'].endswith('/'):
            LOG.warning("Casper URL should not end with a '/'.")
            self.settings['url'] = self.settings['url'][:-1]

        self.url_template = "%s/{0}" % self.settings['url']
        sync_type = self.settings.get('sync_type', None)
        if sync_type is None:
            LOG.warning("No sync_type configured. Defaulting to 'computers'.")
            sync_type = "computers"
        elif not sync_type:
            LOG.warning("Empty sync_type configured. Defaulting to 'computers'.")
            sync_type = "computers"

        self.sync_type = SyncTypes.get(sync_type, None)
        if self.sync_type is None:
            raise ConfigError("Invalid sync_type: %r", self.sync_type)

        if sync_type == "computers":
            # print self.field_mappings.keys()
            if 'APPLICATIONS' not in self.field_mappings:
                self.field_mappings['APPLICATIONS'] = {"source": "software.applications"}
        else:
            self.MappingName = Connector.MappingName+".MDM"

        self.group_name = self.settings.get("group_name", "")
        if self.group_name:
            LOG.info("Loading assets from group: %r", self.group_name)
            self.ids_url = self.url_template.format(
                self.sync_type['group_ids_path'].format(
                    name=urllib.quote(self.group_name)
                )
            )
            self.ids_converter = lambda data: data['{}_group'.format(self.sync_type['data'])][self.sync_type['array']]
        else:
            self.ids_url = self.url_template.format(self.sync_type['all_ids_path'])
            self.ids_converter = lambda data: data[self.sync_type['array']]

        self.details_url = self.get_details_url(sync_type)

    def get_headers(self):
        return {
            'Accept': 'application/json'
        }

    def get_auth(self):
        return self.settings['username'], self.settings['password']

    def do_test_connection(self, options):
        try:
            response = self.get(self.ids_url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            LOG.exception("Error testing connection.")
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}
        except HTTPError as exp:
            LOG.exception("Error testing connection!")
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}

    def _load_records(self, options):

        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        for device_info in connection_pool.imap(self.fetch_asset_details, self.fetch_asset_ids(), maxsize=pool_size):
            if device_info:
                yield device_info
            else:
                raise StopIteration

    def fetch_asset_ids(self):
        """
        This method is used to retrieve the ids of assets in Casper
        """
        try:
            # print self.ids_url
            response = self.get(self.ids_url)
            data = self.ids_converter(response.json())
            return [c['id'] for c in data]
        except HTTPError:
            if self.group_name:
                LOG.error("Error loading assets for group: %r. Please verify the group name is correct.", self.group_name)
            else:
                LOG.exception("Error loading IDs from Casper.")
            return []

    def fetch_asset_details(self, device_id):
        """
        This method is used to retrieve the details of an asset by its Casper's ID
        """
        try:
            url = self.details_url.format(str(device_id))
            # print url
            details = self.get(url).json()[self.sync_type['data']]

            if self.settings.get("__save_data__", False):
                try:
                    os.makedirs("./saved_data")
                except OSError as exc:
                    if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                        pass
                    else:
                        raise
                with open("./saved_data/{}.json".format(str(device_id)), "w") as save_file:
                    save_file.write(json.dumps(details))

            return details
        except:
            LOG.exception("fetch_asset_details( %s ) failed." % device_id)
            return None

    def server_handler(self, body, wsgi_env, options):
        """
        Webhook handler (https://github.com/brysontyrrell/Example-JSS-Webhooks)
        It will consume incoming POST request and perform a sync for a certain record
        """
        try:
            payload = json.loads(body)

            event_type = payload['webhook']['webhookEvent']
            object_id = payload['event'].get('jssID')

            if object_id:
                LOG.info('Casper webhook event %s triggered for device #%s' % (event_type, object_id))

                if self.is_authorized():

                    if event_type.startswith('Computer'):
                        device = self.get(self.get_details_url("computers").format(object_id)).json()['computer']
                    elif event_type.startswith('MobileDevice'):
                        device = self.get(self.get_details_url("mobiledevices").format(object_id)).json()['mobile_device']
                    else:
                        LOG.warning('Casper unknown event %s caught. Cannot handle' % event_type)
                        return

                    # sync retrieved device with Oomnitza
                    gevent.spawn(self.sender, *(self.OomnitzaConnector, options, device)).start()
        except:
            LOG.exception('Casper server handler failed')
