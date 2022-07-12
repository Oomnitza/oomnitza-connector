from __future__ import absolute_import

import binascii
import datetime
import hashlib
import hmac
import time
import sys

import logging
import json
import requests
from lib.connector import AssetsConnector
from lib.error import ConfigError
import os
from converters import empty_key_remover

LOGGER = logging.getLogger(__name__)  # pylint:disable=invalid-name
OOMNITZA_SUBDOMAIN = "example"

# Logs URL: https://<subdomain>.oomnitza.com/api/v3/connector_run_logs/connector_crowdstrike_assets/


def json_validator(value):
    try:
        return json.loads(value)
    except ValueError:
        raise ConfigError('setting is incorrect json expected but %r found' % value)


def check_drivestrike_encryption(hardware_info):
    if hardware_info == {}:
        return None
    drive_info = [value for key, value in hardware_info.items() if 'Fixed Drive' in key]
    if not drive_info:
        if 'Is Device Encrypted' in hardware_info.keys():
            return hardware_info['Is Device Encrypted']
        else:
            return None
    if 'BitLocker Status' in drive_info[0].keys():
        return list(drive_info[0]['BitLocker Status'])[0]
    return 'Not Encrypted'


class Connector(AssetsConnector):
    MappingName = 'Drivestrike_Assets'
    Settings = {
        'api_url': {'order': 1, 'example': "",
                    'default': "https://app.drivestrike.com/api/devices"},
        'username': {'order': 2, 'example': 'user', 'default': ""},
        'password': {'order': 3, 'example': 'FQoGZXIvYXdzEITTTXX', 'default': ""},
        'sync_field': {'order': 5, 'example': '5A22F8E992574C4099AA16CFE4C092C9',
                       'default': "drivestrike_serial_number"},
        'asset_type': {'order': 6, 'example': "Laptop", 'default': "Laptop"},
    }


    FieldMappings_v3 = {
        "drivestrike_id": {'source': 'device_id'},
        "drivestrike_status_last_updated": {'source': 'statusUpdated'},
        "drivestrike_os": {'source': 'os'},
        "drivestrike_os_version": {'source': 'osVersion'},
        "drivestrike_hostname": {'source': 'DNS Host Name'},
        "drivestrike_last_seen": {'source': 'lastSeen'},
        "drivestrike_encryption_status": {'source': 'Is Device Encrypted'},
        "drivestrike_manufacturer": {'source': 'Manufacturer'},
        "drivestrike_model": {'source': 'Model'},
        "drivestrike_serial_number": {'source': 'BIOS Serial Number'},
        "serial_number": {'source': 'BIOS Serial Number'},
    }

    FieldMappings = FieldMappings_v3

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)

        # self.authenticate_vault()

        self.__init_oomnitza_session()
        self.authenticate()

        self.drivestrike_devices = []

        self.tokenPriv = os.environ.get('DRIVESTRIKE_PRIVATE_TOKEN').encode('utf-8')
        self.tokenPub = os.environ.get('DRIVESTRIKE_PUBLIC_TOKEN').encode('utf-8')

        if not (self.tokenPub or self.tokenPriv):
            LOGGER.fatal('Drivestrike public/private key not found')

        # -------------- Drivestrike Header Preparation -------------------
        self.requestBody = b""

        ts = datetime.datetime.now(datetime.timezone.utc).isoformat().encode("utf8")
        salt = binascii.hexlify(os.urandom(4))
        bodyHash = hashlib.sha256(self.requestBody).hexdigest().encode("utf8")

        # Sign the request using an HMAC
        hmacValue = hmac.new(self.tokenPriv, digestmod=hashlib.sha256)
        hmacValue.update(ts)
        hmacValue.update(salt)
        hmacValue.update(bodyHash)
        hmacStr = hmacValue.hexdigest().encode("utf8")

        # Create the headers dictionary
        self.drivestrike_headers = {
            "Accept": "application/json; version=2",
            "X-DriveStrike-TS": ts,
            "X-DriveStrike-Salt": salt,
            "X-DriveStrike-Body-Hash": bodyHash,
            "X-DriveStrike-Token": self.tokenPub,
            "X-DriveStrike-HMAC": hmacStr
        }
        # ----------------------------------------------------------------

    def __init_oomnitza_session(self):
        self.oomnitza_session = requests.Session()
        token = self.OomnitzaConnector.settings['api_token']
        self.oomnitza_session.headers.update({
            "Authorization2": os.environ.get('OOMNITZA_API_KEY', token),
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def _load_records(self, options):

        output = {}
        response = None

        self.drivestrike_devices = self.fetch_drivestrike_info()

        for device in self.drivestrike_devices:
            formatted_device = self._fetch_custom(device)
            output[formatted_device.get('drivestrike_serial_number')] = {'formatted_entry': formatted_device,
                                                          'response': None}
            equipment_id = self.create_or_update(self.oomnitza_session, formatted_device)
            serial_num = formatted_device.get('drivestrike_serial_number')
            if not serial_num:
                LOGGER.fatal(f"Could not find sync field for {serial_num}")
                continue
            if equipment_id:
                LOGGER.info("Updating oomnitza asset %s (%s)", equipment_id, serial_num)
                try:
                    response = self.oomnitza_session.patch(
                        json=formatted_device,
                        url=f"https://{OOMNITZA_SUBDOMAIN}.oomnitza.com/api/v3/assets/{equipment_id}"
                        # todo: revert url to production post-testing
                    )
                except Exception:
                    LOGGER.error("Unknown error trying to patch device", exc_info=True)
                    print(response.json())
                output[formatted_device.get('drivestrike_serial_number')]['response'] = response.json()
            else:
                LOGGER.warning(
                    f"Unable to find oomnitza asset for drivestrike_serial_number "
                    f"{formatted_device.get('drivestrike_serial_number')})"
                )
                output[formatted_device.get('drivestrike_serial_number')]['response'] = \
                    f"Unable to find oomnitza asset for drivestrike_serial_number entry " \
                    f"{formatted_device['drivestrike_serial_number']})"

                # yield formatted_device
        return output

    def _fetch_custom(self, drivestrike_entry):
        hwInfo = drivestrike_entry.get('hardwareInfo')
        serial_num = hwInfo.get('System Serial Number', hwInfo.get('BIOS Serial Number'))
        if not serial_num:
            LOGGER.fatal(f"Serial Number not found for {drivestrike_entry.get('deviceID')}")
            return {}

        output = {
            'drivestrike_id': drivestrike_entry.get('deviceID'),
            'drivestrike_status_last_updated': drivestrike_entry.get('statusUpdated'),
            'drivestrike_last_seen': drivestrike_entry.get('lastSeen'),
            'drivestrike_os': drivestrike_entry.get('os'),
            'drivestrike_os_version': drivestrike_entry.get('osVersion'),
            'drivestrike_hostname': hwInfo.get('DNS Host Name'),
            'drivestrike_encryption_status': check_drivestrike_encryption(
                hwInfo),
            'drivestrike_manufacturer': hwInfo.get('Manufacturer'),
            'drivestrike_model': hwInfo.get('Model'),
            'drivestrike_serial_number': hwInfo.get(
                'System Serial Number', hwInfo.get('BIOS Serial Number'))
        }

        output = empty_key_remover.converter(output, integration_name=self.MappingName)

        return output

    def create_or_update(self, oomnitza_session, formatted_entry):
        if all(value is None for value in formatted_entry.values()):
            LOGGER.info('Formatted Entry is empty. Skipping to next entry')
            return None
        serial_number = formatted_entry.get('drivestrike_serial_number')
        LOGGER.debug('Serial Number: {}'.format(serial_number))

        existing_assets = []

        if not existing_assets and serial_number:
            LOGGER.info("Attempting to resolve Drivestrike record by System Serial Number (%s)...",
                        serial_number)
            url_base = f"https://{OOMNITZA_SUBDOMAIN}.oomnitza.com/api/v3/assets?filter=serial_number eq '{serial_number}'"
            response = oomnitza_session.get(url=url_base)

            request_status = response.status_code

            if request_status == 200 and response.json():
                LOGGER.info("Found asset based on System Serial Number %s", serial_number)
                existing_assets.append(response.json())

        assets_found = len(existing_assets)
        if existing_assets and assets_found == 1:
            existing_asset = existing_assets[0]
            if existing_asset:
                return existing_asset[0].get('equipment_id')
            else:
                return None
        elif existing_assets and assets_found > 1:
            LOGGER.error(
                "Found %s assets during oomnitza lookup. Yielding first record only. %s",
                assets_found, existing_assets
            )
            existing_asset = existing_assets[0]
            if existing_asset:
                return existing_asset[0].get('equipment_id')

        return None

    def fix_time(self, timestring):
        import dateutil.parser
        parsed_time = dateutil.parser.parse(timestring)
        return parsed_time.strftime('%s' % parsed_time)

    def fetch_drivestrike_info(self):
        list_of_devices = []

        response = requests.get("https://app.drivestrike.com/api/devices/",
                                headers=self.drivestrike_headers,
                                data=self.requestBody)
        response = response.json()

        congestion_ctrl = 1
        start = time.time()

        while True:
            list_of_devices.extend(response['results'])
            if congestion_ctrl == 50:
                stop = time.time()
                if start - stop < 60:
                    time.sleep(stop - start)
                start = time.time()
                congestion_ctrl = 0
            if response['next'] is None:
                break
            else:
                device_url = response['next']
                response = requests.get(device_url, headers=self.drivestrike_headers,
                                        data=self.requestBody)
                response = response.json()
                congestion_ctrl += 1
        return list_of_devices
