import os
import base64
import logging
import errno
import json

from requests import ConnectionError, HTTPError
from lib.connector import AuditConnector

logger = logging.getLogger("connectors/airwatch")  # pylint:disable=invalid-name

"""
Curl Auth Test:
curl -v --user [USERNAME]:[PASSWORD] \
        --header "aw-tenant-code: [API-TOKEN]" \
        --header "Accept: application/json" \
        https://[HOST]/api/v1/help
"""


class Connector(AuditConnector):
    MappingName = 'AirWatch'
    Settings = {
        'url':        {'order': 1, 'default': "https://apidev.awmdm.com"},
        'username':   {'order': 2, 'example': "username@example.com"},
        'password':   {'order': 3, 'example': "change-me"},
        'api_token':  {'order': 4, 'example': "YOUR AirWatch API TOKEN"},
        'sync_field': {'order': 5, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.url_template = "%s/api/v1/mdm/devices/search?pagesize={0}&page={1}" % self.settings['url']
        self.network_url_template = "%s/api/v1/mdm/devices/macaddress/{mac}/network" % self.settings['url']

        self.__load_network_data = False
        for key, value in self.field_mappings.items():
            if 'network.' in value.get('source', ''):
                self.__load_network_data = True
                logger.info("Network data request.")
                break

    def get_headers(self):
        auth_string = self.settings['username'] + ":" + self.settings['password']
        return {
            'Authorization': b"Basic " + base64.b64encode(auth_string),
            'Accept': 'application/json',
            'aw-tenant-code': self.settings['api_token']
        }

    def do_test_connection(self, options):
        try:
            page = options.get('start_page', 0)
            rows = options.get('rows_per_page', 1)
            url = self.url_template.format(rows, page)
            response = self.get(url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        page = options.get('start_page', 0)
        rows = options.get('rows_per_page', 500)
        processed_device_count = -1
        total_device_count = 0

        while processed_device_count < total_device_count:
            url = self.url_template.format(rows, page)
            try:
                response = self.get(url)
                response = response.json()
                if total_device_count == 0:
                    processed_device_count = 0
                    total_device_count = response['Total']
                devices = response['Devices']
            except ValueError as exp:
                logger.exception("Error getting data from AirWatch.")
                if hasattr(exp, 'doc'):
                    logger.error("Error Document: %r", exp.doc)
                devices, total_device_count = [], -1

            for device in devices:
                if self.__load_network_data:
                    device['network'] = self._load_network_information(device['MacAddress'])

                processed_device_count += 1
                if self.settings.get("__save_data__", False):
                    try:
                        os.makedirs("./saved_data")
                    except OSError as exc:
                        if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                            pass
                        else:
                            raise
                    with open("./saved_data/{}.json".format(str(processed_device_count)), "w") as save_file:
                        save_file.write(json.dumps(device))
                yield device

            page += 1

    def _load_network_information(self, mac_address):
        try:
            mac_address = mac_address.strip()
            if not mac_address:
                return {}

            url = self.network_url_template.format(mac=mac_address)
            response = self.get(url).json()
            return response
        except Exception as e:
            logger.exception("Error trying to load network details for device: %s", url)
            return {}
