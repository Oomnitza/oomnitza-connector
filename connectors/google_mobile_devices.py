import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from lib.connector import AssetsConnector

GOOGLEMDM_API_SCOPE = (
    'https://www.googleapis.com/auth/admin.directory.device.mobile.readonly',
)


class Connector(AssetsConnector):
    MappingName = 'GoogleMobileDevices'

    Settings = {
        'service_account_impersonate': {'order': 1, 'example': "username@example.com", 'default': ''},
        'service_account_json_key': {'order': 2, 'example': '{}', 'default': '{}'},
    }
    DefaultConverters = {
    }

    def get_sa_credentials(self):
        """
        Build and return an Admin SDK Directory service object authorized with the service accounts
        that act on behalf of the given G Suite Admin user.
        """
        impersonated_user = self.settings.get('service_account_impersonate')
        service_account_json_key = json.loads(self.settings.get('service_account_json_key', '{}'))

        if impersonated_user and service_account_json_key:
            return service_account.Credentials.from_service_account_info(
                service_account_json_key,
                scopes=GOOGLEMDM_API_SCOPE,
                subject=impersonated_user
            )

    def _load_records(self, options):
        credentials = self.get_sa_credentials()
        if credentials is None:
            self.logger.error("Set the email of the G Suite administrator and service account's json key")
            raise StopIteration

        api_client = build('admin', 'directory_v1', credentials=credentials, cache_discovery=False)

        self.logger.info("Getting user list")
        mobiledevices = api_client.mobiledevices()
        request = mobiledevices.list(customerId='my_customer', projection='FULL')

        while request is not None:
            records = request.execute()

            for device_record in records.get('mobiledevices', []):
                yield device_record

            request = mobiledevices.list_next(request, records)
