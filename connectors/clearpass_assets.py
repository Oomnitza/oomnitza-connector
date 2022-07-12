from __future__ import absolute_import

import sys
import os
import logging
import logging.handlers as logging_handlers
import json
from lib.connector import AssetsConnector
from lib.error import ConfigError
from converters import mac_address_converter
import requests
import netaddr

LOGGER = logging.getLogger(__name__)  # pylint:disable=invalid-name
AUTH_TOKEN_GENERATE_MSG = "No auth token found, attempting to generate"
JSON_REQUEST_HEADER = "application/json"


# Logs URL: https://<subdomain>.oomnitza.com/api/v3/connector_run_logs/connector_clearpass_assets/
def json_validator(value):
    try:
        return json.loads(value)
    except ValueError:
        raise ConfigError('setting is incorrect json expected but %r found' % value)


def authenticate_vault():
    return "Not implemented"


class Connector(AssetsConnector):
    MappingName = 'Clearpass_Assets'
    Settings = {
        'api_url': {'order': 1, 'example': "https://aruba-cp-p.example.com/api/",
                    'default': "https://aruba-cp-p.example.com/api/"},
        'client_id': {'order': 2, 'example': 'ammDVpAi0xry3KIMpemeBGejwmAnzZUrZFc9KXhv',
                      'default': ""},
        'client_secret': {'order': 3, 'example': 'FQoGZXIvYXdzEIT//////////', 'default': ""},
        'sync_field': {'order': 5, 'example': '5A22F8E992574C4099AA16CFE4C092C9'},
        'asset_type': {'order': 6, 'example': "Laptop", 'default': "Laptop"},
    }

    FieldMappings_v3 = {
        "serial_number": {'source': 'device_serial'},
        "clearpass_id": {'source': 'id'},
        "asset_type": {'source': 'asset_type'},
        "clearpass_status": {'source': 'status'},
        "clearpass_usernames": {'source': 'usernames'},
        "clearpass_device_identifier": {'source': 'device_identifier'},
        "clearpass_mac_address": {'source': 'mac_address'},
    }

    FieldMappings = FieldMappings_v3

    def __init__(self, section, settings):
        LOGGER.debug("Setting up connector %s", __name__)
        super(Connector, self).__init__(section, settings)

        self.authenticate()

    def authenticate(self):
        LOGGER.info("Authenticating to %s", self.settings.get('api_url'))
        LOGGER.debug("Attempting authentication with the following:")
        LOGGER.debug("Token: %s", self.settings.get('token'))
        LOGGER.debug("Secret Key: %s", self.settings.get('secret_key'))
        LOGGER.debug("URL: %s", self.settings.get('api_url'))
        self.clearpass_client = ClearpassInterface(client_id=self.settings.get('client_id'),
                                                   client_secret=self.settings.get('client_secret'),
                                                   clearpass_base_url=self.settings.get('api_url'))
        self.devices = self.clearpass_client.list_devices()

    def do_test_connection(self, options):
        return True

    def _load_records(self, options):
        LOGGER.info("Loading records from Clearpass")
        if not self.do_test_connection(options=options):
            LOGGER.fatal("Unable to connect to Clearpass. Probably a credentials problem.")
            sys.exit(1)
        if not self.devices:
            try:
                self.devices = self.clearpass_client.list_devices()
            except Exception as e:
                self.devices = []
                LOGGER.error("Error listing devices from Clearpass.", exc_info=True)

        if hasattr(self, 'devices') and not isinstance(self.devices, list):
            LOGGER.error("Invalid response from Clearpass")
            LOGGER.fatal(self.devices)
            sys.exit(1)

        # This is to prevent flip flops where the serial number shows up in clearpass more than once.
        # TODO: Flag or report there is a dupe serial number/entry in clearpass.
        devices_by_serial = {
            device['device_serial']: device for device in self.devices if
            device.get('device_serial', False)
        }

        for serial, device in devices_by_serial.items():
            if not serial:
                LOGGER.error("Unable to find device serial for clearpass device %s",
                             device.get('id'))
                LOGGER.debug("Device info: %s", device)
                continue

            formatted_device = self._fetch_custom(device)

            LOGGER.info("Updating %s clearpass data.", serial)
            yield formatted_device

    def _fetch_custom(self, clearpass_entry):
        # Concat MACs and
        mac_address = clearpass_entry.get('mac_address', None)
        if mac_address and isinstance(mac_address, list):
            output = []
            for mac_addr in mac_address:
                formatted_mac = mac_address_converter.converter(mac_addr,
                                                                integration_name=self.MappingName)
                if formatted_mac:
                    output.append(formatted_mac)
            clearpass_entry['mac_address'] = ','.join(output).upper().rstrip(',')
        else:
            clearpass_entry['mac_address'] = mac_address_converter.converter(
                clearpass_entry['mac_address'].upper(), integration_name=self.MappingName)

        asset_type = clearpass_entry.get('product_name')
        if asset_type and isinstance(asset_type, str) and 'iPad' in asset_type:
            clearpass_entry['asset_type'] = "Tablet"
        else:  # default to laptop
            clearpass_entry['asset_type'] = "Laptop"
        return clearpass_entry

    def _fetch_certs(self, clearpass_entry):
        clearpass_id = clearpass_entry.get('id')
        device_certs = self.clearpass_client.get_cert(clearpass_id)
        clearpass_entry['certs'] = device_certs
        return clearpass_entry


LOGGING_LEVEL = logging.INFO


def set_logger():
    logger.setLevel(LOGGING_LEVEL)

    # create console handler and set level to debug
    console_handlder = logging.StreamHandler()
    console_handlder.setLevel(LOGGING_LEVEL)

    # create formatter
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(processName)s:[%(process)d] | %(name)s.%(funcName)s: %("
        "message)s')")

    # add formatter to ch
    console_handlder.setFormatter(formatter)

    # add ch to LOGGER
    logger.addHandler(console_handlder)


def parse_mac(mac):
    """
    Parses the MAC address and converts to common format
    :param mac: Unparsed MAC Address in string format
    :return: If it succeeds returns parsed MAC with proper formatting in string format
    else if the MAC is unrecognized (usually when not a MAC) returns None
    """
    try:  # checks common MAC formatting and converts it to uppercase MAC address
        mac = netaddr.EUI(mac.replace(' ', ''))  # removes spaces
        mac.dialect = netaddr.mac_unix_expanded  # converts different MAC formats to XX:XX:XX:XX:XX:XX
        return str(mac).upper()  # converts mac to string and letters to upper case
    except (AttributeError,
            netaddr.AddrFormatError):  # if MAC not in common format or MAC is blank set MAC to NULL
        logger.error("Invalid MAC address format %s", mac, exc_info=True)
        return mac


class ClearpassInterface(object):
    """
    Class to interact with Aruba API.
    """

    def __init__(self, **kwargs):
        """
        Initializes the class with required credientials to get bearer certificate from aruba
        :param username: string
        :param password: string
        """
        global logger
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(processName)s:[%(process)d] | %(name)s.%(funcName)s:%(lineno)d %(message)s"
        )
        if kwargs.get("save_log", False):
            file_handler = logging_handlers.RotatingFileHandler(
                filename="anet-clearpass.log",
                mode="a",
                encoding="utf-8",
                maxBytes=10485760,
                backupCount=5,
            )
            file_handler.setFormatter(formatter)

            logger.addHandler(file_handler)

        else:
            set_logger()

        logger.info("Creating Clearpass Interface")
        self.username = kwargs.get('username', os.environ.get('CLEARPASS_USERNAME', None))
        logger.debug("Username: {}".format(self.username))
        self.password = kwargs.get('password', os.environ.get('CLEARPASS_PASSWD', None))
        logger.debug("Password: {}".format(self.password))

        self.client_id = kwargs.get('client_id', os.environ.get('CLEARPASS_CLIENT_ID', None))
        logger.debug("Client ID: {}".format(self.client_id))

        self.client_secret = kwargs.get('client_secret',
                                        os.environ.get('CLEARPASS_CLIENT_SECRET', None))
        logger.debug("Client Secret: {}".format(self.client_secret))

        self.clearpass_base_url = kwargs.get('clearpass_base_url',
                                             os.environ.get('CLEARPASS_BASE_URL', None))
        logger.debug("Base URL: {}".format(self.clearpass_base_url))

        self.main_host_url = self.clearpass_base_url + 'static-host-list/' + os.environ.get(
            'CLEARPASS_STATIC_HOST_LIST', '')

        logger.debug("Main URL: {}".format(self.main_host_url))

        self.auth_type = kwargs.get('auth_type', "client_credentials")
        logger.debug("Auth type: {}".format(self.auth_type))

        self.refresh_token = kwargs.get('refresh_token',
                                        os.environ.get('CLEARPASS_REFRESH_TOKEN', None))
        logger.debug("Refresh token: {}".format(self.refresh_token))

        self.access_token = kwargs.get('access_token', os.environ.get('CLEARPASS_AUTH_TOKEN', None))
        logger.debug("Access token: {}".format(self.access_token))

        self.forbidden_count = 0
        self.request_limit = 1000
        self.request_params = {}
        self.request_headers = {}

        self._init_request()

    def _init_request(self):
        if not self.access_token:
            logger.debug(AUTH_TOKEN_GENERATE_MSG)
            self._get_bearer()

        params = {
            'sort': 'id',
            'limit': self.request_limit,
        }
        self.request_headers = {
            'Content-Type': JSON_REQUEST_HEADER,
            'Authorization': f'Bearer {self.access_token}',
        }
        logger.debug("Headers: %s", self.request_headers)

    def get_auth_token(self):
        if not self.access_token:
            self._get_bearer()
        return {"token": self.access_token}

    def _get_bearer(self, refresh_token=None, **kwargs):
        """
        Get Bearer certificate which will be used to communicate with Aruba
        :return: Bearer token in string format
        """

        auth_type = kwargs.get('auth_type', self.auth_type)
        logger.debug("Authenticating to clearpass via {}".format(auth_type))
        if not refresh_token:
            logger.debug("Not a refresh token")
            data = {
                'grant_type': auth_type,
                'username': self.username,
                'client_id': self.client_id
            }
            if auth_type == "password":
                data['password'] = self.password
            else:
                data['client_secret'] = self.client_secret
        else:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }

        logger.debug("Request payload: {}".format(data))
        try:
            api_scope = kwargs.get("api_scope", "oauth")
            auth_url = self.clearpass_base_url + api_scope
            logger.debug("Getting bearer token from {}".format(auth_url))
            response = requests.post(auth_url, json=data, verify=True)
            logger.debug('Response code %s', response.status_code)
            if response.status_code != 200:
                try:
                    logger.error(response.text)
                except Exception as e:
                    logger.error(e, exc_info=True)
                    pass
            elif response.status_code == 200:
                logger.debug("Auth success.")
                data = response.json()
                logger.debug(f"Response: {data}")
                self.refresh_token = data.get('refresh_token', None)
                self.access_token = data.get('access_token', None)
                return data
        except Exception as e:
            logger.error("Unknown error", exc_info=True)

    def get_user(self, **kwargs):
        logger.debug("Get user: {}".format(kwargs))
        clearpass_id = kwargs.get('clearpass_id', None)
        if not clearpass_id:
            return {"error": "Invalid request; must provide clearpass identifer as parameter."}

        try:
            clearpass_id = int(clearpass_id)
            return self.get(api_scope='user/{id}'.format(id=clearpass_id),
                            clearpass_id=clearpass_id)
        except ValueError:
            query_filter = kwargs.get('filter', None)
            if query_filter:
                return self.get(api_scope='user', filter=query_filter)
            else:
                if clearpass_id:
                    query_filter = json.dumps({"username": clearpass_id})
                    return self.get(api_scope='user', filter=query_filter)
                return {
                    "error": "Invalid request, must provide filter in JSON format. ex. \"{\"username\":\"mjtest\"}\""}
        return {"error": "Invalid request. Must provide clearpass ID or username + JSON filter."}

    def get_cert(self, **kwargs):

        clearpass_id = kwargs.get('clearpass_id', None)

        if not clearpass_id:
            return {"error": "Invalid request; must provide clearpass identifer as parameter."}
        logger.debug("Get cert: {}".format(clearpass_id))
        try:
            clearpass_id = int(clearpass_id)
            return self.get(api_scope='certificate/{id}'.format(id=clearpass_id),
                            clearpass_id=clearpass_id)
        except ValueError:
            query_filter = kwargs.get('filter', None)
            if query_filter:
                return self.get(api_scope='certificate', filter=query_filter)
            else:
                if clearpass_id:
                    query_filter = json.dumps({"subject_common_name": clearpass_id})
                    return self.get(api_scope='certificate', filter=query_filter)
                return {
                    "error": "Invalid request, must provide filter in JSON format. ex. \"{\"username\":\"mjtest\"}\""}

    def get_device(self, clearpass_id, api_scope="onboard/device"):
        logger.debug("Get device: {}".format(clearpass_id))
        return self.get(api_scope="{scope}/{id}".format(scope=api_scope, id=clearpass_id),
                        clearpass_id=clearpass_id)

    def list_users(self, **kwargs):
        return self.list(api_scope="user", **kwargs)

    def get(self, api_scope, **kwargs):
        if not self.access_token:
            logger.debug(AUTH_TOKEN_GENERATE_MSG)
            self._get_bearer()

        headers = {
            'Content-Type': JSON_REQUEST_HEADER,
            'Authorization': 'Bearer {}'.format(self.access_token)
        }
        logger.debug("Headers: {}".format(headers))
        params = {
            'sort': '+id',
            'calculate_count': 1
        }
        query_filter = kwargs.get('filter', None)
        if query_filter:
            params['filter'] = query_filter

        try:
            request_url = kwargs.get('url', self.clearpass_base_url) + api_scope
            logger.info("Pulling data from {}".format(request_url))
            response = requests.get(request_url, headers=headers, params=params, verify=True)
            response_data = response.json()
            logger.debug("Response: {}".format(response.json()))
            logger.info("{results_count} results returned for GET {url}{params}".format(
                results_count=response_data.get('count', 0), url=request_url, params=params))
            return response_data
        except Exception as e:
            return None

    def list(self, api_scope, output, offset=0, limit=1000, **kwargs):
        if not self.access_token:
            logger.debug(AUTH_TOKEN_GENERATE_MSG)
            self._get_bearer()

        params = {
            'sort': 'id',
            'limit': limit,
            'calculate_count': 1
        }
        query_filter = kwargs.get('filter', None)
        if query_filter:
            params['filter'] = query_filter
        headers = {
            'Content-Type': JSON_REQUEST_HEADER,
            'Authorization': 'Bearer {}'.format(self.access_token)
        }
        logger.debug("Headers: {}".format(headers))

        try:
            request_url = kwargs.get('url', self.clearpass_base_url) + api_scope
            logger.info("Pulling data from {}".format(request_url))
            has_next = True
            while has_next:
                logger.debug("Processing next page...")
                response = requests.get(request_url, headers=headers, params=params, verify=True)
                response_data = response.json()
                logger.debug("Response: {}".format(response.json()))

                urls = response_data.get('_links', None)
                if urls:
                    next_url_obj = urls.get('next', None)
                    if not next_url_obj:
                        has_next = False
                    else:
                        request_url = next_url_obj.get('href')
                    logger.debug("Next URL: {}".format(request_url))
                else:
                    request_url = None
                    logger.info("No more records to process")
                    has_next = False

                if response.status_code == 403:
                    self.forbidden_count += 1
                    if self.forbidden_count < 3:
                        logging.info("Got 403. Attempting re-authenticate and token refresh...")
                        self._get_bearer(refresh_token=self.refresh_token)
                        self.list(api_scope=api_scope, output=output, offset=offset, **kwargs)
                    else:
                        has_next = False
                        raise requests.exceptions.AuthenticationException("Access denied")

                if response.status_code == 200:
                    data = response.json()
                    logger.debug("Pull success")
                    logger.debug("Response: {}".format(response.json))
                    if len(data['_embedded']['items']) > 0:
                        output.extend(data['_embedded']['items'])
            return output
        except Exception as e:
            logger.error("Unknown error", exc_info=True)

    def list_devices(self, **kwargs):
        get_guest_devices = kwargs.get("guest_devices", False)
        get_all_devices = kwargs.get("all_devices", False)
        if get_all_devices:
            logger.info("Listing ALL devices")
            guest_devices = self.list(api_scope="device")
            onboarded_devices = self.list(api_scope="onboard/device")
            return {"guest_devices": guest_devices, "onboarded_devices": onboarded_devices}
        elif get_guest_devices:
            logger.info("Listing GUEST devices")
            return self.list(api_scope="device")
        logger.info("Listing ONBOARD devices")
        return self.list(api_scope="onboard/device")

    def _make_host_lists(self, value, mac_type):
        """
        makes a new static_host_list - used if wired/wifi lists are not present
        :param value:
        :param mac_type:
        :return:
        """
        value = ",".join(value)
        response = requests.post(self.clearpass_base_url + '/static-host-list',
                                 headers=self.request_header, verify=True, json={
                'name': mac_type, 'host_format': 'list', 'host_type': 'MACAddress', 'value': value
            }).json()
        return response

    def _get_api_token(self, client_id, client_secret):
        """
        gets api token from secret
        :param client_secret:
        :return:
        """
        logger.debug('getting access token')
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        headers = {
            "content-type": "application/json",
        }

        response = requests.post(self.oauth_url, json=payload, headers=headers, verify=True).json()
        if response.get('status') == 400:
            logger.error('failed to get access token - error: %s', response)
        else:
            logger.debug('got access token for clearpass')

        return response.get('access_token')
