import json
import logging

from lib.connector import UserConnector
from lib.error import ConfigError
from lib.ext.ldap import LdapConnection

LOG = logging.getLogger("connectors/ldap_users")  # pylint:disable=invalid-name


def json_validator(value):
    try:
        return json.loads(value)
    except ValueError:
        raise ConfigError('setting is incorrect json expected but %r found' % value)


class Connector(UserConnector):
    MappingName = 'LDAP'
    Settings = {
        'url':                  {'order': 1, 'example': "ldaps://ldap.com:389"},
        'username':             {'order': 2, 'example': "cn=read-only-admin,dc=example,dc=com"},
        'password':             {'order': 3, 'default': ""},
        'base_dn':              {'order': 4, 'example': "dc=example,dc=com"},
        'group_dn':             {'order': 5, 'default': ""},
        'protocol_version':     {'order': 6, 'default': "3"},
        'filter':               {'order': 7, 'default': "(objectClass=*)"},
        'default_role':         {'order': 8, 'example': 25, 'type': int},
        'default_position':     {'order': 9, 'example': 'Employee'},
        'page_criterium':       {'order': 10, 'example': "", 'default': ""},
        'groups_dn':            {'order': 11, 'default': "[]", 'example': '[]', 'validator': json_validator},
        'group_members_attr':   {'order': 12, 'default': 'member'},
        'group_member_filter':  {'order': 13, 'default': ''},
    }

    FieldMappings = {
        'USER':           {'source': "uid", 'required': True, 'converter': 'ldap_user_field'},
        'FIRST_NAME':     {'source': "givenName"},
        'LAST_NAME':      {'source': "sn"},
        'EMAIL':          {'source': "mail", 'required': True},
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        fields = list(set([str(f['source']) for f in self.field_mappings.values() if 'source' in f]+['sAMAccountName']))
        self.ldap_connection = LdapConnection(self.settings, fields)

    def authenticate(self):
        self.ldap_connection.authenticate()

    def _load_records(self, options):
        for user in self.ldap_connection.load_data(options):
            yield user
