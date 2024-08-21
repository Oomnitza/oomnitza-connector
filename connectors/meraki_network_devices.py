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
        'authorization_settings': {'order': 3, 'default': {}}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.api_key = 'X-Cisco-Meraki-API-Key'
        self.get_networks_api = 'https://api.meraki.com/api/v1/organizations/{id}/networks?' \
                                'perPage=100&startingAfter={network_id}'
        self.get_network_devices_api = 'https://api.meraki.com/api/v1/networks/{id}/devices'
        self.get_inventory_devices_api = 'https://api.meraki.com/api/v1/organizations/{org_id}/inventoryDevices?' \
                                         'perPage=100&startingAfter={serial_number}'
        self.authorization_settings = self.settings.get('authorization_settings')

    def get_headers(self):
        api_token = None
        if self.authorization_settings.get(self.api_key):
            api_token = self.authorization_settings.get(self.api_key)
        elif self.settings['meraki_api_key']:
            api_token = self.settings['meraki_api_key']
        else:
            self.logger.warning("Missing API Key and/or Authorization. Can not continue")
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

    def load_cloud_records(self, credential_details):
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

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################
