import json
import logging
import urllib.error
import urllib.parse
import urllib.request

import gevent
from gevent.pool import Pool
from requests import ConnectionError, HTTPError

from lib.connector import AssetsConnector
from lib.error import ConfigError

LOG = logging.getLogger("connectors/casper")  # pylint:disable=invalid-name


COMPUTERS = 'computers'
MOBILE_DEVICES = 'mobiledevices'


SyncTypes = {
    COMPUTERS: dict(
        all_ids_path="JSSResource/computers",
        group_ids_path="JSSResource/computergroups/name/{name}",
        array="computers",
        data="computer",
    ),
    MOBILE_DEVICES: dict(
        all_ids_path="JSSResource/mobiledevices",
        group_ids_path="JSSResource/mobiledevicegroups/name/{name}",
        array="mobile_devices",
        data="mobile_device",
    ),
}


class Connector(AssetsConnector):
    MappingName = 'Casper'
    RetryCount = 10

    sync_config = None

    Settings = {
        'url':         {'order': 1, 'default': "https://jss.jamfcloud.com/example"},
        'username':    {'order': 2, 'example': "username@example.com"},
        'password':    {'order': 3, 'example': "change-me"},
        'sync_type':   {'order': 5, 'default': COMPUTERS, 'choices': (COMPUTERS, MOBILE_DEVICES)},
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
            subsets = set(map(str.capitalize, list(filter(bool, [str(_.get('source', '').split('.')[0]) for _ in self.field_mappings.values()]))))
        except:
            pass

        # Add `ExtensionAttributes` subset to the set of subsets if special converter is used
        if subsets:
            for _ in self.field_mappings.values():
                if 'casper_extension_attribute' in _.get('converter', ''):
                    subsets |= {'ExtensionAttributes'}

        if subsets:
            details_url = self.url_template.format(
                "JSSResource/%s/id/{}/subset/%s" % (sync_type, '&'.join(subsets))
            )
        else:
            details_url = self.url_template.format(
                "JSSResource/%s/id/{}" % sync_type
            )

        return details_url

    def get_mapping_from_oomnitza(self):
        name = self.get_name_for_mapping_and_connection()
        return self.settings['__oomnitza_connector__'].get_mappings(name)

    def get_sync_type_from_settings(self):
        sync_type = self.settings.get('sync_type', None)
        if not sync_type:
            LOG.warning("No sync_type configured or set as empty. Defaulting to '%s'." % COMPUTERS)
            sync_type = COMPUTERS

        if sync_type not in SyncTypes:
            raise ConfigError("Invalid sync_type: %r", self.sync_type)

        return sync_type

    def get_name_for_mapping_and_connection(self):
        """
        Depending on the sync type we have to ask for the mapping and send the data 
        to the Oomnitza as "Casper.MDM" or as "Casper"
        :return: 
        """
        sync_type = self.get_sync_type_from_settings()

        if sync_type == MOBILE_DEVICES:
            return self.MappingName + ".MDM"

        return self.MappingName

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)

        # ensure URL does not end with a trailing '/'
        self.settings['url'] = self.settings['url'].strip('/')

        self.url_template = "%s/{0}" % self.settings['url']

        self.sync_type = self.get_sync_type_from_settings()
        if self.sync_type == COMPUTERS:
            if 'APPLICATIONS' not in self.field_mappings:
                self.field_mappings['APPLICATIONS'] = {"source": "software.applications"}

        # set the mapping name to be used in the
        self.MappingName = self.get_name_for_mapping_and_connection()

        self.sync_config = SyncTypes[self.sync_type]
        self.group_name = self.settings.get("group_name", "")
        if self.group_name:
            LOG.info("Loading assets from group: %r", self.group_name)
            self.ids_url = self.url_template.format(
                self.sync_config['group_ids_path'].format(
                    name=urllib.parse.quote(self.group_name)
                )
            )
            self.ids_converter = lambda data: data['{}_group'.format(self.sync_config['data'])][self.sync_config['array']]
        else:
            self.ids_url = self.url_template.format(self.sync_config['all_ids_path'])
            self.ids_converter = lambda data: data[self.sync_config['array']]

        self.details_url = self.get_details_url(self.sync_type)

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
            return {'result': False, 'error': f'Connection Failed: {str(exp)}'}
        except HTTPError as exp:
            LOG.exception("Error testing connection!")
            return {'result': False, 'error': f'Connection Failed: {str(exp)}'}

    def _load_records(self, options):

        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        for device_info in connection_pool.imap(self.fetch_asset_details, self.fetch_asset_ids(), maxsize=pool_size):
            if device_info:
                yield device_info
            else:
                break

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
        # noinspection PyBroadException
        try:
            url = self.details_url.format(str(device_id))
            # print url
            details = self.get(url).json()[self.sync_config['data']]

            return details
        except:
            LOG.exception("fetch_asset_details( %s ) failed." % device_id)
            return None

    def server_handler(self, body, wsgi_env, options):
        """
        Webhook handler (https://github.com/brysontyrrell/Example-JSS-Webhooks)
        It will consume incoming POST request and perform a sync for a certain record
        """
        # noinspection PyBroadException
        try:
            payload = json.loads(body)

            event_type = payload['webhook']['webhookEvent']
            object_id = payload['event'].get('jssID')

            if object_id:
                if self.is_authorized():

                    if event_type.startswith('Computer'):
                        device = self.get(self.get_details_url(COMPUTERS).format(object_id)).json()['computer']
                    elif event_type.startswith('MobileDevice'):
                        device = self.get(self.get_details_url(MOBILE_DEVICES).format(object_id)).json()['mobile_device']
                    else:
                        LOG.warning('Casper unknown event caught. Cannot handle')
                        return

                    # sync retrieved device with Oomnitza
                    gevent.spawn(self.sender, *(self.OomnitzaConnector, device)).start()
        except:
            LOG.exception('Casper server handler failed')
