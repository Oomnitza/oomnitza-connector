import logging

from gevent.pool import Pool
from requests.auth import _basic_auth_str

from lib import TrueValues
from lib.connector import AssetsConnector
from lib.error import ConfigError


COMPUTERS = 'computers'
MOBILE_DEVICES = 'mobiledevices'


LOG = logging.getLogger("connectors/simplemdm")


class Connector(AssetsConnector):
    """
    SimpleMDM integration
    """
    MappingName = 'SimpleMDM'
    Settings = {
        'secret_access_key':    {'order': 1, 'example': '***', 'default': ''},
        'device_groups':        {'order': 2, 'example': '', 'default': ''},
        'device_types':         {'order': 3, 'example': '{0},{1}'.format(COMPUTERS, MOBILE_DEVICES),
                                 'default': '{0},{1}'.format(COMPUTERS, MOBILE_DEVICES)},
        'custom_attributes':    {'order': 4, 'example': '0', 'default': '0'},

    }

    DefaultConverters = {
        "last_seen_at":     "timestamp"
    }

    FieldMappings = {
        'APPLICATIONS':      {'source': "software"},  # <-- default mapping for APPLICATIONS
    }

    def get_headers(self):
        return {
            'Authorization': _basic_auth_str(self.settings['secret_access_key'], ''),
            'Accept': 'application/json',
        }

    @staticmethod
    def get_device_type(device):
        """
        Check is based on the `cellular_technology` attribute value.
         If it is None - the cellular value is not applicable here, it is not a mobile device
        """
        return COMPUTERS if device['attributes']['cellular_technology'] is None else MOBILE_DEVICES

    def is_computer(self, device):
        return self.get_device_type(device) == COMPUTERS

    def paginator(self, url):
        """
        Generic paginator control used to handle any paginated resources in SimpleMDM API
        """
        starting_after = None
        while True:
            _url = url
            if starting_after:
                starting_after_query_arg = 'starting_after={0}'.format(starting_after)
                _url += ('&' + starting_after_query_arg) if '?' in _url else ('?' + starting_after_query_arg)

            records = self.get(_url).json()
            for record in records['data']:
                yield record

            if records['has_more'] and record:
                starting_after = record['id']

            else:
                break

    def get_device_groups_to_process(self):
        device_groups = []
        if self.settings['device_groups'].strip():
            try:
                device_groups = list(map(int, map(str.strip, self.settings['device_groups'].split(','))))
            except:
                raise ConfigError("Device groups have to be set as the integer IDs of groups separated with a comma")
        return device_groups

    def get_device_types_to_process(self):
        try:
            _device_types = list(map(str.lower, map(str.strip, self.settings['device_types'].split(','))))
        except:
            raise ConfigError("Invalid string values are used for the device types")
        device_types = [device_type for device_type in _device_types if device_type in (COMPUTERS, MOBILE_DEVICES)]
        if not device_types:
            device_types = [COMPUTERS, MOBILE_DEVICES]

        return device_types

    def get_device_custom_attributes(self, device):
        """
        https://simplemdm.com/docs/api/#get-values-for-device
        """
        device_id = device['id']
        url = 'https://a.simplemdm.com/api/v1/devices/{0}/custom_attribute_values'.format(device_id)
        custom_attribute_values = self.get(url).json()
        return {attr['id']: attr['attributes']['value'] for attr in custom_attribute_values['data']}

    def get_device_software(self, device):
        """
        https://simplemdm.com/docs/api/#list-installed-apps
        """
        device_id = device['id']
        url = 'https://a.simplemdm.com/api/v1/devices/{0}/installed_apps?limit=100'.format(device_id)

        all_installed_software = list(self.paginator(url))

        return [
            {
                'name': software['attributes']['name'],
                'version': software['attributes']['short_version'],
                'path': None  # < -- to keep compatibility
            } for software in all_installed_software
        ]

    def get_all_devices(self):
        """
        https://simplemdm.com/docs/api/#list-all41
        """
        url = 'https://a.simplemdm.com/api/v1/devices?limit=100'

        device_groups = self.get_device_groups_to_process()
        device_types = self.get_device_types_to_process()

        def is_device_ok_to_push(_device):
            """
            closure used to decide if the device has to be processed / pushed to the oomnitza
            """
            if self.get_device_type(_device) in device_types:
                _device_group_id = _device['relationships']['device_group']['data']['id']
                if (device_groups and _device_group_id in device_groups) or not device_groups:
                    return True

            return False

        for device in self.paginator(url):
            if is_device_ok_to_push(device):
                yield device

    def prepare_device(self, device):
        call_for_custom_attributes = self.settings['custom_attributes'] in TrueValues
        device_info = device['attributes']
        if call_for_custom_attributes:
            device_info['custom_attributes'] = self.get_device_custom_attributes(device)

        software = []
        if self.is_computer(device):
            software = self.get_device_software(device)

        device_info['software'] = software
        return device_info

    def _load_records(self, options):
        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        for device_info in connection_pool.imap(
            self.prepare_device,
            self.get_all_devices(),
            maxsize=pool_size
        ):
            yield device_info
