import base64
import json
import logging

import xmltodict
from enum import Enum
from requests import ConnectionError, HTTPError

from lib.connector import UserConnector
from lib.error import ConfigError, AuthenticationError

LOG = logging.getLogger("connectors/onelogin")  # pylint:disable=invalid-name


class Connector(UserConnector):
    MappingName = 'OneLogin'
    Version = Enum('Version', ['v1_to_v3', 'slash_one'])
    Settings = {
        'url':              {'order': 1, 'default': "https://api.us.onelogin.com/api/1/users"},
        'client_id':        {'order': 2, 'example': 'qwerty12345678901234567890', 'default': ""},
        'client_secret':    {'order': 3, 'example': 'qwerty12345678901234567890', 'default': ""},
        'default_role':     {'order': 4, 'example': 25, 'type': int},
        'default_position': {'order': 5, 'example': 'Employee'},
        'api_token':        {'order': 6, 'example': "", 'default': ""},
    }

    FieldMappings = {
        'USER':           {'source': "username"},
        'FIRST_NAME':     {'source': "firstname"},
        'LAST_NAME':      {'source': "lastname"},
        'EMAIL':          {'source': "email"},
        'PHONE':          {'source': "phone"},
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    # API: v1-v3 APIs have been deprecated. But they won't be shut off until 2017.
    V1ToV3Fields = {
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

    # API: /1 is the newest OneLogin API which is based on RESTful principles and secured by OAuth 2.0.
    SlashOneFields = {
        'activated_at',
        'created_at',
        'email',
        'username',
        'firstname',
        'group_id',
        'id',
        'invalid_login_attempts',
        'invitation_sent_at',
        'last_login',
        'lastname',
        'locked_until',
        'comment',
        'openid_name',
        'locale_code',
        'password_changed_at',
        'phone',
        'status',
        'updated_at',
        'distinguished_name',
        'external_id',
        'directory_id',
        'member_of',
        'samaccountname',
        'userprincipalname',
        'manager_ad_id',
        'role_id',
        'company',
        'department',
        'title',
        'state',
        'trusted_idp_id',
    }

    access_token = None
    api_version = None

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self._decide_api_version()
        self._init_url_template()

    def _decide_api_version(self):
        if self.settings.get('client_id') and self.settings.get('client_secret'):
            self.api_version = Connector.Version.slash_one
        elif self.settings.get('api_token'):
            LOG.warning('Deprecated API used! Please switch to the new OneLogin API')
            self.api_version = Connector.Version.v1_to_v3
        else:
            raise ConfigError('OneLogin connector configured improperly')

    def _init_url_template(self):
        if self.api_version == Connector.Version.slash_one:
            self.url_template = "%s?after_cursor={0}" % self.settings['url']
            self.test_conn_url = self.url_template.format('')
        elif self.api_version == Connector.Version.v1_to_v3:
            self.url_template = "%s?include_custom_attributes=true&page={0}" % self.settings['url']
            self.test_conn_url = self.url_template.format(1)
        else:
            raise ConfigError('OneLogin connector url template cannot be initialized with invalid version')

    def get_headers_v1_to_v3(self):
        """
        DEPRECATED
        """
        return {
            'Authorization': "Basic %s" % base64.standard_b64encode(self.settings['api_token'] + ":x")
        }

    def get_headers_slash_one(self):
        # Load OAuth 2.0 token if need
        if not self.access_token:
            client_id = self.settings['client_id']
            client_secret = self.settings['client_secret']
            headers = {
                "Content-Type": "application/json",
                "Authorization": "client_id:{}, client_secret:{}".format(client_id, client_secret)
            }
            data = {
                "grant_type": "client_credentials"
            }
            response = self.post('https://api.us.onelogin.com/auth/oauth2/token', data, headers)
            response = json.loads(response.text)
            if response['status']['code'] != 200:
                raise AuthenticationError("Unexpected response from OneLogin. Got code: {}, message: {}".format(
                    response['status']['code'], response['status']['message']))
            self.access_token = response['data'][0]['access_token']

        return {
            'Authorization': 'bearer:{}'.format(self.access_token)
        }

    def get_headers(self):
        if self.api_version == Connector.Version.v1_to_v3:
            return self.get_headers_v1_to_v3()
        elif self.api_version == Connector.Version.slash_one:
            return self.get_headers_slash_one()
        else:
            raise RuntimeError('OneLogin connector headers cannot be fetched with invalid version')

    def do_test_connection(self, options):
        try:
            response = self.get(self.test_conn_url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % exp.message}

    def get_users_v1_to_v3(self):
        """
        DEPRECATED
        """

        # The OneLogin API returns 100 results at a time. We'll start at 0 and
        # set the from_id parameter to the max_id for each subsequent request.

        page = 1
        while True:
            url = self.url_template.format(page)
            response = self.get(url)
            response.raise_for_status()

            users = xmltodict.parse(response.text).get('users', {}).get('user', [])
            if not users:
                # The 'users' key doesn't exist.
                # We've likely gotten all the users we're going to get
                break
            else:
                if isinstance(users, dict):
                    # If the OneLogin API returns one result users won't
                    # be in a list, there will just be one OrderedDict
                    users = [users]

                for user in users:
                    for key in user:
                        if isinstance(user[key], dict) and '@nil' in user[key]:
                            user[key] = None
                    yield user

            page += 1

    def get_users_slash_one(self):

        # The OneLogin API returns 50 results at a time. We'll start from empty after_cursor
        # set after_cursor from response['pagination']['after_cursor']
        # when after_cursor - eq to None, it's last page

        after_cursor = ''
        while True:
            url = self.url_template.format(after_cursor)
            response = self.get(url)
            response.raise_for_status()

            response = json.loads(response.text)
            if 'pagination' not in response:
                # need pagination to request for next page
                break
            else:
                after_cursor = response['pagination']['after_cursor']
            if 'data' not in response:
                # The 'data' key doesn't exist.
                # We've likely gotten all the users we're going to get
                break
            else:
                users = response['data']

                for user in users:
                    for key in user:
                        if isinstance(user[key], dict) and '@nil' in user[key]:
                            user[key] = None
                    yield user

            # When we've loaded last page
            if after_cursor is None:
                return

    def _load_records(self, options):

        # region Deprecated functionality?
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
                    for key in user:
                        if isinstance(user[key], dict) and '@nil' in user[key]:
                            user[key] = None
                    yield user
            return
        # endregion

        if self.api_version == Connector.Version.v1_to_v3:
            generator = self.get_users_v1_to_v3()
        elif self.api_version == Connector.Version.slash_one:
            generator = self.get_users_slash_one()
        else:
            raise RuntimeError('OneLogin connector users cannot be fetched with invalid version')

        for user in generator:
            yield user

    def get_field_value(self, field, data, default=None):
        custom_prefix = "custom_attributes."
        standard_fields = Connector.SlashOneFields
        if self.api_version == Connector.Version.v1_to_v3:
            custom_prefix = "custom_attribute_"
            standard_fields = Connector.V1ToV3Fields

        if field not in standard_fields and not field.startswith(custom_prefix):
            field = "{}{}".format(custom_prefix, field)
        return super(Connector, self).get_field_value(field, data, default)
