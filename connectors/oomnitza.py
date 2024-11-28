import pprint
import os

from constants import FATAL_ERROR_FLAG
from lib.connector import AuthenticationError, BaseConnector
from lib.error import ConfigError
from lib.version import VERSION
from requests import RequestException

CSRF_HEADER = "X-CSRF-Token"
CONNECTOR_SOURCE = "X-Connector-Source"


class Connector(BaseConnector):
    Settings = {
        'url':       {'order': 1, 'example': "https://example.oomnitza.com"},
        'api_token': {'order': 2, 'example': "", 'default': ""},
        'username':  {'order': 3, 'example': "oomnitza-sa", 'default': ""},
        'password':  {'order': 4, 'example': "ThePassword", 'default': ""},

    }
    # no FieldMappings for oomnitza connector
    FieldMappings = {}

    def __init__(self, section, settings):
        """Initialize the connector."""
        self._csrf_token = None
        super(Connector, self).__init__(section, settings)
        self.authenticate()

    def _extract_csrf_token(self, response):
        if CSRF_HEADER in response.headers:
            self._csrf_token = response.headers[CSRF_HEADER]

    def get_connector_name(self):
        """ Return connector name to be used for logging. """
        return "connectors/oomnitza"

    def get_field_mappings(self, extra_mappings):
        """ Override base to always return an empty mapping set.
        :param extra_mappings:
        :return: an empty dict()
        """
        return {}

    def get_headers(self):
        if self.settings['api_token']:
            headers = {
                'Content-Type': 'application/json; charset=utf-8', 
                'Authorization2': self.settings['api_token'],
                # TODO - Pass context id to Oomnitza
                # ContextLoggingAdapter.HEADER_CONTEXT_ID: self.context_id
            }
        # these empty headers because of the old implementation of request_token
        # endpoint, body SHOULD NOT be interpreted as JSON here!
        else:
            headers = {}
        if self._csrf_token:
            headers.update({CSRF_HEADER: self._csrf_token})
        if source := os.getenv("OOMNITZA_CONNECTOR_SOURCE"):
            headers.update({CONNECTOR_SOURCE: source})
        return headers

    def authenticate(self):
        if not any((
            self.settings['api_token'],
            self.settings.get('user_pem_file'),
            self.settings['username'] and self.settings['password']
        )):
            raise ConfigError(
                "Oomnitza section needs either: api_token or username & password "
                "or PEM certificate."
            )

        try:
            if self.settings['api_token']:
                response = self.get(
                    "{url}/api/v2/mappings?name=AuthTest".format(**self.settings)
                )
                self._extract_csrf_token(response)
                return

            auth_url = "{url}/api/request_token".format(**self.settings)
            response = self.post(
                auth_url,
                {'login': self.settings['username'],
                 'password': self.settings['password']},
                post_as_json=False,
            )
            self.settings['api_token'] = response.json()["token"]
            self._extract_csrf_token(response)
        except RequestException as exp:
            raise AuthenticationError(str(exp))

    def upload(self, payload):
        url = f"{self.settings['url']}/api/v3/bulk"
        response = self.post(url, payload)
        return response

    def finalize_portion(self, portion_id):
        url = f"{self.settings['url']}/api/v3/bulk/{portion_id}/finalize"
        response = self.post(url, {})
        return response

    def create_synthetic_finalized_successful_portion(self, service_id, correlation_id):
        url = f"{self.settings['url']}/api/v3/bulk/{service_id}/add_ready_portion"
        self.post(url, {'correlation_id': str(correlation_id), 'added': 1})

    def create_synthetic_finalized_failed_portion(
        self,
        service_id,
        correlation_id,
        error,
        multi_str_input_value=None,
        is_fatal=False,
        test_run=False
    ):
        url = f"{self.settings['url']}/api/v3/bulk/{service_id}/add_ready_portion"

        payload = {
            'correlation_id': str(correlation_id),
            'failed': 1,
            'error_message': error,
            'test_run': test_run,
            "multi_str_input_value": multi_str_input_value
        }

        if is_fatal:
            payload['error_type'] = FATAL_ERROR_FLAG

        self.post(url, payload)

    def create_synthetic_finalized_empty_portion(self, service_id, correlation_id, multi_str_input_value=None):
        url = f"{self.settings['url']}/api/v3/bulk/{service_id}/add_ready_portion"

        payload = {
            'correlation_id': str(correlation_id),
            'is_empty_run': True,
            "multi_str_input_value": multi_str_input_value
        }

        self.post(url, payload)

    @staticmethod
    def test_upload(users):
        pprint.pprint(users)

    def perform_sync(self, options):
        """
        Can't call perform_sync on Oomnitza connector because perform_sync in the
        other connectors is what is called to sync to oomnitza. Calling this would
        basically be asking: 'please sync the oomnitza data with oomnitza.'
        """
        raise RuntimeError("Can't call perform_sync on Oomnitza connector.")

    @classmethod
    def example_ini_settings(cls):
        settings = super(Connector, cls).example_ini_settings()
        return settings[1:]

    def get_mappings(self, name):
        url = f"{self.settings['url']}/api/v2/mappings?name={name}"
        response = self.get(url)
        return response.json()

    def get_mappings_for_managed(self, connector_id):
        url = f"{self.settings['url']}/api/v2/mappings?connector_id={connector_id}"
        response = self.get(url)
        return response.json()

    def get_media_storage_files(self, creation_date, source_type, source_id):
        """
        The API endpoint that returns the list of report files is de-facto paginated but because the connector is running every twenty seconds it is OK
        to just fetch the current page and process only it, so the next connector run will process the next page and so on
        """
        url = f"{self.settings['url']}/api/v3/media_storage?filter=" \
              f"(creation_date gt {creation_date}) and " \
              f"(created_by_type eq '{source_type}')" \
              f"&created_by_id={source_id}" \
              f"&sortby=creation_date asc"
        response = self.get(url)
        return response.json()

    def get_location_mappings(self, id_field, label_field):
        try:
            url = "{0}/api/v3/locations".format(self.settings['url'])
            response = self.get(url)
            mappings = {loc[label_field]: loc[id_field] for loc in response.json() if loc.get(id_field, None) and loc.get(label_field, None)}
            
            self.logger.info("Location Map to %s: External Value -> Oomnitza ID", id_field)
            for name in sorted(mappings.keys()):
                self.logger.info("    %s -> %s" % (name, mappings[name]))
                
            return mappings
        except:
            self.logger.exception("Failed to load Locations from Oomnitza.")
            return {}

    def get_settings(self, connector, *keys):
        try:
            url = "{0}/api/v3/settings/{1}/{2}".format(
                self.settings['url'],
                connector,
                '/'.join(keys)
            )
            response = self.get(url)
            return response.json()['value']  ##!!!!!
        except:
            self.logger.exception("Failed to load settings from Oomnitza.")
            raise

    def get_setting(self, key):
        try:
            url = "{0}/api/v3/settings/{1}".format(
                self.settings['url'],
                key
            )
            response = self.get(url)
            return response.json()['value']
        except:
            self.logger.exception("Failed to load setting from Oomnitza.")
            raise

    def check_managed_cloud_configs(self) -> list:
        """
        Check if there is any cloud-managed config in place to be processed within the connector now
        Process
        """
        return self.post(
            f'{self.settings["url"]}/api/v3/bulk/check_managed',
            data={'version': VERSION}
        ).json()

    def get_secret_by_credential_id(
        self,
        credential_id: str,
        url: str,
        http_method: str,
        params: dict,
        headers: dict,
        body: dict,
        **kwargs
    ) -> dict:
        response = self.post(
            f'{self.settings["url"]}/api/v3/auth/{credential_id}/secret',
            data=dict(
                url=url,
                http_method=http_method,
                params=params,
                headers=headers,
                body=body or '',
            )
        )
        response_json = response.json()

        return {
            'headers': response_json.get('headers', {}),
            'params': response_json.get('params', {}),
            'certificates': response_json.get('certificates', {}),
            'url_attributes': response_json.get('url_attributes', {}),
            'body_attributes': response_json.get('body_attributes', {}),
        }

    def get_token_by_token_id(
            self,
            token_id,
    ):
        response = self.get(
            f'{self.settings["url"]}/api/v3/auth/oomnitza_tokens/{token_id}'
        )
        return response.json()['token']

    def get_global_variables_list(self):
        response = self.get(f'{self.settings["url"]}/api/v3/settings/global_variables')
        return response.json()

    def get_credential_details(self, credential_id: str,) -> dict:
        response = self.get(f'{self.settings["url"]}/api/v3/auth/{credential_id}')
        return response.json()

    def get_aws_session_secret(
        self,
        url: str,
        http_method: str,
        params: dict,
        headers: dict,
        body: dict,
        access_key: str,
        secret_key: str,
        session_token: str,
        **kwargs
    ) -> dict:
        response = self.post(
            f'{self.settings["url"]}/api/v3/auth/aws/session/secret',
            data=dict(
                url=url,
                http_method=http_method,
                params=params,
                headers=headers,
                body=body or '',
                access_key=access_key,
                secret_key=secret_key,
                session_token=session_token
            )
        )
        response_json = response.json()

        return {
            'headers': response_json.get('headers', {}),
            'params': response_json.get('params', {}),
            'certificates': response_json.get('certificates', {}),
        }

    def get_portion_info(self, correlation_id: str) -> dict:
        return self.get(
            f'{self.settings["url"]}/api/v3/bulk/{correlation_id}'
        ).json()
