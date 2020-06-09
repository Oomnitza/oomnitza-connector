from lib.connector import AssetsConnector


class Connector(AssetsConnector):
    """
    Meraki SM (EMM solution) connector 
    """
    MappingName = 'MerakiSM'
    Settings = {
        'meraki_api_key':   {'order': 1, 'example': '', 'default': ""},
        'network_id':       {'order': 2, 'example': 'N_**************', 'default': ""},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.base_api_url = 'https://dashboard.meraki.com/api/v0/{0}'
        self.sm_devices_additional_fields = ','.join((
            'ip', 'systemType', 'availableDeviceCapacity', 'kioskAppName', 'biosVersion', 'lastConnected', 'userSuppliedAddress',
            'location', 'lastUser', 'publicIp', 'phoneNumber', 'diskInfoJson', 'deviceCapacity', 'isManaged', 'hadMdm', 'isSupervised', 'meid',
            'imei', 'iccid', 'simCarrierNetwork', 'cellularDataUsed', 'isHotspotEnabled', 'createdAt', 'batteryEstCharge', 'quarantined', 'avName',
            'avRunning', 'asName', 'fwName', 'isRooted', 'loginRequired', 'screenLockEnabled', 'screenLockDelay', 'autoLoginDisabled',
            'hasMdm', 'hasDesktopAgent', 'diskEncryptionEnabled', 'hardwareEncryptionCaps', 'passCodeLock'
        ))

    def get_headers(self):
        return {
            'X-Cisco-Meraki-API-Key': self.settings['meraki_api_key']
        }

    def yield_devices_from_network(self, network_id):
        cursor = None

        while True:
            network_sm_devices_url = self.base_api_url.format(
                'networks/{0}/sm/devices?fields={1}'.format(
                    network_id, self.sm_devices_additional_fields
                )
            )
            if cursor:
                network_sm_devices_url += '&batchToken={0}'.format(cursor)

            network_sm_devices = self.get(network_sm_devices_url).json()

            for device in network_sm_devices['devices']:
                yield device

            cursor = network_sm_devices.get('batchToken')
            if not cursor:
                raise StopIteration

    def _load_records(self, options):

        for organization_network_device in self.yield_devices_from_network(
                self.settings['network_id']
        ):
            yield organization_network_device
