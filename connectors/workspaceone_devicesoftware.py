import base64
import json

import arrow
from lib.connector import AssetsConnector
from lib import TrueValues


class Connector(AssetsConnector):
    """
    WorkspaceOne Device Plus Device Software connector
    """

    scope_type_constants = ["managed", "installed", "all"]
    applications_key = "software"

    MappingName = 'workspaceone_devicesoftware'
    Settings = {
        'client_id': {'order': 1, 'example': '', 'default': ""},
        'client_secret': {'order': 2, 'example': '', 'default': ""},
        'url': {'order': 3, 'example': 'https://{subdomain}.awmdm.com, the url is from https to .com inclusive', 'default': ""},
        'region': {'order': 4, 'example': 'na or uat or apac, etc', 'default': ""},
        'apps_scope': {'order': 5, 'example': ''.join(scope_type_constants), 'default': "all"},
        'ignore_apple': {'order': 6, 'example': 'False', 'default': False},
        'default_versioning': {'order': 7, 'example': 'False', 'default': False},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.managed_apps_list_url = '{url}/api/mam/apps/search?page={page}&pageSize=100'
        self.devices_per_app_url = '{url}/api/mam/apps/{app_id}/devices?isinstalled=true'
        self.apps_per_device_url = '{url}/api/mdm/devices/{deviceUuid}/apps/search?page={page}&pageSize=100'
        self.devices_list_url = '{url}/api/mdm/devices/search?page={page}&pageSize=100'
        self.access_token_url = 'https://{region}.uemauth.vmwservices.com/connect/token'

        self.workspace_one_access_token = ""
        self.workspace_one_expires_in = 0.0

        self.ignore_apple_software = False
        self.apply_default_version = False
        self.default_app_version = "0.0"

        self.apps_cache_dict = {}
        self.devices_per_app_map = {}

        if "APPLICATIONS" not in self.field_mappings:
            self.field_mappings["APPLICATIONS"] = {"source": self.applications_key}

    def _get_utcnow_timestamp(self):
        return round(arrow.utcnow().float_timestamp)

    def get_headers(self):
        if self._get_utcnow_timestamp() > self.workspace_one_expires_in:
            self.get_access_token(self.settings.get('client_id', ''),
                                  self.settings.get('client_secret', ''),
                                  self.settings.get('region', ''))
        return {'Accept': 'application/json',
                'Authorization': f'Bearer {self.workspace_one_access_token}'}

    def get_access_token(self, client_id, client_secret, region):
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
        expires_in = json_response.get('expires_in', 3600)

        # expires in 1hr according to docs, reduced by 5 minutes so we don't hit the edge case of an api call on the hour mark.
        expires_in_time = expires_in - 300 if expires_in > 600 else expires_in
        self.workspace_one_expires_in = self._get_utcnow_timestamp() + expires_in_time

    def populate_apps_cache(self, url):
        # First step, grab all the software/apps from workspace one.
        iteration = 0
        self.logger.info("Generating the Managed Applications cache.")
        while True:
            formatted_url = self.managed_apps_list_url.format(url=url, page=iteration)
            response = self.get(formatted_url)
            status_code = response.status_code

            if not self._check_response_status(status_code, msg=f"Failed to fetch Software with {status_code} reason: '{response.reason}'"):
                if iteration == 0:
                    self.logger.info("No Software detected for any devices.")
                self.logger.info("Finished Fetching Software for devices.")
                break

            _apps_list = self._convert_to_json(response, formatted_url).get('Application', [])

            for _app in _apps_list:
                if _app_id_value := _app.get('Uuid', ''):

                    _app_version = _app.get('AppVersion', '')
                    if self.apply_default_version and not _app_version:
                        _app_version = self.default_app_version

                    if self.ignore_apple_software and "com.apple." in _app.get('BundleId', ''):
                        continue

                    self.apps_cache_dict[_app_id_value] = {'name': _app.get('ApplicationName', ''),
                                                           'version': _app_version,
                                                           'bundle_id': _app.get('BundleId', ''),
                                                           'path': None  # < -- to keep compatibility
                                                           }
                else:
                    self.logger.info(f"No Software ID found for App Name: '{_app.get('ApplicationName')}'")
            iteration += 1

    def generate_device_app_cache(self, url):
        """ Map the app id to all the devices this app is installed on. """
        self.logger.info("Generating the device app cache.")

        for app_id, _ in self.apps_cache_dict.items():
            formatted_url = self.devices_per_app_url.format(url=url, app_id=app_id)
            response = self.get(formatted_url)
            status_code = response.status_code

            if not self._check_response_status(status_code, msg=f"Failed to fetch Devices for Software with {status_code} reason: '{response.reason}'"):
                self.logger.info(f"Finished Fetching Devices for software {app_id}.")
                continue

            app_on_devices = self._convert_to_json(response, formatted_url).get('devices', [])
            for device in app_on_devices:
                device_uuid = device.get('device_uuid')
                if device_uuid in self.devices_per_app_map:
                    self.devices_per_app_map[device_uuid].append(app_id)
                else:
                    self.devices_per_app_map[device_uuid] = [app_id]

    def _check_response_status(self, response_status: int, msg: str = "") -> bool:
        # WorkspaceOne returns a 204 when there is no more content.
        # Except for this url '/api/mdm/devices/{deviceUuid}/apps/search?page={page}&pageSize=100' it returns a 200 Ok.
        if response_status == 204:
            return False
        elif response_status != 200:
            self.logger.warning(msg)
            return False
        return True

    def get_installed_apps(self, url, device_uuid):
        iteration = 0
        installed_apps = []
        self.logger.info(f"Gathering installed apps for device: {device_uuid}")

        while True:
            formatted_url = self.apps_per_device_url.format(url=url, deviceUuid=device_uuid, page=iteration)
            response = self.get(formatted_url)
            status_code = response.status_code

            if not self._check_response_status(status_code,
                                               msg=f"Failed to fetch Installed Apps on Device '{device_uuid}', with {status_code} reason: '{response.reason}'"):
                self.logger.info(f"Finished fetching Installed Software for {device_uuid}.")
                break

            unmanaged_software = self._convert_to_json(response, formatted_url).get('app_items', [])

            if not unmanaged_software:
                self.logger.info(f"No more Installed Software detected for {device_uuid}.")
                break

            for app in unmanaged_software:
                if self.ignore_apple_software:
                    if "com.apple." in app.get('bundle_id', ''):
                        continue

                app_version = app.get('installed_version', '')
                if self.apply_default_version and not app_version:
                    app_version = self.default_app_version

                installed_apps.append({
                    "version": app_version,
                    "name": app.get('name', ''),
                    "bundle_id": app.get('bundle_id', ''),
                    "path": None  # < -- to keep compatibility
                })

            iteration += 1

        return installed_apps

    def yield_devices_with_managed_software(self, url):
        iteration = 0
        while True:
            formatted_url = self.devices_list_url.format(url=url, page=iteration)
            response = self.get(formatted_url)
            status_code = response.status_code

            if not self._check_response_status(status_code,
                                               msg=f"Failed to fetch Devices with {status_code} reason: '{response.reason}'"):
                self.logger.info(f"Finished Fetching Devices.")
                break

            devices = self._convert_to_json(response, formatted_url).get('Devices', [])
            if not devices:
                self.logger.warning(f"Devices list call was empty. Exiting")

            for device in devices:
                if type(device.get('Uuid')) == dict:
                    device_uuid = device.get('Uuid').get('Value')
                else:
                    device_uuid = device.get('Uuid')

                device[self.applications_key] = [
                    self.apps_cache_dict.get(app_id)
                    for app_id in self.devices_per_app_map.get(device_uuid, '')
                    if self.apps_cache_dict and app_id
                ]

                yield device
            iteration += 1

    def yield_devices_with_installed_software(self, url):
        iteration = 0
        while True:
            formatted_url = self.devices_list_url.format(url=url, page=iteration)
            response = self.get(formatted_url)
            status_code = response.status_code

            if not self._check_response_status(status_code,
                                               msg=f"Failed to fetch Devices with {status_code} reason: '{response.reason}'"):
                self.logger.info(f"Finished Fetching Devices.")
                break

            devices = self._convert_to_json(response, formatted_url).get('Devices', [])
            for device in devices:
                device_id = ""
                if type(device.get('Id')) == dict:
                    device_id = device.get('Id').get('Value')

                device[self.applications_key] = self.get_installed_apps(url, device_id)

                yield device
            iteration += 1

    def yield_devices_with_all_software(self, url):
        for device in self.yield_devices_with_managed_software(url):
            if type(device.get('Uuid')) == dict:
                device_uuid = device.get('Id').get('Value')
            else:
                device_uuid = device.get('Uuid')

            if not device_uuid:
                self.logger.info(f"Finished Fetching Unmanaged Software.")
                continue

            device[self.applications_key].extend(self.get_installed_apps(url, device_uuid))

            yield device

    def alter_software(self, device: dict):
        if self.applications_key in device and device[self.applications_key]:

            for index, software in enumerate(device[self.applications_key]):
                self.logger.warning(f"what {index} {self.ignore_apple_software and 'com.apple' in software['bundle_id']}")
                if self.ignore_apple_software and "com.apple" in software['bundle_id']:
                    del device[self.applications_key][index]

                if self.apply_default_version and not software['version']:
                    software['version'] = self.default_app_version

        return device

    def _convert_to_json(self, response, url):
        try:
            response_json = response.json()
            return response_json
        except json.JSONDecodeError:
            self.logger.warning(f"Failed to convert response to json for {url}")
        return {}

    def _are_cred_inputs_ok(self) -> bool:
        if not all((self.settings.get('client_id', ''), self.settings.get('client_secret', ''),
                    self.settings.get('region', ''))):
            self.logger.warning("Missing client_id, client_secret and/or region. Can not run. Exiting")
            return False
        return True

    def _is_url_input_ok(self, url: str) -> bool:
        if not url and ("http://" not in url or "https://" not in url):
            self.logger.warning("No URL supplied. URL input requires 'https://<subdomain>.awmdm.com' "
                                "including 'https://' and 'top level domain i.e. '.com'. Can not run. Exiting.")
            return False
        return True

    def _is_app_scope_input_ok(self, apps_scope: str) -> bool:
        if apps_scope not in self.scope_type_constants:
            self.logger.warning(f"'{apps_scope}' is not a valid option please use any of:"
                                f" {''.join(self.scope_type_constants)}. Exiting.")
            return False
        return True

    def _generate_caches(self, url):
        self.populate_apps_cache(url)
        self.generate_device_app_cache(url)

    def _load_records(self, options):
        self.ignore_apple_software = self.settings.get('ignore_apple', False) in TrueValues
        self.apply_default_version = self.settings.get('default_versioning', False) in TrueValues
        apps_scope = self.settings.get('apps_scope', '').lower()
        url = self.settings.get('url', '').strip('/')

        if not self._are_cred_inputs_ok() and not self._is_app_scope_input_ok(apps_scope) and not self._is_url_input_ok(url):
            return

        self.get_access_token(self.settings.get('client_id', ''),
                              self.settings.get('client_secret', ''),
                              self.settings.get('region', ''))

        if not self.workspace_one_access_token:
            self.logger.warning("No access token returned. Further processing is not possible. Exiting.")
            return

        # Determine the fetch method.
        if apps_scope == 'managed' or apps_scope == 'all':
            self._generate_caches(url)

            if apps_scope == 'all':
                # Yield devices with both installed and managed apps too
                for device_all_software in self.yield_devices_with_all_software(url):
                    yield device_all_software

            else:
                # Yield devices with just the managed apps
                for device_managed_software in self.yield_devices_with_managed_software(url):
                    yield device_managed_software
        else:
            # Yield devices with only apps installed on the device (non managed and some managed)
            for device_installed_software in self.yield_devices_with_installed_software(url):
                yield device_installed_software
