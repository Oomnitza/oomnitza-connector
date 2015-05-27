from __future__ import absolute_import

import logging
import ldap
import ldapurl

from ldap.controls import SimplePagedResultsControl
from lib.connector import UserConnector, AuthenticationError

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class Connector(UserConnector):
    MappingName = 'LDAP'
    Settings = {
        'url':              {'order':  1, 'example': "ldap://ldap.forumsys.com:389"},
        'username':         {'order':  2, 'example': "cn=read-only-admin,dc=example,dc=com"},
        'password':         {'order':  3, 'example': "change-me"},
        'base_dn':          {'order':  4, 'example': "dc=example,dc=com"},
        'protocol_version': {'order':  5, 'default': "3"},
        'enable_tls':       {'order':  6, 'example': "True"},
        'filter':           {'order':  7, 'example': "(objectClass=*)"},
        'default_role':     {'order':  8, 'example': 25, 'type': int},
        'default_position': {'order':  9, 'example': 'Employee'},
    }

    FieldMappings = {
        'USER':           {'source': "uid", 'required': True, 'converter': 'ldap_user_field'},
        'FIRST_NAME':     {'source': "givenName", 'required': True},
        'LAST_NAME':      {'source': "sn", 'required': True},
        'EMAIL':          {'source': "mail", 'required': True},
        'PERMISSIONS_ID': {'setting': "default_role"},
        'POSITION':       {'setting': "default_position"},
    }

    def __init__(self, settings):
        super(Connector, self).__init__(settings)
        self.ldap_connection = None
        self.ldap_query_fields = list(set([str(f['source']) for f in self.field_mappings.values() if 'source' in f]+['sAMAccountName']))

    def authenticate(self):
        # ldap.set_option(ldap.OPT_DEBUG_LEVEL,1)
        ldap.set_option(ldap.OPT_REFERRALS, 0)
        ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 30)

        # the default LDAP protocol version - if not recognized - is v3
        if self.settings['protocol_version'] == '2':
            ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION2)
        else:
            if self.settings['protocol_version'] != '3':
                logger.warning("Unrecognized Protocol Version '%s', setting to '3'.", self.settings['protocol_version'])
                self.settings['protocol_version'] = '3'
            ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)

        try:
            parsed_url = ldapurl.LDAPUrl(self.settings['url'])
        except ValueError:
            raise AuthenticationError("Invalid url to LDAP service. "
                                      "Check config examples at https://github.com/Oomnitza.")  # FixMe: get new url
        self.ldap_connection = ldap.initialize(parsed_url.unparse())

        # check for tls
        if self.settings['enable_tls'] in self.TrueValues and self.settings['protocol_version'] == '3':
            try:
                self.ldap_connection.start_tls_s()
            except ldap.LDAPError as exp:
                logger.debug("%s", exp.message)
                raise AuthenticationError("Error when trying to enable TLS on connection. You may need to set enable_tls = False in your config.ini file.")

        try:
            if self.settings['password'] in [None, '', ' ']:  # FixMe: test for interactive console? just remove?
                raise AuthenticationError("Password is required.")
                # self.ldap_connection.simple_bind_s(self.settings['username'], getpass())
            else:
                self.ldap_connection.simple_bind_s(self.settings['username'], self.settings['password'])
        except ldap.INVALID_CREDENTIALS:
            raise AuthenticationError("Cannot connect to the LDAP server with given credentials. "
                                      "Check the 'username', 'password' and 'dn' options "
                                      "in the config file in the '[ldap]' section.")

    def test_connection(self, options):
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
        assert self.settings['protocol_version'] in ['2', '3'], \
            "Unknown protocol version %r" % self.settings['protocol_version']

        if self.settings['protocol_version'] == '2':
            return self.query_users(options)
        else:
            return self.query_users_paged(options)

    def query_users(self, options):
        """
        Connects to LDAP server and attempts to query and return all users.
        """
        # search the server for users
        ldap_users = self.ldap_connection.search_s(
            self.settings['base_dn'], ldap.SCOPE_SUBTREE, self.settings['filter'],
            self.ldap_query_fields
        )
        # disconnect and return results
        self.ldap_connection.unbind_s()
        for user in ldap_users:
            if user[0]:
                yield user[1]

    def query_users_paged(self, options):
        """
        Connects to LDAP server and attempts to query and return all users
        by iterating through each page result. Requires LDAP v3.
        """
        page_size = options.get('page_size', 500)
        criticality = options.get('criticality', True)
        cookie = options.get('cookie', '')

        # search the server for users
        first_pass = True
        pg_ctrl = SimplePagedResultsControl(criticality, page_size, cookie)

        logger.debug("self.ldap_query_fields = %r", self.ldap_query_fields)
        while first_pass or pg_ctrl.cookie:
            first_pass = False
            msgid = self.ldap_connection.search_ext(
                self.settings['base_dn'], ldap.SCOPE_SUBTREE, self.settings['filter'],
                self.ldap_query_fields,
                serverctrls=[pg_ctrl]
            )

            result_type, ldap_users, msgid, serverctrls = self.ldap_connection.result3(msgid)
            pg_ctrl.cookie = serverctrls[0].cookie
            for user in ldap_users:
                if user[0]:
                    yield user[1]

        # disconnect and return results
        self.ldap_connection.unbind_s()

    @classmethod
    def get_field_value(cls, field, data, default=[None]):
        return data.get(field, default)[0]

