import logging
import json
import requests

from gevent.pool import Pool
from requests import HTTPError
from requests.auth import _basic_auth_str
from requests.exceptions import RetryError
from converters import mac_address_converter
from lib.connector import AssetsConnector

logger = logging.getLogger("connectors/airwatch")  # pylint:disable=invalid-name


class Connector(AssetsConnector):
    MappingName = 'AirWatch'
    Settings = {
        'url': {'order': 1, 'default': "https://apidev.awmdm.com"},
        'username': {'order': 2, 'example': "username@example.com"},
        'password': {'order': 3, 'example': "change-me"},
        'api_token': {'order': 4, 'example': "YOUR AirWatch API TOKEN"},
        'dep_uuid': {'order': 6, 'default': ''}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.url_template = "%s/api/mdm/devices/search?pagesize={0}&page={1}" % self.settings['url']
        self.network_url_template = "%s/api/mdm/devices/{device_id}/network" % self.settings['url']
        self.encryption_url_template = "%s/api/mdm/devices/{device_id}/security" % self.settings[
            'url']
        self.applications_url_template = "%s/api/mdm/devices/{device_id}/apps" % self.settings[
            'url']
        self.dep_devices = {}  # this is the storage for the device info retrieved through the DEP-specific API

        self.__load_network_data = False
        for key, value in self.field_mappings.items():
            if 'network.' in value.get('source', ''):
                self.__load_network_data = True
                logger.info("Network data request.")
                break

    def get_headers(self):
        return {
            'Authorization': _basic_auth_str(self.settings['username'], self.settings['password']),
            'Accept': 'application/json',
            'aw-tenant-code': self.settings['api_token']
        }

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

        for page in connection_pool.imap(self.get_device_page_info,
                                         self.device_page_url_generator(options),
                                         maxsize=pool_size):
            if not page:
                break
            yield page

    def retrieve_device_info(self, devices):
        """
        Extract device info

        :param devices: list of devices to process
        :return:
        """

        def set_network_info(device):
            device['network'] = self._load_network_information(
                device.get('Id', {}).get('Value', ''))
            serial_number = device.get('SerialNumber', {})
            network_info = device['network']
            additional_adapters = network_info.get('DeviceNetworkInfo', {})

            device['airwatch_network_info'] = json.dumps(additional_adapters)
            network_info_size = len(device['airwatch_network_info'])
            if network_info_size > 1024:
                logger.error(
                    "Raw airwatch network info for %s is too large %s. Data has been clipped to 1024 characters.",
                    serial_number, network_info_size)
                device['airwatch_network_info'] = device['airwatch_network_info'][:1024]
            device['public_ip'] = network_info.get('PublicIPAddress')

            mac_address = device.get('MacAddress', '')
            if mac_address:
                device['MacAddress'] = mac_address_converter.converter(mac_address,
                                                                       integration_name=self.MappingName)

            wifi_info = network_info.get('WifiInfo', None)
            if wifi_info:
                device['wifi_mac_address'] = mac_address_converter.converter(
                    wifi_info.get('WifiMacAddress'), integration_name=self.MappingName)
                if not device['wifi_mac_address']:
                    logger.debug("Didn't find a wifi mac address...so we're not updating it")
                    device.pop('wifi_mac_address')

            device['airwatch_mac_addresses'] = []
            device['airwatch_bluetooth_mac_addresses'] = []
            device['airwatch_usb_mac_addresses'] = []

            for adapter in additional_adapters:
                adapter_type = adapter.get('ConnectionType')
                mac_address = mac_address_converter.converter(adapter.get('MACAddress'),
                                                              integration_name=self.MappingName)
                # If the mac address has been removed by the converter then skip it
                if not mac_address:
                    continue

                if adapter_type == "USB":
                    device['airwatch_usb_mac_addresses'].append(mac_address)
                elif adapter_type == "Bluetooth":
                    device['airwatch_bluetooth_mac_addresses'].append(mac_address)
                else:
                    device['airwatch_mac_addresses'].append(mac_address)

            device['airwatch_mac_addresses'] = ",".join(
                sorted(list(set(device['airwatch_mac_addresses'])))).lstrip(',')
            device['airwatch_bluetooth_mac_addresses'] = ",".join(
                sorted(list(set(device['airwatch_bluetooth_mac_addresses'])))).lstrip(',')
            device['airwatch_usb_mac_addresses'] = ",".join(
                sorted(list(set(device['airwatch_usb_mac_addresses'])))).lstrip(',')

            # device = self._fix_mac_address(device)
            return device

        def set_encryption_info(device):
            device_id = device.get('Id', {}).get('Value', '')
            aw_sec_info = self._load_encryption_information(device_id)
            device['airwatch_encrypted'] = aw_sec_info.get('IsEncrypted', False)
            device['airwatch_encryption_status'] = aw_sec_info.get('EncryptionStatus', False)
            device['airwatch_personal_recovery_key'] = aw_sec_info.get('PersonalRecoveryKey', None)
            device['airwatch_id'] = device_id
            device['airwatch_security'] = json.dumps(aw_sec_info)

            return device

        def set_application_info(device):
            device_id = device.get('Id', {}).get('Value', '')
            apps_list_response = self._load_application_information(device_id)
            apps_list = apps_list_response.get('DeviceApps', [])

            apps_list = sorted(apps_list, key=lambda app_name: app_name['ApplicationName'])
            base_field_key = "airwatch_applications"
            max_fields = 4
            max_field_len = 4096
            current_field = 1
            field_key = f"{base_field_key}_{current_field}"
            device[field_key] = []
            for app_object in apps_list:
                appname = app_object.get('ApplicationName', 'Unknown Application')
                is_managed = app_object.get('IsManaged', False)
                if appname:
                    if isinstance(device[field_key], str):
                        logger.error("Wait a minute!")
                    else:
                        device[field_key].append(appname)
                    appslist_str = ",".join(device[field_key])
                    if len(appslist_str) > max_field_len:
                        del device[field_key][-1]  # Remove the entry that made an overflow
                        device[field_key] = ",".join(device[field_key])
                        logger.debug("%s length is %s", field_key, len(device[field_key]))
                        current_field += 1
                        if current_field > max_fields:
                            logger.error("Unable to get all apps for device %s (%s)", device_id,
                                         device.get('DeviceFriendlyName', 'SerialNumber'))
                            break
                        field_key = f"{base_field_key}_{current_field}"
                        device[field_key] = [appname, ]
            if isinstance(device[field_key], list):
                device[field_key] = ",".join(device[field_key])
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
            devices = list(map(set_dep_info, devices))

        if self.__load_network_data:
            pool_size = self.settings['__workers__']
            connection_pool = Pool(size=pool_size)
            processed_devices = connection_pool.map(set_network_info, devices)
        else:
            pool_size = self.settings['__workers__']
            connection_pool = Pool(size=pool_size)
            processed_devices = connection_pool.map(set_network_info, devices)
            processed_devices = connection_pool.map(set_encryption_info, processed_devices)
            processed_devices = connection_pool.map(set_application_info, processed_devices)
            # processed_devices = connection_pool.map(set_application_info, devices)

        return processed_devices

    def _load_records(self, options):

        if self.settings.get('dep_uuid'):
            # if the dep_uuid is given, we have to retrieve the different subset of devices from the separate API
            # it is not clear from the docs if the API supports pagination, looks like not
            # also this API is supported only by the AirWatch starting from 9.2(?)
            dep_api_url = '%s/api/mdm/dep/groups/%s/devices' % (
            self.settings['url'], self.settings['dep_uuid'])
            self.dep_devices = {_['deviceSerialNumber']: _ for _ in self.get(dep_api_url).json()}

        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        for device_info in connection_pool.imap(self.retrieve_device_info,
                                                self.device_page_generator(options),
                                                maxsize=pool_size):
            if not device_info:
                break
            yield device_info

    def _load_encryption_information(self, device_id):
        try:
            if not device_id:
                return {}

            url = self.encryption_url_template.format(device_id=device_id)
            response = self.get(url).json()
            return response
        except HTTPError:
            logger.exception("Error trying to load encryption details for device: %s", device_id)
            return {}

    def _load_application_information(self, device_id):
        try:
            if not device_id:
                return {}

            url = self.applications_url_template.format(device_id=device_id)
            response = self.get(url).json()
            return response
        except HTTPError:
            logger.exception("Error trying to load application details for device: %s", device_id)
            return {}

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
