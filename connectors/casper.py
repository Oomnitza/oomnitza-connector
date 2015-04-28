import os
import json
import logging
import errno

from requests import ConnectionError, HTTPError
from lib.connector import AuditConnector

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


SyncTypes = {
    "computers": dict(path="JSSResource/computers", array="computers", data="computer"),
    "mobiledevices": dict(path="JSSResource/mobiledevices", array="mobile_devices", data="mobile_device"),
}


class Connector(AuditConnector):
    MappingName = 'Casper'
    Settings = {
        'url':         {'order': 1, 'default': "https://apidev.awmdm.com"},
        'username':    {'order': 2, 'example': "username@example.com"},
        'password':    {'order': 3, 'example': "qwerty123"},
        'sync_field':  {'order': 4, 'example': '24DCF85294E411E38A52066B556BA4EE'},
        'sync_type':   {'order': 5, 'default': "computers", 'choices': ("computers", "mobiledevices")},
        'verify_ssl':  {'order': 6, 'default': "True"},
        'update_only': {'order': 7, 'default': "False"}
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

    def __init__(self, settings):
        super(Connector, self).__init__(settings)
        self.url_template = "%s/{0}" % self.settings['url']
        sync_type = self.settings.get('sync_type', 'computers')
        self.sync_type = SyncTypes[sync_type]
        if sync_type == "computers":
            self.field_mappings['APPLICATIONS'] = {"source": "software.applications"}
        else:
            self.MappingName = Connector.MappingName+".MDM"
        self._api_root = self.sync_type['path']

    def get_headers(self):
        return {
            'Accept': 'application/json'
        }

    def get_auth(self):
        return self.settings['username'], self.settings['password']

    def test_connection(self, options):
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
        # if False:
        #     import os
        #     for filename in [f for f in os.listdir('testing/snapchat/casper') if f.endswith('.json')]:
        #         with open('testing/snapchat/casper/{}'.format(filename), 'r') as in_json:
        #             j = json.load(in_json)
        #             j['status123'] = filename
        #             yield j
        #     return
        for id in self.fetch_computer_ids():
            computer = self.fetch_computer_details(id)
            yield computer

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
