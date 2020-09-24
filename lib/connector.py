import copy
import errno
import json
import logging
import os
from uuid import uuid4
from datetime import datetime, date
from distutils.util import strtobool

import requests
from gevent.pool import Pool
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException

from lib import TrueValues
from utils.data import get_field_value
from .converters import Converter
from .error import ConfigError, AuthenticationError
from .filter import DynamicException
from .httpadapters import AdapterMap, retries
from .strongbox import Strongbox, StrongboxBackend
from .version import VERSION

LOG = logging.getLogger("lib/connector")


LastInstalledHandler = None


def run_connector(oomnitza_connector, connector, options):
    global LOG

    try:
        LOG = logging.getLogger(connector['__name__'])

        conn = connector["__connector__"]

        try:
            conn.authenticate()
        except AuthenticationError as exp:
            LOG.error("Authentication failure: %s", str(exp))
            return
        except requests.HTTPError:
            LOG.exception("Error connecting to %s service.", connector['__name__'])
            return

        try:
            conn.perform_sync(oomnitza_connector, options)
        except ConfigError as exp:
            LOG.error(exp)
        except requests.HTTPError:
            LOG.exception("Error syncing data for %s service.", connector['__name__'])
    except DynamicException as exp:
        LOG.error("Error running filter for %s: %s", connector['__name__'], str(exp))
    except:  # pylint:disable=broad-except
        LOG.exception("Unhandled error in run_connector for %s", connector['__name__'])


class BaseConnector(object):
    Converters = {}
    FieldMappings = {}
    MappingName = "unnamed"
    OomnitzaBatchSize = 100
    BuiltinSettings = ('ssl_protocol',)

    OomnitzaConnector = None

    CommonSettings = {
        'verify_ssl':     {'order': 0, 'default': "True"},
        'cacert_file':    {'order': 1, 'default': ""},
        'cacert_dir':     {'order': 2, 'default': ""},
        'env_password':   {'order': 3, 'default': ""},
        'ssl_protocol':   {'order': 4, 'default': ""},
        'use_server_map': {'order': 5, 'default': "True"},
        'only_if_filled': {'order': 6, 'default': ""},
        'dont_overwrite': {'order': 7, 'default': ""},
        'insert_only':    {'order': 8, 'default': "False"},
        'update_only':    {'order': 9, 'default': "False"},
        'sync_field':     {'order': 10},
        'vault_keys':     {'order': 11, 'default': ""},
        'vault_backend':  {'order': 12, 'default': StrongboxBackend.KEYRING},
        'vault_alias':    {'order': 13, 'default': ""},
        'user_pem_file':  {'order': 14, 'default': ""}
    }

    def __init__(self, section, settings):
        self.processed_records_counter = 0.
        self.sent_records_counter = 0.
        self.section = section
        self.settings = {'VERSION': VERSION}
        self.keep_going = True
        ini_field_mappings = {}
        self.__filter__ = None
        self.send_counter = 0
        self._session = None
        self.portion = str(uuid4())

        for key, value in list(settings.items()):
            if key.startswith('mapping.'):
                # it is a field mapping from the ini
                field_name = key.split('.')[1].upper()
                # ToDo: validate mapping
                ini_field_mappings[field_name] = value
            # elif key.startswith('subrecord.'):
            #     ini_field_mappings[key] = value
            elif key == '__filter__':
                self.__filter__ = value
            else:
                # first, simple copy for internal __key__ values
                if (key.startswith('__') and key.endswith('__')) or key in self.BuiltinSettings:
                    self.settings[key] = value
                    continue

                if key not in self.Settings and key not in self.CommonSettings:
                    LOG.warning("Invalid setting in %r section: %r." % (section, key))
                    continue

                self.settings[key] = value

        # loop over settings definitions, setting default values
        for key, setting in list(self.Settings.items()):
            setting_value = self.settings.get(key, None)
            if not setting_value:
                setting_value = setting.get('default', None)
                if setting_value is None:
                    raise ConfigError("Missing setting value for %s." % key)
            if setting.get('validator', None):
                setting_value = setting['validator'](setting_value)
            self.settings[key] = setting_value

        self.field_mappings = self.get_field_mappings(ini_field_mappings)
        if hasattr(self, "DefaultConverters"):
            for field, mapping in list(self.field_mappings.items()):
                source = mapping.get('source', None)
                if source in self.DefaultConverters and 'converter' not in mapping:
                    mapping['converter'] = self.DefaultConverters[source]

        if section == 'oomnitza' and not BaseConnector.OomnitzaConnector:
            BaseConnector.OomnitzaConnector = self

        backend_name = settings.get('vault_backend', StrongboxBackend.KEYRING)
        secret_alias = settings.get("vault_alias") or section
        self._strongbox = Strongbox(secret_alias, backend_name)
        self._preload_secrets()

    @staticmethod
    def json_serializer(value):
        """
        In the `--save-data` mode we are dumping the data to the JSON notation.
        So the we should pre-process the values to be sure these can be represented as the 
        JSON (https://docs.python.org/2/library/json.html#py-to-json-table)
        """
        if isinstance(value, (date, datetime)):
            return value.isoformat()

    def _get_secrets(self, keys=None):
        """
        Get secrets from vault for specified keys. Raises ``ConfigError``
        if secret is missed in vault.
        """
        secrets = {}
        if keys is not None:
            for secret_key in keys:
                secret_value = self._strongbox.get_secret(secret_key)
                if secret_value:
                    secrets[secret_key] = secret_value
                else:
                    raise ConfigError(
                        "Unable to find secret in secretbox, ensure secret "
                        "key/value pair has been inserted before starting "
                        "connector:\n\t"
                        "python strongbox.py --connector=%s --key=%s --value="
                        % (self._strongbox._service_name, secret_key)
                    )
        return secrets

    def _preload_secrets(self):
        """
        Load secrets from vault into connector settings.
        """
        secret_keys_string = self.settings.get('vault_keys', '')
        secret_keys = secret_keys_string.split()
        secrets = self._get_secrets(secret_keys)
        self.settings.update(secrets)

    def get_field_mappings(self, extra_mappings):
        mappings = self.get_default_mappings()  # loads from Connector object or Oomnitza mapping api

        for field, mapping in list(extra_mappings.items()):
            if field not in mappings:
                mappings[field] = mapping
            else:
                for key, value in list(mapping.items()):
                    mappings[field][key] = value

        return mappings

    def get_mapping_from_oomnitza(self):
        """
        Connect to the DSS service for the mapping
        :return: 
        """
        return self.settings['__oomnitza_connector__'].get_mappings(self.MappingName)

    def get_default_mappings(self):
        """
        Returns the default mappings, as defined in the class level FieldMappings dict.
        It supports loading mappings from Oomnitza API.
        :return: the default mappings
        """
        # Connector mappings are stored in Oomnitza, so get them.
        default_mappings = copy.deepcopy(self.FieldMappings)

        if self.settings.get('use_server_map', True) in TrueValues:
            server_mappings = self.get_mapping_from_oomnitza()

            for source, fields in list(server_mappings.items()):
                if isinstance(fields, str):
                    fields = [fields]
                for f in fields:
                    if f not in default_mappings:
                        default_mappings[f] = {}
                    default_mappings[f]['source'] = source

        return default_mappings

    @classmethod
    def example_ini_settings(cls):
        """
        Returns the ini settings for this connector with default and example values.
        This is used to generate the INI file.
        :return:
        """
        settings = [('enable', 'False')]
        for key, value in sorted(list(cls.Settings.items()), key=lambda t: t[1]['order']):
            if 'example' in value:
                # settings.append((key, "[{0}]".format(value['example'])))
                settings.append((key, value['example']))
            elif 'default' in value:
                settings.append((key, value['default']))
            else:
                settings.append((key, ''))
        return settings

    def _get_session(self):
        if not self._session:
            self._session = requests.Session()
            protocol = self.settings.get('ssl_protocol', "")
            user_pem_file = self.settings.get('user_pem_file')
            if user_pem_file:
                self._session.cert = user_pem_file
            if protocol:
                LOG.info("Forcing SSL Protocol to: %s", protocol)
                if protocol.lower() in AdapterMap:
                    self._session.mount("https://", AdapterMap[protocol.lower()](max_retries=retries))
                else:
                    raise RuntimeError("Invalid value for ssl_protocol: %r. Valid values are %r.",
                                       protocol, list(set(AdapterMap.keys())))
            else:
                self._session.mount("https://", HTTPAdapter(max_retries=retries))

            self._session.mount("http://", HTTPAdapter(max_retries=retries))
        return self._session

    def get(self, url, headers=None, auth=None):
        """
        Performs a HTTP GET against the passed URL using either the standard or passed headers
        :param url: the full url to retrieve.
        :param headers: optional headers to override the headers from get_headers()
        :return: the response object
        """
        LOG.debug("getting url: %s", url)
        session = self._get_session()

        headers = headers or self.get_headers()
        auth = auth or self.get_auth()
        # LOG.debug("headers: %r", headers)
        response = session.get(url, headers=headers, auth=auth,
                               verify=self.get_verification())

        response.raise_for_status()
        return response

    def post(self, url, data, headers=None, auth=None, post_as_json=True):
        """
        Performs a HTTP GET against the passed URL using either the standard or passed headers
        :param url: the full url to retrieve.
        :param headers: optional headers to override the headers from get_headers()
        :return: the response object
        """
        LOG.debug("posting url: %s", url)
        session = self._get_session()

        headers = headers or self.get_headers()
        auth = auth or self.get_auth()
        if post_as_json:
            data = json.dumps(data, default=self.json_serializer)
        response = session.post(url, data=data, headers=headers, auth=auth,
                                verify=self.get_verification())
        response.raise_for_status()
        return response

    def get_verification(self):
        """
        Returns the value of verification.
        :return: True (Path_to_cacert in binary) / False
        """
        return self.settings.get('verify_ssl', True) in TrueValues

    def get_headers(self):
        """
        Returns the headers to be used by default in get() and post() methods
        :return: headers dict
        """
        return {}

    def get_auth(self):
        return None

    def authenticate(self):
        """
        Perform authentication to target service, if needed. Many APIs don't really support this.
        :return: Nothing
        """
        LOG.debug("%s has no authenticate() method.", self.__class__.__module__)

    def stop_sync(self):
        self.keep_going = False

    def sender(self, oomnitza_connector, rec):
        """
        This is data sender that should be executed by greenlet to make network IO operations non-blocking.

        :param oomnitza_connector:
        :param options:
        :param rec:
        :return:
        """

        if not (self.__filter__ is None or self.__filter__(rec)):
            LOG.info("Skipping record %r because it did not pass the filter.", rec)
            return

        converted_record = self.convert_record(rec)
        if not converted_record:
            LOG.info("Skipping record %r because it has not been converted properly", rec)
            return

        self.send_to_oomnitza(oomnitza_connector, converted_record)

    def is_authorized(self):
        """
        Check if authorized
        :return:
        """
        try:
            self.authenticate()
        except AuthenticationError as exp:
            LOG.error("Authentication failed: %r.", str(exp))
            return False
        except requests.exceptions.ConnectionError as exp:
            LOG.exception("Authentication Failed: %r.", str(exp))
            return False

        return True

    def perform_sync(self, oomnitza_connector, options):
        """
        This method controls the sync process. Called from the command line script to do the work.
        :param oomnitza_connector: the Oomnitza API Connector
        :param options: right now, always {}
        :return: boolean success
        """
        if not self.is_authorized():
            return

        limit_records = float(options.get('record_count', 'inf'))

        save_data = self.settings.get("__save_data__", False)

        if save_data:
            try:
                os.makedirs("./saved_data")
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                    pass
                else:
                    raise

        try:
            pool_size = self.settings['__workers__']

            connection_pool = Pool(size=pool_size)
            for index, record in enumerate(self._load_records(options)):

                if not self.keep_going:
                    break

                if save_data:
                    filename = "./saved_data/{}.json".format(str(index))
                    with open(filename, "w") as save_file:
                        LOG.info("Saving fetched payload data to %s.", filename)
                        json.dump(record, save_file, indent=2, default=self.json_serializer)

                if not isinstance(record, list):
                    record = [record]

                for rec in record:

                    if self.processed_records_counter < limit_records:

                        # increase records counter
                        self.processed_records_counter += 1
                        if not self.processed_records_counter % 10:
                            LOG.info("Processed %d records. Sent %d records to Oomnitza." % (self.processed_records_counter, self.sent_records_counter))

                        if not self.keep_going:
                            break

                        connection_pool.spawn(self.sender, *(oomnitza_connector, rec))

            connection_pool.join(timeout=60)  # set non-empty timeout to guarantee context switching in case of threading

            LOG.info("Finished! Processed %d records. %d records have been sent to Oomnitza" % (self.processed_records_counter, self.sent_records_counter))

            return True
        except RequestException as exp:
            raise ConfigError("Error loading records from %s: %s" % (self.MappingName, str(exp)))

    def _save_data(self, payload):
        filename = "./saved_data/oom.payload{0:0>3}.json".format(self.send_counter)
        LOG.info("Saving processed payload data to %s.", filename)
        with open(filename, 'w') as save_file:
            self.send_counter += 1
            json.dump(payload, save_file, indent=2, default=self.json_serializer)

    def _validate_insert_update_only(self, insert_only, update_only):
        if insert_only and update_only:
            raise ValueError('"insert_only" and "update_only" can not be both of True value')

    def _collect_payload(self, records):
        insert_only = bool(strtobool(self.settings.get('insert_only', '0')))
        update_only = bool(strtobool(self.settings.get('update_only', '0')))
        self._validate_insert_update_only(insert_only, update_only)
        payload = {
            "connector_name": self.MappingName,
            "connector_version": VERSION,
            "sync_field": list(filter(bool, map(str.strip, self.settings.get('sync_field', '').split(',')))),
            "records": records if isinstance(records, list) else [records],
            "portion": self.portion,
            "data_type": self.RecordType,
            "insert_only": insert_only,
            "update_only": update_only
        }
        return payload

    def send_to_oomnitza(self, oomnitza_connector, data):
        """
        Determine which method on the Oomnitza connector to call based on type of data.
        Can call:
            oomnitza_connector.(_test_)upload_assets
            oomnitza_connector.(_test_)upload_users
            oomnitza_connector.(_test_)upload_audit
        :param oomnitza_connector: the Oomnitza connector
        :param data: the data to send (either single object or list)
        :return: the results of the Oomnitza method call
        """
        payload = self._collect_payload(data)

        if self.settings.get("__save_data__"):
            try:
                self._save_data(payload)
            except:
                LOG.exception("Error saving data.")

        if self.settings['__testmode__']:
            result = oomnitza_connector.test_upload(payload)
        else:
            result = oomnitza_connector.upload(payload)
            self.sent_records_counter += 1

        return result

    def test_connection(self, options):
        """
        Here to support GUI Test Connection button.
        :param options: currently always {}
        :return: Nothing
        """
        # NOTE: not used for now, because we have deprecated GUI
        try:
            return self.do_test_connection(options)
        except Exception as exp:
            LOG.exception("Exception running %s.test_connection()." % self.MappingName)
            return {'result': False, 'error': 'Test Connection Failed: %s' % str(exp)}

    def do_test_connection(self, options):
        raise NotImplementedError

    def _load_records(self, options):
        """
        Performs the record retrieval of the records to be imported.
        :param options: currently always {}
        :return: nothing, but yields records wither singly or in a list
        """
        raise NotImplementedError

    def server_handler(self, body, wsgi_env, options):
        """
        Do the server side logic for the certain connector.
        :param wsgi_env: WSGI env dict
        :param body: request bode read from the
        :param options:
        :return:
        """
        raise NotImplementedError

    def convert_record(self, incoming_record):
        """
        Takes the record from the target and returns the data in the Oomnitza format.
        This is done using the self.field_mappings.
        :param incoming_record: the incoming record
        :return: the outgoing record
        """
        # LOG.debug("incoming_record = %r", incoming_record)
        return self._convert_record(incoming_record, self.field_mappings)

    def _convert_record(self, incoming_record, field_mappings):
        """
        Convert the passed incoming_record using passed field mappings.
        :param incoming_record: the incoming record, as a dict
        :param field_mappings: the field mappings to use
        :return: the outgoing record as a dict
        """
        outgoing_record = {}
        missing_fields = set()
        # subrecords = {}

        for field, specs in list(field_mappings.items()):
            # First, check if this is a subrecord. If so, re-enter _convert_record
            # LOG.debug("%%%% %r: %r", field, specs)
            # if field.startswith('subrecord.'):
            #     LOG.debug("**** processing subrecord %s: %r", field, specs)
            #     name = field.split('.', 1)[-1]
            #     if specs['source'] in incoming_record:
            #         subrecords[name] = self._convert_record(incoming_record[specs['source']], specs['mappings'])
            #     continue

            source = specs.get('source', None)
            if source:
                incoming_value = self.get_field_value(source, incoming_record)
            else:
                setting = specs.get('setting')
                if setting:
                    incoming_value = self.get_setting_value(setting)
                else:
                    hardcoded = specs.get('hardcoded', None)
                    if hardcoded is not None:
                        incoming_value = hardcoded
                    else:
                        raise RuntimeError("Field %s is not configured correctly.", field)

            converter = specs.get('converter', None)
            if converter:
                try:
                    incoming_value = self.apply_converter(converter, source or field, incoming_record, incoming_value)
                except Exception as exp:
                    LOG.exception("Failed to run converter: %s", converter)
                    incoming_value = None

            f_type = specs.get('type', None)
            if f_type:
                incoming_value = f_type(incoming_value)

            if specs.get('required', False) in TrueValues and not incoming_value:
                missing_fields.add(field)

            outgoing_record[field] = incoming_value

        # if subrecords:
        #     outgoing_record.update(subrecords)

        if missing_fields:
            LOG.warning("Record missing fields: %r. Incoming Record: %r", list(missing_fields), incoming_record)
            return None

        return outgoing_record

    def get_field_value(self, field, data, default=None):
        """
        Will return the field value out of data.
        Field can contain '.', which will be followed.
        :param field: the field name, can contain '.'
        :param data: the data as a dict, can contain sub-dicts
        :param default: the default value to return if field can't be found
        :return: the field value, or default.
        """
        return get_field_value(data, field, default)

    def get_setting_value(self, setting, default=None):
        """
        Nice helper to get settings.
        :param setting: the setting to return
        :param default: the default to return is the settings is not set.
        :return: the setting value, or default
        """
        return self.settings.get(setting, default)

    @classmethod
    def apply_converter(cls, converter_name, field, record, value):
        params = {}
        if ':' in converter_name:
            converter_name, args = converter_name.split(':', 1)
            for arg in args.split('|'):
                if '=' in arg:
                    k, v = arg.split('=', 1)
                else:
                    k, v = arg, True
                params[k] = v

        return Converter.run_converter(converter_name, field, record, value, params)


class UserConnector(BaseConnector):
    RecordType = 'users'

    def __init__(self, section, settings):
        super(UserConnector, self).__init__(section, settings)

        if 'POSITION' not in self.field_mappings:
            self.field_mappings['POSITION'] = {"setting": 'default_position'}

        if 'PERMISSIONS_ID' not in self.field_mappings:
            self.field_mappings['PERMISSIONS_ID'] = {"setting": 'default_role'}


class AssetsConnector(BaseConnector):
    RecordType = 'assets'
    OomnitzaBatchSize = 1
