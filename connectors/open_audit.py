import logging

import requests

from lib.connector import AssetsConnector


LOG = logging.getLogger("connectors/open_audit")  # pylint:disable=invalid-name


class Connector(AssetsConnector):
    MappingName = 'Open_Audit'
    Settings = {
        'url':                  {'order': 1, 'example': "http://XXX.XXX.XXX.XXX"},
        'username':             {'order': 2, 'example': ""},
        'password':             {'order': 3, 'default': ""},
    }
    DefaultConverters = {
        'hardware.end_of_life':           'date_format',
        'hardware.end_of_service':        'date_format',
        'hardware.first_seen':            'date_format',
        'hardware.last_seen':             'date_format',
        'hardware.os_installation_date':  'date_format',
        'hardware.warranty_expires':      'date_format',

    }
    FieldMappings = {
        'APPLICATIONS': {'source': "software"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.oa = OpenAuditCommunityAPI(
            url=self.settings['url'],
            username=self.settings['username'],
            password=self.settings['password']
        )

    def authenticate(self):
        """Attempts to authenticate with OpenAudIT, raises error if invalid."""
        self.oa.establish_session()

    def server_handler(self, body, wsgi_env, options):
        """Abstract method for server handler. Not needed for this connector."""
        raise NotImplementedError

    def _load_records(self, options):
        """Generator method that yields individual devices to synchronize."""
        for device in self.oa.get_devices():
            detail = self.oa.get_device_detail(device['id'])
            network = self.oa.get_device_network_detail(device['id'])
            software = self.oa.get_device_software(device['id'])

            # append network details
            detail['mac'] = network[0]['attributes'].get('mac') if network else ''
            detail['mac_vendor'] = network[0]['attributes'].get('manufacturer') if network else ''

            yield {'hardware': detail, 'software': software}


class OpenAuditCommunityAPI(object):
    """https://community.opmantek.com/display/OA/The+Open-AudIT+API"""
    def __init__(self, url, username, password):
        self.url = url
        self.username = username
        self.password = password
        self.session_id = None

    def get_url(self, parts):
        """Returns a complete URL, combining the base url and provided parts."""
        return self.url + '/open-audit/index.php' + parts

    def establish_session(self):
        """Establishes a session by invoking the logon endpoint."""
        response = requests.post(
            url=self.get_url('/logon'),
            data={
                'username': self.username,
                'password': self.password
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
        )
        response.raise_for_status()
        self.session_id = response.cookies.get('PHPSESSID')

    def perform_api_get(self, url):
        """Performs an HTTP GET API request using providing URL. Returns dictionary of parsed result."""
        response = requests.get(
            url=url,
            headers={
                'Cookie': 'PHPSESSID=' + self.session_id,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        )
        response.raise_for_status()
        return response.json()

    def get_devices(self, limit=1000):
        """Returns list of dictionaries for each device enrolled in OpenAudIT."""
        next_page = True
        offset = 0

        while next_page:
            url = self.get_url('/devices?limit=' + str(limit) + "&offset=" + str(offset))
            data = self.perform_api_get(url)
            next_page = bool(data['meta']['filtered'] == limit)
            offset += limit

            if not data['data']:
                next_page = False
                continue

            for result in data['data']:
                yield result

    def get_device_detail(self, device_id):
        """Returns a dictionary with device hardware attributes."""
        data = self.perform_api_get(
            url=self.get_url('/devices/' + str(device_id))
        )
        if not data['data']:
            raise Exception("No data retrieved for device detail: id=" + device_id)
        return data['data'][0]['attributes']

    def get_device_network_detail(self, device_id):
        """Returns a list of dictionaries for network interfaces associated with device."""
        data = self.perform_api_get(
            url=self.get_url('/devices/' + str(device_id) + '?sub_resource=network')
        )
        return data['data'] if data['data'] else []

    def get_device_software(self, device_id):
        """Returns a list of dictionaries for each piece of software associated with device."""
        data = self.perform_api_get(
            url=self.get_url('/devices/' + str(device_id) + '?sub_resource=software')
        )

        # prepare software records
        installed_software = []
        if data['data']:
            for software in data['data']:
                installed_software.append({
                    'name': software['attributes'].get('name'),
                    'version': software['attributes'].get('version'),
                    'publisher': software['attributes'].get('publisher'),
                    'path': software['attributes'].get('location')
                })

        return installed_software
