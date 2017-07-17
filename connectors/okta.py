import errno
import json
import logging
import os

from requests import ConnectionError, HTTPError

from lib.connector import UserConnector

logger = logging.getLogger("connectors/okta")  # pylint:disable=invalid-name


class Connector(UserConnector):
    MappingName = 'Okta'
    Settings = {
        'url':              {'order': 1, 'default': "https://example-admin.okta.com"},
        'api_token':        {'order': 2, 'example': "YOUR Okta API TOKEN"},
        'default_role':     {'order': 3, 'example': 25, 'type': int},
        'default_position': {'order': 4, 'example': 'Employee'},
    }

    FieldMappings = {
        'USER':           {'source': "profile.login"},
        'FIRST_NAME':     {'source': "profile.firstName"},
        'LAST_NAME':      {'source': "profile.lastName"},
        'EMAIL':          {'source': "profile.email"},
        'PHONE':          {'source': "profile.mobilePhone"},
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'SSWS %s' % self.settings['api_token']
        }

    def do_test_connection(self, options):
        try:
            url = "{0}/api/v1/users?limit=1".format(self.settings['url'])
            response = self.get(url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}

    def _load_records(self, options):
        page = "{0}/api/v1/users?limit={1}".format(self.settings['url'], options.get('limit', 100))
        index = 0
        while page:
            response = self.get(page)
            for user in response.json():
                if self.settings.get("__save_data__", False):
                    try:
                        os.makedirs("./saved_data")
                    except OSError as exc:
                        if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                            pass
                        else:
                            raise
                    with open("./saved_data/{}.json".format(str(index)), "w") as save_file:
                        save_file.write(json.dumps(user['profile']))
                index += 1
                yield user

            page = response.links.get('next', {}).get('url', None)
