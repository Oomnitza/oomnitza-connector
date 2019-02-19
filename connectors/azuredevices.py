from lib.connector import AuditConnector
from lib.ext.graph import GraphAPIResourceFetcher


class Connector(AuditConnector):
    MappingName = 'Azuredevices'
    Settings = {
        'tenant_id':        {'order': 1, 'example': '', 'default': ""},
        'client_id':        {'order': 2, 'example': "", 'default': ''},
        'secret':           {'order': 3, 'example': "", 'default': ''},
        'sync_field':       {'order': 4, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.graph_api = GraphAPIResourceFetcher()

    def get_headers(self):
        return self.graph_api.get_headers(
            self.settings['tenant_id'],
            self.settings['client_id'],
            self.settings['secret']
        )

    def _load_records(self, options):

        users = self.graph_api.pagination_wrapper(self.get, 'users')
        for user in users:
            owned_devices = self.graph_api.pagination_wrapper(self.get, 'users/{userid}/ownedDevices'.format(userid=user['id']))
            for owned_device in owned_devices:
                yield owned_device
