from lib.connector import UserConnector
from requests.auth import _basic_auth_str


class Connector(UserConnector):
    MappingName = 'BambooHR'
    Settings = {
        'url':              {'order': 1, 'default': "https://api.bamboohr.com/api/gateway.php"},
        'system_name':      {'order': 2, 'example': "YOUR BambooHR SYSTEM NAME"},
        'api_token':        {'order': 3, 'example': "YOUR BambooHR API TOKEN"},
        'default_role':     {'order': 4, 'example': '25'},
        'default_position': {'order': 5, 'example': 'Employee'},
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

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.url_template = "%s/%s/{0}" % (self.settings['url'], self.settings['system_name'])

    def get_headers(self):
        return {
            'Authorization': _basic_auth_str(self.settings['api_token'], 'x'),
            'Accept': 'application/json'
        }

    def _load_records(self, options):
        url = self.url_template.format("v1/employees/directory")
        response = self.get(url)
        employees = response.json()['employees']

        for employee in employees:
            yield employee
