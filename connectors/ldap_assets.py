from __future__ import absolute_import

import json
import logging

import ldap

from lib.connector import AuditConnector, AuthenticationError
from lib.ext.ldap import LdapConnection

LOG = logging.getLogger("connectors/ldap_assets")  # pylint:disable=invalid-name


def json_validator(value):
    try:
        return json.loads(value)
    except ValueError:
        raise RuntimeError('setting is incorrect json expected but %r found' % value)


class Connector(AuditConnector):
    MappingName = 'LDAP_assets'
    Settings = {
        'url':              {'order':  1, 'example': "ldap://ldap.forumsys.com:389"},
        'username':         {'order':  2, 'example': "cn=read-only-admin,dc=example,dc=com"},
        'password':         {'order':  3, 'default': ""},
        'base_dn':          {'order':  4, 'example': "dc=example,dc=com"},
        'group_dn':         {'order':  5, 'default': ""},
        'protocol_version': {'order':  6, 'default': "3"},
        'filter':           {'order':  7, 'default': "(objectClass=*)"},
        'sync_field':       {'order':  8, 'example': '24DCF85294E411E38A52066B556BA4EE'},
        'page_criterium': {'order': 9, 'example': "someField[somechar]", 'default': ""},
        'groups_dn': {'order': 10, 'default': "[]",
                      'example': '["some.group", "other.group"]',
                      'validator': json_validator},
        'group_members_attr': {'order': 11, 'default': 'member'},
        'group_member_filter': {'order': 12, 'default': ''},
    }

    FieldMappings = {}

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        fields = list(set([str(f['source']) for f in self.field_mappings.values() if 'source' in f]))
        self.ldap_connection = LdapConnection(self.settings, fields)

    def authenticate(self):
        self.ldap_connection.authenticate()

    def do_test_connection(self, options):
        try:
            self.authenticate()
            return {'result': True, 'error': ''}
        except AuthenticationError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except ldap.SERVER_DOWN as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message['desc'])}
        except Exception as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % exp}

    def _load_records(self, options):
        for asset in self.ldap_connection.load_data(options):
            yield asset
