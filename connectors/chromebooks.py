import json
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build

from lib.connector import AuditConnector

LOG = logging.getLogger("connectors/chromebooks")  # pylint:disable=invalid-name


CHROMEDEVICES_API_SCOPE = (
    'https://www.googleapis.com/auth/admin.directory.device.chromeos.readonly',
)


class Connector(AuditConnector):
    MappingName = 'Chromebooks'

    Settings = {
        'service_account_impersonate':  {'order': 1, 'example': "username@example.com", 'default': ''},
        'service_account_json_key':     {'order': 2, 'example': '{}', 'default': '{}'},
        'sync_field':                   {'order': 3, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }
    DefaultConverters = {
    }

    def get_sa_credentials(self):
        """
        Build and returns an Admin SDK Directory service object authorized with the service accounts
        that act on behalf of the given G Suite Admin user.
        
        :return: 
        """
        sa_credentials = None

        impersonated_user = self.settings.get('service_account_impersonate')
        service_account_json_key = json.loads(self.settings.get('service_account_json_key', '{}'))
        if all((impersonated_user, service_account_json_key)):

            sa_credentials = service_account.Credentials.from_service_account_info(
                service_account_json_key,
                scopes=CHROMEDEVICES_API_SCOPE,
                subject=impersonated_user
            )

        return sa_credentials

    def _load_records(self, options):
        credentials = self.get_sa_credentials()
        if not credentials:
            LOG.error("Set the email of the G Suite administrator and service account's json key")
            raise StopIteration

        api_client = build('admin', 'directory_v1', credentials=credentials, cache_discovery=False)

        chromeosdevices = api_client.chromeosdevices()
        request = chromeosdevices.list(customerId='my_customer', projection='FULL')

        while request is not None:
            records = request.execute()

            for device_record in records.get('chromeosdevices', []):
                yield device_record

            request = chromeosdevices.list_next(request, records)
