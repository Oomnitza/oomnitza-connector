import base64
import errno
import json
import logging
import os
import uuid

from gevent.pool import Pool
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
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}

    def device_page_url_generator(self, options):
        """
        This is generator of urls for device pages
        :return:
        """
        page = options.get('start_page', 0)
        rows = options.get('rows_per_page', 250)
        while True:
            yield self.url_template.format(rows, page)
            page += 1

    def get_device_page_info(self, page_url):
        """
        This is method used to return page information
        :param page_url: url for the airwatch `page`
        :return:
        """
        response = self.get(page_url)
        try:
            response.raise_for_status()
        except HTTPError:
            return []

        if response.status_code == 204:
            # Sometimes it is just an empty response!
            # logger.error("Got a 204 (Empty Response) from AirWatch! No devices found to process.")
            return []

        response = response.json()
        return response['Devices']

    def device_page_generator(self, options):
        """
        Page info generator
        :param options:
        :return:
        """

        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        for page in connection_pool.imap(self.get_device_page_info, self.device_page_url_generator(options), maxsize=pool_size):
            if not page:
                raise StopIteration
            yield page

    def retrieve_device_info(self, devices):
        """
        Extract device info

        :param devices: list of devices to process
        :return:
        """
        def set_network_info(device):
            device['network'] = self._load_network_information(device['MacAddress'])
            return device

        if self.__load_network_data:
            pool_size = self.settings['__workers__']
            connection_pool = Pool(size=pool_size)
            processed_devices = connection_pool.map(set_network_info, devices)
        else:
            processed_devices = devices

        if self.settings.get("__save_data__", False):
            try:
                os.makedirs("./saved_data")
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                    pass
                else:
                    raise
            with open("./saved_data/{}.json".format(uuid.uuid4().hex), "w") as save_file:
                save_file.write(json.dumps(processed_devices))
        return processed_devices

    def _load_records(self, options):

        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        for device_info in connection_pool.imap(self.retrieve_device_info, self.device_page_generator(options), maxsize=pool_size):
            if not device_info:
                raise StopIteration
            yield device_info

    def _load_network_information(self, mac_address):
        try:
            mac_address = mac_address.strip()
            if not mac_address:
                return {}

            url = self.network_url_template.format(mac=mac_address)
            response = self.get(url).json()
            return response
        except HTTPError:
            logger.exception("Error trying to load network details for device: %s", mac_address)
            return {}
