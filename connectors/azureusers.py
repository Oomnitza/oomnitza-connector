from azure.common.credentials import ServicePrincipalCredentials
from azure.graphrbac import GraphRbacManagementClient

from lib.connector import UserConnector

AUTH_RESOURCE = "https://graph.windows.net"


class Connector(UserConnector):
    MappingName = 'Azureusers'
    Settings = {
        'tenant_id':        {'order': 1, 'example': '', 'default': ""},
        'client_id':        {'order': 2, 'example': "", 'default': ''},
        'secret':           {'order': 3, 'example': "", 'default': ''},
        'default_role':     {'order': 4, 'example': 25, 'type': int},
        'default_position': {'order': 5, 'example': 'Employee'},
        'sync_field':       {'order': 6, 'default': 'USER'}
    }

    FieldMappings = {
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    def _load_records(self, options):

        tenant_id = self.settings['tenant_id']
        client_id = self.settings['client_id']
        secret = self.settings['secret']

        credentials = ServicePrincipalCredentials(
            client_id=client_id,
            secret=secret,
            tenant=tenant_id,
            resource=AUTH_RESOURCE
        )

        graphrbac_client = GraphRbacManagementClient(
            credentials,
            tenant_id
        )

        for user in graphrbac_client.users.list():
            yield user.__dict__
