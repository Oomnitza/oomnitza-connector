import logging
import math
import time
from distutils.util import strtobool
from enum import Enum

from gevent.pool import Pool
from requests import HTTPError
from requests.auth import _basic_auth_str
from requests.exceptions import RetryError

from lib.connector import AssetsConnector

LOG = logging.getLogger("connectors/mobileiron")

Version = Enum('Version', ['v1', 'v2'])  # TODO: set proper cases


class Connector(AssetsConnector):
    MappingName = 'MobileIron'
    RetryCount = 10

    Settings = {
        'url':        {'order': 1, 'default': "https://na1.mobileiron.com"},
        'username':   {'order': 2, 'example': "username@example.com"},
        'password':   {'order': 3, 'example': "change-me"},
        'partitions': {'order': 4, 'example': '["Drivers"]', 'is_json': True},
        'api_version': {'order': 6, 'example': '1', 'default': '1'},
        'include_checkin_devices_only': {'order': 7, 'example': 'True', 'default': 'True'},
        'last_checkin_date_threshold': {'order': 8, 'example': '129600', 'default': '129600'},
    }

    api_version = None

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        if self.settings.get('api_version') == '2':
            self.api_version = Version.v2
        else:
            self.api_version = Version.v1
        self._retry_counter = 0

    def get_headers(self):
        headers = {
            'Authorization': _basic_auth_str(self.settings['username'], self.settings['password']),
            'Accept': 'application/json'
        }
        return headers

    @staticmethod
    def get_primary_cpu_hdd_ram_placeholder():
        return {
            'primaryHDDSize': None,
            'primaryProcessorName': None,
            'primaryProcessorCores': None,
            'primaryMemoryCapacity': None
        }

    @staticmethod
    def is_windows_device(device):
        return bool(device.get('windowsDeviceType'))

    def fetch_device_hardware_by_id(self, id):
        device_hardware = {}
        try:
            url = f"{self.settings['url']}/api/v1/device/{id}/hardwareinventory"
            response = self.get(url).json()
            device_hardware = response.get('result')
        except (HTTPError, RetryError) as exc:
            LOG.exception(f'Unable to fetch hardware data for device: {id}')
        return device_hardware

    @staticmethod
    def extract_primary_processor(device_hardware):
        primary_processor_name = None
        primary_processor_cores = None
        if isinstance(device_hardware, dict):
            processors = device_hardware.get('processor')
            if processors and isinstance(processors, list):
                primary_processor = processors[0]
                primary_processor_name = primary_processor.get('name') if isinstance(primary_processor, dict) else None
                primary_processor_cores = primary_processor.get('cores') if isinstance(primary_processor, dict) else None

        return {
            'primaryProcessorName': primary_processor_name,
            'primaryProcessorCores': primary_processor_cores,
        }

    @staticmethod
    def extract_primary_hdd_size(device_hardware):
        primary_hdd_size = None
        if isinstance(device_hardware, dict):
            hard_drives = device_hardware.get('hardDrive')
            if hard_drives and isinstance(hard_drives, list):
                primary_hdd = hard_drives[0]
                primary_hdd_size = primary_hdd.get('size') if isinstance(primary_hdd, dict) else None

        return {
            'primaryHDDSize': primary_hdd_size
        }

    @staticmethod
    def extract_primary_ram_capacity(device_hardware):
        primary_ram_capacity = None
        if isinstance(device_hardware, dict):
            physical_memory = device_hardware.get('physicalMemory')
            if physical_memory and isinstance(physical_memory, list):
                primary_ram = physical_memory[0]
                primary_ram_capacity = primary_ram.get('capacity') if isinstance(primary_ram, dict) else None

        return {
            'primaryMemoryCapacity': primary_ram_capacity
        }

    @staticmethod
    def extract_windows_device_serial_number(device_hardware):
        serial_number = None
        if isinstance(device_hardware, dict):
            computer_system_product = device_hardware.get('computerSystemProduct')
            if computer_system_product and isinstance(computer_system_product, dict):
                serial_number = computer_system_product.get('identifyingNumber')

        return {
            'serialNumber': serial_number
        }

    def load_primary_cpu_hdd_ram_and_serial_for_windows_device(self, device):
        if not isinstance(device, dict):
            raise AssertionError(f'The devices must be in a form of dictionary')

        primary_cpu_hdd_ram_placeholder = self.get_primary_cpu_hdd_ram_placeholder()
        device.update(primary_cpu_hdd_ram_placeholder)

        if self.is_windows_device(device) and device.get('id'):
            device_hardware = self.fetch_device_hardware_by_id(device['id'])
            if device_hardware:
                device.update(self.extract_primary_processor(device_hardware))
                device.update(self.extract_primary_hdd_size(device_hardware))
                device.update(self.extract_primary_ram_capacity(device_hardware))
                device.update(self.extract_windows_device_serial_number(device_hardware))
        return device

    def load_hardware_and_serial_for_windows_devices(self, devices):
        if not isinstance(devices, list):
            raise AssertionError(f'The devices must be in a form of list')

        pool_size = self.settings.get('__workers__', 2)
        connection_pool = Pool(size=pool_size)
        return connection_pool.map(self.load_primary_cpu_hdd_ram_and_serial_for_windows_device, devices)

    def load_devices_api_v1(self, *a, **kw):
        for partition in self.fetch_all_partitions():
            if self.settings['partitions'] == "All" or partition['name'] in self.settings['partitions']:
                pool_size = self.settings.get('__workers__', 2)
                connection_pool = Pool(size=pool_size)
                for device in connection_pool.imap(self.load_hardware_and_serial_for_windows_devices,
                                                   self.fetch_all_devices_for_partition(partition['id']),
                                                   maxsize=pool_size):
                    yield device
            else:
                LOG.debug("Skipping partition %r", partition)

    def load_spaces_api_v2(self):
        url = self.settings['url'] + "/api/v2/device_spaces/mine"

        response = self.get(url)
        spaces = response.json()['results']

        for space in spaces:
            yield space['id']

    def load_space_fields_api_v2(self, space):
        url = self.settings['url'] + "/api/v2/device_spaces/criteria?adminDeviceSpaceId={space}".format(space=space)

        response = self.get(url)
        fields = response.json()['results']

        return [_['name'] for _ in fields]

    def load_devices_api_v2(self, *a, **kw):

        url_template = self.settings['url'] + "/api/v2/devices?adminDeviceSpaceId={space}&fields={fields}&labelId=-1&limit={limit}&offset={offset}"

        for space in self.load_spaces_api_v2():

            limit = 50
            offset = 0

            fields = ','.join(self.load_space_fields_api_v2(space))
            while True:
                response = self.get(url_template.format(limit=limit, offset=offset, space=space, fields=fields))
                response_body = response.json()
                devices = response_body['results']

                for device in devices:
                    yield device

                if not response_body['hasMore']:
                    break

                offset += limit

    def _load_records(self, options):
        generator = {

            Version.v1: self.load_devices_api_v1(),
            Version.v2: self.load_devices_api_v2()

        }[self.api_version]

        # noinspection PyTypeChecker
        for device in generator:
            yield device

    def fetch_all_partitions(self):
        """
        Fetches all available device partitions using the MobileIron REST API.
        /api/v1/tenant/partition/device
        """
        url = self.settings['url'] + "/api/v1/tenant/partition/device"
        response = self.get(url)
        response.raise_for_status()

        partitions = [{'id': x['id'], 'name': x['name']} for x in response.json()['result']['searchResults']]
        # logger.debug("partitions = %r", partitions)
        return partitions

    def keep_device_in_results(self, now, last_checkin_date):
        include_checkin_devices_only = bool(strtobool(self.settings.get('include_checkin_devices_only', '1')))
        if include_checkin_devices_only:
            one_point_five_days_in_sec = 60 * 60 * 24 * 1.5
            last_checkin_date_threshold = int(self.settings.get('last_checkin_date_threshold', one_point_five_days_in_sec))
            cutoff = int((now - last_checkin_date_threshold) * 1000)
            return isinstance(last_checkin_date, int) and last_checkin_date >= cutoff
        return True

    def fetch_all_devices_for_partition(self, partition_id, rows=500):
        """
        Fetches all available device for a provided partition using the MobileIron REST API.
        Yields response objects for all each partition offset/page.

        Note: 'offset' does not operate as the MobileIron documentation indicates. We should
        instead use 'start' and pass the latest index

        /api/v1/device?dmPartitionId=X
        """
        url = "{0}/api/v1/device?dmPartitionId={1}&rows={2}&start={3}&sortFields[0].name=lastCheckin&sortFields[0].order=DESC"
        start = -1
        total_count = 0
        now = time.time()

        while start < total_count:
            if self._retry_counter > Connector.RetryCount:
                LOG.error("Retry limit of %s attempts has been exceeded.", Connector.RetryCount)
                break
            if start == -1:
                start = 0
            try:
                response = self.get(url.format(self.settings['url'], partition_id, rows, start))
                result = response.json()['result']
                if total_count == 0:
                    total_count = result['totalCount']

                LOG.info("Processing devices %s-%s of %s", start, start+len(result['searchResults']), total_count)
                # yield result['searchResults']
                results = [r for r in result['searchResults'] if self.keep_device_in_results(now, r.get('lastCheckin'))]
                if results:
                    yield results
                else:
                    LOG.info("No more records found after cutoff date.")
                    break  # we have run out of records to process. The rest will be before the cutoff date.
                start += len(result['searchResults'])
            except:
                LOG.exception("Error getting devices for partition. Attempt #%s failed.", self._retry_counter+1)
                self._retry_counter += 1
                sleep_secs = math.pow(2, min(self._retry_counter, 8))
                LOG.warning("Sleeping for %s seconds.", sleep_secs)
                time.sleep(sleep_secs)
