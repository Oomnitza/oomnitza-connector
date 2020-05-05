import base64
import logging

from gevent.pool import Pool
from requests import ConnectionError, HTTPError
from requests.exceptions import RetryError

from lib.connector import AssetsConnector

logger = logging.getLogger("connectors/airwatch")  # pylint:disable=invalid-name


class Connector(AssetsConnector):
    MappingName = 'AirWatch'
    Settings = {
        'url':        {'order': 1, 'default': "https://apidev.awmdm.com"},
        'username':   {'order': 2, 'example': "username@example.com"},
        'password':   {'order': 3, 'example': "change-me"},
        'api_token':  {'order': 4, 'example': "YOUR AirWatch API TOKEN"},
        'dep_uuid':   {'order': 6, 'default': ''}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.url_template = "%s/api/mdm/devices/search?pagesize={0}&page={1}" % self.settings['url']
        self.network_url_template = "%s/api/mdm/devices/{device_id}/network" % self.settings['url']
        self.dep_devices = {}  # this is the storage for the device info retrieved through the DEP-specific API

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
            device['network'] = self._load_network_information(device.get('Id', {}).get('Value', ''))
            return device

        def set_dep_info(device):
            serial_number = device.get('SerialNumber')
            if serial_number:
                dep_info_about_device = self.dep_devices.get(serial_number)
                if dep_info_about_device:
                    device['dep'] = dep_info_about_device
            return device

        # extend the info about devices using info from the separate API
        if self.dep_devices:
            devices = map(set_dep_info, devices)

        if self.__load_network_data:
            pool_size = self.settings['__workers__']
            connection_pool = Pool(size=pool_size)
            processed_devices = connection_pool.map(set_network_info, devices)
        else:
            processed_devices = devices

        return processed_devices

    def _load_records(self, options):

        if self.settings.get('dep_uuid'):
            # if the dep_uuid is given, we have to retrieve the different subset of devices from the separate API
            # it is not clear from the docs if the API supports pagination, looks like not
            # also this API is supported only by the AirWatch starting from 9.2(?)
            dep_api_url = '%s/api/mdm/dep/groups/%s/devices' % (self.settings['url'], self.settings['dep_uuid'])
            self.dep_devices = {_['deviceSerialNumber']: _ for _ in self.get(dep_api_url).json()}

        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        for device_info in connection_pool.imap(self.retrieve_device_info, self.device_page_generator(options), maxsize=pool_size):
            if not device_info:
                raise StopIteration
            yield device_info

    def _load_network_information(self, device_id):
        try:
            if not device_id:
                return {}

            url = self.network_url_template.format(device_id=device_id)
            response = self.get(url).json()
            return response
        except (HTTPError, RetryError):
            logger.exception("Error trying to load network details for device: %s", device_id)
            return {}
