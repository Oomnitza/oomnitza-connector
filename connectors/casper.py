import os
import json
import logging
import errno
import math
import time
import urllib

from requests import ConnectionError, HTTPError, RequestException
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
        # Not sure mac_model_from_sn should be applied by default. -djs
        # "hardware.model":              "mac_model_from_sn",
    }

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

        self.details_url = self.url_template.format(
            "JSSResource/%s/id/{}" % sync_type
        )

        self._retry_counter = 0

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
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except HTTPError as exp:
            LOG.exception("Error testing connection!")
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        for id in self.fetch_asset_ids():
            while self._retry_counter <= Connector.RetryCount:
                try:
                    computer = self.fetch_asset_details(id)
                    if computer:
                        yield computer
                    break  # out of retry loop
                except RequestException:
                    self._retry_counter += 1
                    LOG.exception("Error getting devices details for %r. Attempt #%s failed.",
                                  id,
                                  self._retry_counter)
                    sleep_secs = math.pow(2, min(self._retry_counter, 8))
                    LOG.warning("Sleeping for %s seconds.", sleep_secs)
                    time.sleep(sleep_secs)

            if self._retry_counter > Connector.RetryCount:
                LOG.error("Retry limit of %s attempts has been exceeded.", Connector.RetryCount)
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
        except HTTPError as exp:
            if self.group_name:
                LOG.error("Error loading assets for group: %r. Please verify the group name is correct.", self.group_name)
            else:
                LOG.exception("Error loading IDs from Casper.")
            return []
        # except Exception as exp:
        #     LOG.exception("C")
        #     raise

    def fetch_asset_details(self, id):
        """
        This method is used to retrieve the details of an asset by its Casper's ID
        """
        try:
            url = self.details_url.format(str(id))
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
                with open("./saved_data/{}.json".format(str(id)), "w") as save_file:
                    save_file.write(json.dumps(details))

            return details
        except:
            LOG.exception("fetch_ssset_details( {} ) failed." % id)
            return None
