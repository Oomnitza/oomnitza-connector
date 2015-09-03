import os
import json
import logging
import errno
import math
import time

from requests import ConnectionError, HTTPError, RequestException
from lib.connector import AuditConnector
from lib.error import ConfigError

LOG = logging.getLogger("connectors/casper")  # pylint:disable=invalid-name


SyncTypes = {
    "computers": dict(path="JSSResource/computers", array="computers", data="computer"),
    "mobiledevices": dict(path="JSSResource/mobiledevices", array="mobile_devices", data="mobile_device"),
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
    }
    DefaultConverters = {
        "general.report_date":         "date_format",
        "general.last_contact_time":   "date_format",
        "general.initial_entry_date":  "date_format",
        "purchasing.warranty_expires": "date_format",
        "purchasing.lease_expires":    "date_format",
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
        sync_type = self.settings.get('sync_type', 'computers')
        self.sync_type = SyncTypes[sync_type]
        if sync_type == "computers":
            print self.field_mappings.keys()
            if 'APPLICATIONS' not in self.field_mappings:
                self.field_mappings['APPLICATIONS'] = {"source": "software.applications"}
        else:
            self.MappingName = Connector.MappingName+".MDM"
        self._api_root = self.sync_type['path']
        self._retry_counter = 0

    def get_headers(self):
        return {
            'Accept': 'application/json'
        }

    def get_auth(self):
        return self.settings['username'], self.settings['password']

    def do_test_connection(self, options):
        try:
            url = self.url_template.format("JSSResource/computers")
            response = self.get(url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        for id in self.fetch_computer_ids():
            while self._retry_counter <= Connector.RetryCount:
                try:
                    computer = self.fetch_computer_details(id)
                    yield computer
                    break
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

    def fetch_computer_ids(self):
        """
        This method is used to retrieve the ids of computers in Casper
        """
        response = self.get(self.url_template.format(self._api_root))
        return [c['id'] for c in response.json()[self.sync_type['array']]]

    def fetch_computer_details(self, id):
        """
        This method is used to retrieve the details of computer by its Casper's ID
        """
        url = self.url_template.format("{}/id/{}".format(self.sync_type['path'], str(id)))
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
