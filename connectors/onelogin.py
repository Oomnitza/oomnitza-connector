import base64
import logging
import xmltodict
import os
import errno


from requests import ConnectionError, HTTPError
from lib.connector import UserConnector

LOG = logging.getLogger("connectors/onelogin")  # pylint:disable=invalid-name


class Connector(UserConnector):
    MappingName = 'OneLogin'
    Settings = {
        'url':              {'order': 1, 'default': "https://app.onelogin.com/api/v2/users.xml"},
        'api_token':        {'order': 2, 'example': "YOUR OneLogin API TOKEN"},
        'default_role':     {'order': 3, 'example': 25, 'type': int},
        'default_position': {'order': 4, 'example': 'Employee'},
    }

    FieldMappings = {
        'USER':           {'source': "username"},
        'FIRST_NAME':     {'source': "firstname"},
        'LAST_NAME':      {'source': "lastname"},
        'EMAIL':          {'source': "email"},
        'PHONE':          {'source': "phone"},
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    StandardFields = {
        'activated-at',
        'created-at',
        'directory-id',
        'distinguished-name',
        'email',
        'external-id',
        'firstname',
        'group-id',
        'id',
        'invalid-login-attempts',
        'invitation-sent-at',
        'last-login',
        'lastname',
        'locale-code',
        'locked-until',
        'member-of',
        'openid-name',
        'password-changed-at',
        'phone',
        'status',
        'updated-at',
        'username',
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.url_template = "%s?include_custom_attributes=true&from_id={0}" % self.settings['url']

    def get_headers(self):
        return {
            'Authorization': "Basic %s" % base64.standard_b64encode(self.settings['api_token']+":x")
        }

    def do_test_connection(self, options):
        try:
            url = self.url_template.format(1)
            response = self.get(url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        if 'datafile' in options:
            with open(options['datafile'], 'r') as datafile:
                response = xmltodict.parse(datafile.read())
                users = response['users']
                if isinstance(users['user'], dict):
                    # If the OneLogin API returns one result users won't
                    # be in a list, there will just be one OrderedDict
                    users = [users['user']]
                elif isinstance(users['user'], list):
                    users = users['user']
                else:
                    raise RuntimeError("Unexpected response from OneLogin. Got type: %s" % type(users['user']))
                for user in users:
                    if isinstance(user['phone'], dict) and '@nil' in user['phone']:
                        user['phone'] = None
#                    print repr(user)
                    yield user
            return

        # The OneLogin API returns 100 results at a time. We'll start at 0 and
        # set the from_id parameter to the max_id for each subsequent request.
        last_id = 0
        while True:
            url = self.url_template.format(last_id)
            response = self.get(url)
            response.raise_for_status()

            if self.settings.get("__save_data__", False):
                try:
                    os.makedirs("./saved_data")
                    LOG.info("Saving data to %s.", os.path.abspath("./saved_data"))
                except OSError as exc:
                    if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                        pass
                    else:
                        raise
                with open("./saved_data/onelogin.{}.xml".format(last_id), "w") as output_file:
                    output_file.write(response.text)

            response = xmltodict.parse(response.text)
            if 'users' not in response:
                # The 'users' key doesn't exist.
                # We've likely gotten all the users we're going to get
                break
            else:
                users = response['users']
                if isinstance(users['user'], dict):
                    # If the OneLogin API returns one result users won't
                    # be in a list, there will just be one OrderedDict
                    users = [users['user']]
                elif isinstance(users['user'], list):
                    users = users['user']
                else:
                    raise RuntimeError("Unexpected response from OneLogin. Got type: %s" % type(users['user']))

                for user in users:
                    if isinstance(user['phone'], dict) and '@nil' in user['phone']:
                        user['phone'] = None
                    last_id = user['id']
                    yield user

    @classmethod
    def get_field_value(cls, field, data, default=None):
        if field not in cls.StandardFields and not field.startswith("custom_attribute_"):
            field = "custom_attribute_{}".format(field)
        return UserConnector.get_field_value(field, data, default)

