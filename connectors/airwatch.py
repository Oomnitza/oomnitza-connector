
import base64
import logging

from requests import ConnectionError, HTTPError
from lib.connector import AssetConnector

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name

"""
Curl Auth Test:
curl -v --user [USERNAME]:[PASSWORD] \
        --header "aw-tenant-code: [API-TOKEN]" \
        --header "Accept: application/json" \
        https://[HOST]/api/v1/help
"""


class Connector(AssetConnector):
    MappingName = 'AirWatch'
    Settings = {
        'url':        {'order': 1, 'default': "https://apidev.awmdm.com"},
        'username':   {'order': 2, 'example': "username@example.com"},
        'password':   {'order': 3, 'example': "change-me"},
        'api_token':  {'order': 4, 'example': "YOUR AirWatch API TOKEN"},
        'sync_field': {'order': 5, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    def __init__(self, settings):
        super(Connector, self).__init__(settings)
        self.url_template = "%s/api/v1/mdm/devices/search?pagesize={0}&page={1}" % self.settings['url']

    def get_headers(self):
        auth_string = self.settings['username'] + ":" + self.settings['password']
        return {
            'Authorization': b"Basic " + base64.b64encode(auth_string),
            'Accept': 'application/json',
            'aw-tenant-code': self.settings['api_token']
        }

    def test_connection(self, options):
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
            response = self.get(url).json()
            if total_device_count == 0:
                processed_device_count = 0
                total_device_count = response['Total']
            devices = response['Devices']
            for device in devices:
                processed_device_count += 1
                yield device

            page += 1
