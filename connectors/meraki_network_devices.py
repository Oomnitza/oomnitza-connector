from lib.connector import AssetsConnector

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################


class Connector(AssetsConnector):
    """
    Meraki Network Devices connector
    """
    MappingName = 'meraki_network_devices'
    Settings = {
        'meraki_api_key': {'order': 1, 'example': '', 'default': ""},
        'org_id': {'order': 2, 'example': '******', 'default': ""},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.api_key = 'X-Cisco-Meraki-API-Key'
        self.get_networks_api = 'https://api.meraki.com/api/v1/organizations/{id}/networks?' \
                                'perPage=100&startingAfter={network_id}'
        self.get_network_devices_api = 'https://api.meraki.com/api/v1/networks/{id}/devices'
        self.get_inventory_devices_api = 'https://api.meraki.com/api/v1/organizations/{org_id}/inventoryDevices?' \
                                         'perPage=100&startingAfter={serial_number}'

    def get_headers(self):
        api_token = self.settings[self.api_key] if self.settings.get(self.api_key) else self.settings['meraki_api_key']
        return {self.api_key: api_token}

    def get_chunked_network_devices(self, network_id):
        return self.get(self.get_network_devices_api.format(id=network_id)).json()

    def yield_devices_from_network(self, org_id):
        # Build up the network ids first, then grab the devices.
        network_ids = self.get_all_network_ids(org_id)

        for network_id in network_ids:
            if network_id:
                for network_device in self.get_chunked_network_devices(network_id):
                    yield network_device

    def get_chunked_inventory_devices(self, org_id, starting_after=''):
        device_inventory_api = self.get_inventory_devices_api.format(org_id=org_id, serial_number=starting_after)
        chunked_inventory_devices = self.get(device_inventory_api).json()
        if chunked_inventory_devices:
            return chunked_inventory_devices, chunked_inventory_devices[-1].get('serial')
        return chunked_inventory_devices, ''

    def yield_inventory_device(self, org_id):
        inventory_devices, starting_after = self.get_chunked_inventory_devices(org_id)

        while inventory_devices:
            for inventory_device in inventory_devices:
                yield inventory_device
            inventory_devices, starting_after = self.get_chunked_inventory_devices(org_id, starting_after)

    def get_all_network_ids(self, org_id):
        """ Get All the network ids in a give Meraki org. """
        network_id = ""
        network_ids = []
        while True:
            org_network_api = self.get_networks_api.format(id=org_id, network_id=network_id)
            _chunked_network_ids = [network.get('id') for network in self.get(org_network_api).json()]

            if not _chunked_network_ids:
                break

            network_id = _chunked_network_ids[-1]
            network_ids.extend(_chunked_network_ids)
        self.logger.info(f"Found {len(network_ids)} networks to attempt to pull devices from.")
        return network_ids

    def _load_records(self, options):
        self.logger.warning(
            f"{__name__.split('.')[1].upper()} has been DEPRECATED, this will be removed in the next major release!!")

        org_id = self.settings.get('org_id', '')
        if org_id:
            for organization_network_device in self.yield_devices_from_network(org_id):
                yield organization_network_device
            for organization_inventory_device in self.yield_inventory_device(org_id):
                yield organization_inventory_device
        else:
            self.logger.warning("No Org_id supplied. Finished running.")

    def load_shim_records(self, _settings):
        org_id                 = _settings.get('org_id')
        starting_after         = _settings.get('starting_after', '')
        network_ids            = _settings.get('network_ids', [])
        is_inventory_collected = _settings.get('is_inventory_collected', False)
        self.settings[self.api_key] = _settings.get(self.api_key)
        chunked_devices = []

        if not is_inventory_collected:
            self.logger.info(f"{self.__class__.__name__}: Syncing the Inventory devices settings")
            chunked_devices, starting_after = self.get_chunked_inventory_devices(org_id, starting_after)
            is_inventory_collected = not chunked_devices

        if is_inventory_collected:
            if not network_ids:
                self.logger.info(f"{self.__class__.__name__}: Fetching all Org Networks")
                network_ids = self.get_all_network_ids(org_id)

            self.logger.info(f"{self.__class__.__name__}: Syncing the Network devices")
            while not chunked_devices and network_ids:
                current_network_id = network_ids[0]
                chunked_devices = self.get_chunked_network_devices(current_network_id)
                network_ids.remove(current_network_id)

        return chunked_devices, starting_after, network_ids, is_inventory_collected

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################
