import logging
from lib.connector import AssetsConnector

logger = logging.getLogger("connectors/meraki_network_devices")  # pylint:disable=invalid-name


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
        self.networks = []
        self.get_networks_api = 'https://api.meraki.com/api/v1/organizations/{id}/networks?' \
                                'perPage=100&startingAfter={network_id}'
        self.get_network_devices_api = 'https://api.meraki.com/api/v1/networks/{id}/devices'
        self.get_inventory_devices_api = 'https://api.meraki.com/api/v1/organizations/{org_id}/inventoryDevices?' \
                                         'perPage=100&startingAfter={serial_number}'

    def get_headers(self):
        return {'X-Cisco-Meraki-API-Key': self.settings['meraki_api_key']}

    def yield_devices_from_network(self, org_id):
        # Build up the network ids first, then grab the devices.
        self.get_all_networks(org_id)

        for network in self.networks:
            network_id = network.get('id', '')  # Check the id exists
            if network_id:
                network_devices_api = self.get_network_devices_api.format(id=network_id)
                network_devices = self.get(network_devices_api).json()

                for network_device in network_devices:
                    yield network_device

    def yield_inventory_device(self, org_id):
        inventory_api = self.get_inventory_devices_api.format(org_id=org_id, serial_number='')
        inventory_devices = self.get(inventory_api).json()

        while inventory_devices:
            next_serial = inventory_devices[-1].get('serial')
            for inventory_device in inventory_devices:
                yield inventory_device
            inventory_api = self.get_inventory_devices_api.format(org_id=org_id, serial_number=next_serial)
            inventory_devices = self.get(inventory_api).json()

    def get_all_networks(self, org_id):
        network_id = ""
        while True:
            org_network_api = self.get_networks_api.format(id=org_id, network_id=network_id)
            networks = self.get(org_network_api).json()

            if not networks:
                break

            network_id = networks[-1]['id']
            self.networks.extend(networks)

    def _load_records(self, options):
        org_id = self.settings.get('org_id', '')
        if org_id:
            for organization_network_device in self.yield_devices_from_network(org_id):
                yield organization_network_device
            for organization_inventory_device in self.yield_inventory_device(org_id):
                yield organization_inventory_device
        else:
            logger.info("No Org_id supplied. Finished running.")
