
import base64
import logging

from requests import ConnectionError, HTTPError
from lib.connector import UserConnector

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class Connector(UserConnector):
    MappingName = 'BambooHR'
    Settings = {
        'url':          {'order': 1, 'default': "https://api.bamboohr.com/api/gateway.php"},
        'system_name':  {'order': 2, 'example': "oomnitzasf"},
        'api_token':    {'order': 3, 'example': "ffb86eeabad3d7295b42797c2f003d33dec3cae7"},
        'default_role': {'order': 4, 'example': '12'},
    }

    FieldMappings = {
        'USER':           {'source': "workEmail"},
        'FIRST_NAME':     {'source': "firstName"},
        'LAST_NAME':      {'source': "lastName"},
        'EMAIL':          {'source': "workEmail"},
        'PHONE':          {'source': "mobilePhone"},
        'POSITION':       {'source': "jobTitle"},
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    def __init__(self, settings):
        super(Connector, self).__init__(settings)
        self.url_temlate = "%s/%s/{0}" % (self.settings['url'], self.settings['system_name'])

    def get_headers(self):
        auth_string = "Basic %s" % base64.standard_b64encode(self.settings['api_token'] + ":x")
        return {
            'Authorization': auth_string,
            'Accept': 'application/json'
        }

    def test_connection(self, options):
        try:
            url = self.url_temlate.format("v1/employees/0")
            response = self.get(url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        url = self.url_temlate.format("v1/employees/directory")
        response = self.get(url)
        employees = response.json()['employees']

        users = []
        for employee in employees:
            yield employee
