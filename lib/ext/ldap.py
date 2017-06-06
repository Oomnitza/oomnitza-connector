from __future__ import absolute_import

import errno
import logging
import os

import ldap
import ldapurl
from ldap.controls import SimplePagedResultsControl
from unicodecsv import DictWriter as DictUnicodeWriter

from lib import TrueValues
from lib.connector import AuthenticationError
from lib.error import ConfigError

LOG = logging.getLogger("ext/ldap")  # pylint:disable=invalid-name

ErrorDescriptions = """ From: https://community.hortonworks.com/questions/5322/ranger-user-sync-error-javaxnamingauthenticationex.html

The cause of the LDAP 49 error can vary. You need to check the data code to determine what the actual cause is. Here is a table of the various 49 errors/data codes and what they mean:

49 - LDAP_INVALID_CREDENTIALS - Indicates that during a bind operation one of the following occurred: The client passed either an incorrect DN or password, or the password is incorrect because it has expired, intruder detection has locked the account, or another similar reason. See the data code for more information.

49 / 52e - AD_INVALID CREDENTIALS - Indicates an Active Directory (AD) AcceptSecurityContexterror, which is returned when the username is valid but the combination of password and user credential is invalid. This is the AD equivalent of LDAP error code 49.
Note: I got this error, 52e, with a clearly invalid username.

49 / 525 - USER NOT FOUND - Indicates an Active Directory (AD) AcceptSecurityContextdata error that is returned when the username is invalid.

49 / 530 - NOT_PERMITTED_TO_LOGON_AT_THIS_TIME - Indicates an Active Directory (AD) AcceptSecurityContextdata error that is logon failure caused because the user is not permitted to log on at this time. Returns only when presented with a valid username and valid password credential.

49 / 531 - RESTRICTED_TO_SPECIFIC_MACHINES - Indicates an Active Directory (AD) AcceptSecurityContextdata error that is logon failure caused because the user is not permitted to log on from this computer. Returns only when presented with a valid username and valid password credential.

49 / 532 - PASSWORD_EXPIRED - Indicates an Active Directory (AD) AcceptSecurityContextdata error that is a logon failure. The specified account password has expired. Returns only when presented with valid username and password credential.

49 / 533 - ACCOUNT_DISABLED - Indicates an Active Directory (AD) AcceptSecurityContextdata error that is a logon failure. The account is currently disabled. Returns only when presented with valid username and password credential.

49 / 568 - ERROR_TOO_MANY_CONTEXT_IDS - Indicates that during a log-on attempt, the user's security context accumulated too many security IDs. This is an issue with the specific LDAP user object/account which should be investigated by the LDAP administrator.

49 / 701 - ACCOUNT_EXPIRED - Indicates an Active Directory (AD) AcceptSecurityContextdata error that is a logon failure. The user's account has expired. Returns only when presented with valid username and password credential.

49 / 773 - USER MUST RESET PASSWORD - Indicates an Active Directory (AD) AcceptSecurityContextdata error. The user's password must be changed before logging on the first time. Returns only when presented with valid user-name and password credential.

"""


class LdapConnection(object):
    @classmethod
    def clean_record(cls, record):
        clean_record = {}
        for key, value in record.items():
            try:
                if key == 'memberOf':
                    clean_record[key] = value
                else:
                    if isinstance(value, list):
                        if value:
                            value = value[0]
                        else:
                            value = u""
                    clean_record[key] = value.decode('unicode_escape').encode('iso8859-1').decode('utf8')
            except ValueError:
                clean_record[key] = "*BINARY*"
            except AttributeError:
                clean_record[key] = repr(value)
        return clean_record

    def __init__(self, settings, fields):
        self.settings = settings
        self.ldap_connection = None
        self.ldap_query_fields = fields

    def authenticate(self):
        # ldap.set_option(ldap.OPT_DEBUG_LEVEL, 1)
        ldap.set_option(ldap.OPT_REFERRALS, 0)
        ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 30)

        # the default LDAP protocol version - if not recognized - is v3
        if self.settings['protocol_version'] == '2':
            ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION2)
        else:
            if self.settings['protocol_version'] != '3':
                LOG.warning("Unrecognized Protocol Version '%s', setting to '3'.", self.settings['protocol_version'])
                self.settings['protocol_version'] = '3'
            ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)

        try:
            parsed_url = ldapurl.LDAPUrl(self.settings['url'])
        except ValueError:
            raise AuthenticationError("Invalid url to LDAP service. "
                                      "Check config examples at https://github.com/Oomnitza.")  # FixMe: get new url
        self.ldap_connection = ldap.initialize(parsed_url.unparse())

        cacert_file = self.settings.get('cacert_file', '')
        if cacert_file:
            cacert_file = os.path.abspath(cacert_file)
            if not os.path.isfile(cacert_file):
                raise ConfigError("%s is not a valid file!" % cacert_file)
            LOG.info("Setting CACert File to: %r.", cacert_file)
            ldap.set_option(ldap.OPT_X_TLS_CACERTFILE, cacert_file)
        cacert_dir = self.settings.get('cacert_dir', '')
        if cacert_dir:
            cacert_dir = os.path.abspath(cacert_dir)
            if not os.path.isdir(cacert_dir):
                raise ConfigError("%s is not a valid directory!" % cacert_dir)
            LOG.info("Setting CACert Dir to: %r.", cacert_dir)
            ldap.set_option(ldap.OPT_X_TLS_CACERTDIR, cacert_dir)

        # check for tls
        # if self.settings['enable_tls'] in self.TrueValues and self.settings['protocol_version'] == '3':
        if self.settings.get('verify_ssl', True) in TrueValues:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
        else:
            LOG.info("ldap.verify_ssl = '%s' so SSL certificate validation has been disabled.", self.settings.get('verify_ssl', True))
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)

        try:
            if self.settings['username'].lower() == 'anonymous':
                self.ldap_connection.simple_bind_s()
            else:
                password = self.settings['password']
                if not password:
                    LOG.warning("No password set for LDAP. Connecting without password.")
                    password = u""

                self.ldap_connection.simple_bind_s(self.settings['username'], password)
        except ldap.INVALID_CREDENTIALS:
            LOG.exception("Error calling simple_bind_s()")
            raise AuthenticationError("Cannot connect to the LDAP server with given credentials. "
                                      "Check the 'username', 'password' and 'dn' options "
                                      "in the config file in the '[ldap]' section.")
        except ldap.UNWILLING_TO_PERFORM as exp:
            LOG.exception("Error calling simple_bind_s()")
            raise AuthenticationError("Cannot connect to the LDAP server with given credentials: " + exp.args[0]['info'])

    def load_data(self, options):
        save_data = self.settings.get("__save_data__", False)
        if save_data:
            options['full_record'] = True
            try:
                os.makedirs("./saved_data")
                LOG.info("Saving data to %s.", os.path.abspath("./saved_data"))
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                    pass
                else:
                    raise

        if self.settings['protocol_version'] == '2':
            if self.settings['group_dn']:
                users = self.query_group(options)
            else:
                users = self.query_objects(options)
        else:
            if self.settings['group_dn']:
                users = self.query_group_paged(options)
            else:
                users = self.query_objects_paged(options)

        if save_data:
            data = []
            keys = set()
            for user in users:
                # Note: Not all user dicts contain all the fields. So, need to loop over
                #       all the users to make sure we don't miss any fields.
                keys.update(user.keys())
                data.append(user)

            used_keys = set(self.ldap_query_fields)
            unused_keys = set(keys) - used_keys
            if unused_keys:
                keys = sorted(used_keys) + ['unmapped ->'] + sorted(unused_keys)
            else:
                keys = sorted(used_keys)

            with open('./saved_data/ldap.csv', 'w') as save_file:
                writer = DictUnicodeWriter(save_file, keys)
                writer.writeheader()
                writer.writerows(data)

            users = data

        for user in users:
            yield user

    def query_objects(self, options):
        """
        Connects to LDAP server and attempts to query and return all users.
        """
        # search the server for users
        full_record = options.get('full_record', False)

        fields = self.ldap_query_fields
        if full_record:
            fields = None

        ldap_users = self.ldap_connection.search_s(
            self.settings['base_dn'], ldap.SCOPE_SUBTREE, self.settings['filter'],
            fields
        )
        # disconnect and return results
        self.ldap_connection.unbind_s()
        for user in ldap_users:
            if user[0] and user[1]:
                yield self.clean_record(user[1])

    def query_objects_paged(self, options):
        """
        Connects to LDAP server and attempts to query and return all users
        by iterating through each page result. Requires LDAP v3.
        """
        page_size = options.get('page_size', 500)
        criticality = options.get('criticality', True)
        cookie = options.get('cookie', '')
        full_record = options.get('full_record', False)

        fields = self.ldap_query_fields
        if full_record:
            fields = None

        # search the server for users
        first_pass = True
        pg_ctrl = SimplePagedResultsControl(criticality, page_size, cookie)

        LOG.debug("self.ldap_query_fields = %r", self.ldap_query_fields)
        while first_pass or pg_ctrl.cookie:
            first_pass = False
            msgid = self.ldap_connection.search_ext(
                self.settings['base_dn'], ldap.SCOPE_SUBTREE, self.settings['filter'],
                fields,
                serverctrls=[pg_ctrl]
            )

            result_type, ldap_users, msgid, serverctrls = self.ldap_connection.result3(msgid)
            pg_ctrl.cookie = serverctrls[0].cookie
            for user in ldap_users:
                if user[0] and user[1]:
                    yield self.clean_record(user[1])

        # disconnect and return results
        self.ldap_connection.unbind_s()

    def query_group(self, options):
        """
        Connects to LDAP server and attempts to query and return all objects in a Group.
        """
        group = self.ldap_connection.search_s(
            self.settings['group_dn'], ldap.SCOPE_SUBTREE, "(objectClass=*)", None
        )
        if group:
            group = group[0]
        if len(group) == 2 and group[0] and group[1]:
            group = group[1]
        if group:
            for index, member in enumerate(group['member']):
                print index, member

        members = []
        for member in group['member']:
            print member
            user = self.get_object(options, member)
            if user:
                members.append(self.clean_record(user))

        return members

    def query_group_paged(self, options):
        return self.query_group(options)

    def get_object(self, options, dn):
        full_record = options.get('full_record', False)

        fields = self.ldap_query_fields
        if full_record:
            fields = None

        result = self.ldap_connection.search_s(
            dn, ldap.SCOPE_BASE, self.settings['filter'],
            fields
        )
        if result:
            if len(result[0]) == 2 and result[0][1]:
                return result[0][1]

        LOG.warning("Unable to get LDAP object for '%s'.", dn)
        return None
