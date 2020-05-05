from requests.auth import _basic_auth_str

from lib.connector import UserConnector


class Connector(UserConnector):
    MappingName = 'Workday'
    Settings = {
        'report_url':       {'order': 1, 'example': ''},
        'username':         {'order': 2, 'example': "change-me"},
        'password':         {'order': 3, 'example': "***"},
        'default_role':     {'order': 4, 'example': 25, 'type': int},
        'default_position': {'order': 5, 'example': 'Employee'},
    }

    FieldMappings = {
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    def get_headers(self):
        return {
            'Authorization': _basic_auth_str(self.settings['username'], self.settings['password']),
            'Accept': 'application/json',
        }

    def _load_records(self, options):
        response = self.get(self.settings['report_url'])
        report = response.json()['Report_Entry']
        for user in report:
            yield user
