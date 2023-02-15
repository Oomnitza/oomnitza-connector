import base64

import arrow
from lib.connector import AssetsConnector


class Connector(AssetsConnector):
    """
    WorkspaceOne Device Plus Device Software connector
    """
    MappingName = 'workspaceone_devicesoftware'
    Settings = {
        'client_id': {'order': 1, 'example': '', 'default': ""},
        'client_secret': {'order': 2, 'example': '', 'default': ""},
        'subdomain': {'order': 3, 'example': 'https://<xxxxxx>.awmdm.com the subdomain is between < and >', 'default': ""},
        'region': {'order': 4, 'example': 'na or uat or apac, etc', 'default': ""}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.apps_list_url = 'https://{subdomain}.awmdm.com/api/mam/apps/search?page={page}&pageSize=100'
        self.devices_list_url = 'https://{subdomain}.awmdm.com/api/mdm/devices/search?page={page}&pageSize=100'
        self.devices_per_app_url = 'https://{subdomain}.awmdm.com/api/mam/apps/{app_id}/devices?isinstalled=true'
        self.access_token_url = 'https://{region}.uemauth.vmwservices.com/connect/token'

        self.workspace_one_access_token = ""
        self.workspace_one_expires_in = 0.0

        self.apps_cache_dict = {}
        self.devices_per_app_map = {}

    def get_headers(self):
        if round(arrow.utcnow().float_timestamp) > self.workspace_one_expires_in:
            self.get_access_token(self.settings.get('client_id', ''),
                                  self.settings.get('client_secret', ''),
                                  self.settings.get('region', ''))
        return {'Accept': 'application/json',
                'Authorization': f'Bearer {self.workspace_one_access_token}'}

    def get_access_token(self, client_id, client_secret, region):
        if not client_id or not client_secret or not region:
            return

        # Create the base64 client_id and client_secret token and grab an Access Token
        base64_token = base64.b64encode(':'.encode().join(
            (client_id.encode(), client_secret.encode())
        )).decode()
        token_url = self.access_token_url.format(region=region)

        basic_auth_headers = {
            'Authorization': 'Basic {0}'.format(base64_token),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        json_response = self.post(token_url, data={'grant_type': 'client_credentials'},
                                  headers=basic_auth_headers, post_as_json=False).json()

        self.workspace_one_access_token = json_response.get('access_token', '')
        self.workspace_one_expires_in = round(arrow.utcnow().float_timestamp) + json_response.get('expires_in', 3600)  # expires in 1hr according to docs

    def populate_apps_cache(self, subdomain):
        # First step, grab all the software/apps from workspace one.
        iteration = 0
        while True:
            formatted_url = self.apps_list_url.format(subdomain=subdomain, page=iteration)
            response = self.get(formatted_url)
            if response.status_code != 200:  # WorkspaceOne returns a 204 when there is no more content.
                if iteration == 0:
                    self.logger.info("No software detected for devices.")
                break
            _apps_list = response.json().get('Application', [])

            for _app in _apps_list:
                _app_id_value = ''
                if _app.get('Uuid'):
                    _app_id_value = _app.get('Uuid')

                if _app_id_value:
                    self.apps_cache_dict[_app_id_value] = {'name': _app.get('ApplicationName'), 'version': _app.get('AppVersion')}
            iteration += 1

    def generate_device_app_cache(self, subdomain):
        """ Map the app id to all the devices this app is installed on. """
        for app_id, _ in self.apps_cache_dict.items():
            formatted_url = self.devices_per_app_url.format(subdomain=subdomain, app_id=app_id)
            response = self.get(formatted_url)

            if response.status_code == 200:  # WorkspaceOne returns a 204 when there is no more content.
                app_on_devices = response.json().get('devices', [])
                for device in app_on_devices:
                    device_id = device.get('device_id')
                    if device_id in self.devices_per_app_map:
                        self.devices_per_app_map[device_id].append(app_id)
                    else:
                        self.devices_per_app_map[device_id] = [app_id]

    def yield_devices_with_software(self, subdomain):
        iteration = 0
        while True:
            formatted_url = self.devices_list_url.format(subdomain=subdomain, page=iteration)
            response = self.get(formatted_url)

            if response.status_code != 200:
                break

            devices = response.json().get('Devices', [])
            for device in devices:
                device_id = ""
                if type(device.get('Id')) == dict:
                    device_id = device.get('Id').get('Value')

                device['APPLICATIONS'] = [
                    self.apps_cache_dict.get(app_id)
                    for app_id in self.devices_per_app_map.get(device_id, '')
                    if self.apps_cache_dict and app_id
                ]

                yield device
            iteration += 1

    def _load_records(self, options):
        self.get_access_token(self.settings.get('client_id', ''),
                              self.settings.get('client_secret', ''),
                              self.settings.get('region', ''))
        subdomain = self.settings.get('subdomain', '')
        if subdomain:
            self.populate_apps_cache(subdomain)
            self.generate_device_app_cache(subdomain)
            for device_with_software in self.yield_devices_with_software(subdomain):
                yield device_with_software
        else:
            self.logger.warning("No subdomain supplied. Can not run. Exiting.")
