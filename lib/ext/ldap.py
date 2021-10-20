import logging
import os
import struct

import ldap
import ldapurl
from ldap.controls.libldap import SimplePagedResultsControl
from ldap.controls.sss import SSSRequestControl

from lib import TrueValues
from lib.connector import AuthenticationError
from lib.error import ConfigError

LOG = logging.getLogger("ext/ldap")  # pylint:disable=invalid-name


class LdapBinaryField(object):

    _FIELD_NAME = ''

    @classmethod
    def check_if_handle(cls, field_name):
        return cls._FIELD_NAME == field_name

    @classmethod
    def bin_to_str(cls, bin_value):
        raise NotImplemented

    @classmethod
    def _byte_to_unsigned_long_long(cls, byte_value, little_endian=True):
        if not isinstance(byte_value, bytes):
            raise Exception('Incoming value needs to be a bytes object.')

        byte_order = '<' if little_endian else '>'
        format_char = 'Q'  # unsigned long long
        justified_byte = b'\x00'
        unpack_format = '{byte_order}{format_char}'.format(byte_order=byte_order,
                                                    format_char=format_char)
        buffer_bytes = struct.calcsize(unpack_format)

        if len(byte_value) > buffer_bytes:
            raise Exception('Unpack unsigned long long requires '
                            'a buffer of {} bytes.'.format(buffer_bytes))

        if little_endian:
            justified_byte_value = byte_value.ljust(buffer_bytes, justified_byte)
            return struct.unpack(unpack_format, justified_byte_value)[0]
        else:
            justified_byte_value = byte_value.rjust(buffer_bytes, justified_byte)
            return struct.unpack(unpack_format, justified_byte_value)[0]


class ObjectSidField(LdapBinaryField):

    _FIELD_NAME = 'objectSid'

    @classmethod
    def bin_to_str(cls, bin_value):
        # SID Format: S-Revision-Authority-SubAuthority[n]...
        # SID Example: S-1-5-21-789336058-854245398-1708537768-6412
        # SID Binary Example: '\x01\x05\x00\x00\x00\x00\x00\x05\x15\x00\x00\x00
        #                      \xfaO\x0c/\x16\xc0\xea2\xa87\xd6e\x0c\x19\x00\x00'
        incoming_value = bin_value
        if isinstance(incoming_value, str):
            incoming_value = str.encode(bin_value)

        # byte(0): The revision level of the SID structure
        revision = cls._byte_to_unsigned_long_long(incoming_value[0:1])

        # byte(2 - 7): A 48-bit identifier authority value that identifies
        # the authority that issued this SID (in Big-Endian format)
        identifier_auth_value = cls._byte_to_unsigned_long_long(incoming_value[2:8], False)

        # byte(1): Count of sub-authorities
        count_of_sub_authorities = cls._byte_to_unsigned_long_long(incoming_value[1:2])
        bytes_each_chunk = 4
        start_byte = 8
        end_byte = 12
        relative_ids = []

        # byte(8 - last): A variable number of Relative Identifier (RID) values
        # that uniquely identify the trustee relative to the authority
        # that issued this SID
        for i in range(count_of_sub_authorities):
            start_index = start_byte + bytes_each_chunk * i
            end_index = end_byte + bytes_each_chunk * i
            relative_ids.append(cls._byte_to_unsigned_long_long(incoming_value[start_index: end_index]))

        return 'S-{revision}-{identifier_auth_value}-{relative_ids}'.format(
            revision=revision,
            identifier_auth_value=identifier_auth_value,
            relative_ids='-'.join([str(sub_id) for sub_id in relative_ids])
        )


class LdapConnection(object):

    _BINARY_FIELD_HANDLERS = [
        ObjectSidField
    ]

    @classmethod
    def clean_record(cls, record):
        clean_record = {}
        for key, value in record.items():
            try:
                if key == 'memberOf':
                    if not isinstance(value, list):
                        value = [value]

                    clean_value = [item.decode('UTF-8') for item in value]
                    clean_record[key] = clean_value
                else:
                    if isinstance(value, list):
                        if value:
                            value = value[0]
                        else:
                            value = ""
                    bin_to_str_handler = cls._select_binary_field_handler(key)
                    if bin_to_str_handler:
                        clean_record[key] = bin_to_str_handler.bin_to_str(value)
                    else:
                        clean_record[key] = value.decode('UTF-8')
            except ValueError as ex:
                clean_record[key] = "*BINARY*"
            except AttributeError:
                clean_record[key] = repr(value)
        return clean_record

    @classmethod
    def _select_binary_field_handler(cls, field_name):
        for handler in cls._BINARY_FIELD_HANDLERS:
            if handler.check_if_handle(field_name):
                return handler
        return None

    def __init__(self, settings, fields):
        self.pg_ctrl = None
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
                                      "Check config examples at https://github.com/Oomnitza/oomnitza-connector")
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
            LOG.warning("verify_ssl = '%s' so SSL certificate validation has been disabled.", self.settings.get('verify_ssl', True))
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)

        try:
            if self.settings['username'].lower() == 'anonymous':
                self.ldap_connection.simple_bind_s()
            else:
                password = self.settings['password']
                if not password:
                    LOG.warning("No password set for LDAP. Connecting without password.")
                    password = ""

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

        if self.settings['protocol_version'] == '2':
            if self.settings['groups_dn']:
                users = self.query_groups(options)
            elif self.settings['group_dn']:
                users = self.query_group(options, self.settings['group_dn'])
            else:
                users = self.query_objects(options)
        else:
            if self.settings['groups_dn']:
                users = self.query_groups(options)
            elif self.settings['group_dn']:
                users = self.query_group_paged(options, self.settings['group_dn'])
            else:
                users = self.query_objects_paged(options)

        if save_data:
            data = []
            keys = set()
            for user in users:
                # Note: Not all user dicts contain all the fields. So, need to loop over
                #       all the users to make sure we don't miss any fields.
                keys.update(list(user.keys()))
                data.append(user)

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

    def get_page(self, page_size, full_record):
        """
        Method used to retrieve all the objects in the "page" using Simple Paged Results Manipulation
        and Server Side Sorting extensions

        https://tools.ietf.org/html/rfc2696
        https://tools.ietf.org/html/rfc2891

        :param full_record: flag identifying that we hav to extract the full set of fields
        :param page_size: size of page
        :return: generator
        """
        fields = self.ldap_query_fields
        if full_record:
            fields = None

        # set ldap control extensions
        if not self.pg_ctrl:
            self.pg_ctrl = SimplePagedResultsControl(True, page_size, '')

        serverctrls = [self.pg_ctrl]
        if fields:
            # if we have defined set of fields, use the last one for the sorting
            serverctrls.append(SSSRequestControl(ordering_rules=[fields[-1]]))

        msgid = self.ldap_connection.search_ext(
            self.settings['base_dn'], ldap.SCOPE_SUBTREE, self.settings['filter'],
            fields,
            serverctrls=serverctrls
        )

        _, records, msgid, serverctrls = self.ldap_connection.result3(msgid)
        self.pg_ctrl.cookie = [_ for _ in serverctrls if _.controlType == SimplePagedResultsControl.controlType][0].cookie

        if not self.pg_ctrl.cookie:
            # disconnect, the page is the last one
            self.ldap_connection.unbind_s()

        return (self.clean_record(record[1]) for record in records if (record[0] and record[1]))

    def pages(self, options):
        """
        Gather all the pages and then return them.
        This is not optimal approach but allow us to not handle connection timeout exception
        in case of long data pushing to Oomnitza
        :param options:
        :return:
        """
        pages = []

        page_size = options.get('page_size', 500)
        full_record = options.get('full_record', False)

        LOG.info("Gathering LDAP info...")
        counter = 1
        while not self.pg_ctrl or self.pg_ctrl.cookie:

            pages.append(self.get_page(page_size, full_record))
            LOG.info("Gathered up to %d records" % (counter * page_size))
            counter += 1

        return pages

    def query_objects_paged(self, options):
        """
        Generator over the gathered pages
        :param options:
        :return:
        """
        pages = self.pages(options)

        while pages:

            page_generator = pages.pop()

            for record in page_generator:
                yield record

    def query_groups(self, options):
        members = []
        groups_dn = self.settings['groups_dn']
        for group_dn in groups_dn:
            members.extend(self.query_group(options, group_dn))
        return members

    def query_group(self, options, group_dn):
        """
        Connects to LDAP server and attempts to query and return all objects in a Group.
        """
        group = self.ldap_connection.search_s(
            group_dn, ldap.SCOPE_SUBTREE, "(objectClass=*)", None
        )
        if group:
            group = group[0]
        if len(group) == 2 and group[0] and group[1]:
            group = group[1]

        members = []
        for member in group[self.settings['group_members_attr']]:
            if self.settings['group_member_filter']:
                user = self.get_object(
                    options,
                    filter=self.settings['group_member_filter'].format(member)
                )
            else:
                user = self.get_object(options, dn=member)
            if user:
                members.append(self.clean_record(user))

        return members

    def query_group_paged(self, options, group_dn):
        return self.query_group(options, group_dn)

    def get_object(self, options, dn=None, filter=None):
        full_record = options.get('full_record', False)

        fields = self.ldap_query_fields
        if full_record:
            fields = None

        if dn:
            result = self.ldap_connection.search_s(
                dn, ldap.SCOPE_BASE, self.settings['filter'], fields
            )
        elif filter:
            ldap_filter = '(&{}{})'.format(self.settings['filter'], filter)
            result = self.ldap_connection.search_s(
                self.settings['base_dn'],
                ldap.SCOPE_SUBTREE,
                ldap_filter,
                fields
            )
        else:
            LOG.error("Neither dn nor filter was provided for get_object method")
            return None

        if result:
            if len(result[0]) == 2 and result[0][1]:
                return result[0][1]

        LOG.warning("Unable to get LDAP object for '%s'.", dn)
        return None
