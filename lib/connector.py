
import os
import sys
import requests
import json
import logging
import pprint
import errno

from requests.exceptions import HTTPError, RequestException

from utils.relative_path import relative_app_path

LOG = logging.getLogger("lib/connector")
root_logger = logging.getLogger('')

from .error import ConfigError, AuthenticationError
from .httpadapters import AdapterMap
from .converters import Converter
from .filter import DynamicException
from .version import VERSION

LastInstalledHandler = None


def run_connector(oomnitza_connector, connector, options):
    global LastInstalledHandler

    try:
        if LastInstalledHandler:
            root_logger.removeHandler(LastInstalledHandler)
        LastInstalledHandler = logging.FileHandler(relative_app_path("{}.log".format(connector['__name__'])))
        LastInstalledHandler.setLevel(logging.INFO)
        root_logger.addHandler(LastInstalledHandler)

        conn = connector["__connector__"]

        try:
            conn.authenticate()
        except AuthenticationError as exp:
            LOG.error("Authentication failure: %s", exp.message)
            return
        except requests.HTTPError:
            LOG.exception("Error connecting to %s service.", connector['__name__'])
            return

        try:
            conn.perform_sync(oomnitza_connector, options)
        except ConfigError as exp:
            LOG.error(exp.message)
        except requests.HTTPError:
            LOG.exception("Error syncing data for %s service.", connector['__name__'])
    except DynamicException as exp:
        LOG.error("Error running filter for %s: %s", connector['__name__'], exp)
    except:  # pylint:disable=broad-except
        LOG.exception("Unhandled error in run_connector for %s", connector['__name__'])


def stop_connector(connector):
    try:
        conn = connector["__connector__"]
        conn.stop_sync()
    except Exception as ex:
        LOG.exception(str(ex))


class BaseConnector(object):
    Converters = {}
    FieldMappings = {}
    MappingName = "unnamed"
    OomnitzaBatchSize = 100
    BuiltinSettings = ('ssl_protocol',)

    OomnitzaConnector = None

    TrueValues = ['True', 'true', '1', 'Yes', 'yes', True]
    FalseValues = ['False', 'false', '0', 'No', 'no', False]
    CommonSettings = {
        'verify_ssl':   {'order': 0, 'default': "True"},
        'cacert_file':  {'order': 1, 'default': ""},
        'cacert_dir':   {'order': 2, 'default': ""},
        'env_password': {'order': 3, 'default': ""},
        'ssl_protocol': {'order': 4, 'default': ""},
    }

    def __init__(self, section, settings):
        self.section = section
        self.settings = {'VERSION': VERSION}
        self.keep_going = True
        ini_field_mappings = {}
        self.__filter__ = None
        self.send_counter = 0

        for key, value in settings.items():
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

                if key in self.Settings:
                    setting = self.Settings[key]
                elif key in self.CommonSettings:
                    setting = self.CommonSettings[key]
                else:
                    # raise ConfigError("Invalid setting %r." % key)
                    LOG.warning("Invalid setting in %r section: %r." % (section, key))
                    continue

                self.settings[key] = value

        # loop over settings definitions, setting default values
        for key, setting in self.Settings.items():
            if not self.settings.get(key, None):
                default = setting.get('default', None)
                if default is None:
                    raise RuntimeError("Missing setting value for %s." % key)
                else:
                    self.settings[key] = default

        self.field_mappings = self.get_field_mappings(ini_field_mappings)
        if hasattr(self, "DefaultConverters"):
            for field, mapping in self.field_mappings.items():
                source = mapping.get('source', None)
                if source in self.DefaultConverters and 'converter' not in mapping:
                    mapping['converter'] = self.DefaultConverters[source]

        self._session = None

        if section == 'oomnitza' and not BaseConnector.OomnitzaConnector:
            BaseConnector.OomnitzaConnector = self

    def get_field_mappings(self, extra_mappings):
        mappings = self.get_default_mappings()  # loads from Connector object or Oomnitza mapping api

        for field, mapping in extra_mappings.items():
            if field not in mappings:
                mappings[field] = mapping
            else:
                for key, value in mapping.items():
                    mappings[field][key] = value

        return mappings

    def get_default_mappings(self):
        """
        Returns the default mappings, as defined in the class level FieldMappings dict.
        It supports loading mappings from Oomnitza API.
        :return: the default mappings
        """
        # Connector mappings are stored in Oomnitza, so get them.
        default_mappings = self.FieldMappings.copy()
        server_mappings = self.settings['__oomnitza_connector__'].get_mappings(
            # If '.' is in self.section, it is something like 'Casper.MDM', so use the section name to pull in the maps.
            '.' in self.section and self.section or self.MappingName
        )

        for source, fields in server_mappings.items():
            if isinstance(fields, basestring):
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
        for key, value in sorted(cls.Settings.items(), key=lambda t: t[1]['order']):
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
            if protocol:
                LOG.info("Forcing SSL Protocol to: %s", protocol)
                if protocol.lower() in AdapterMap:
                    self._session.mount("https://", AdapterMap[protocol.lower()]())
                else:
                    raise RuntimeError("Invalid value for ssl_protocol: %r. Valid values are %r.",
                                       protocol, list(set(AdapterMap.keys())))
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
        # LOG.debug("headers: %r", headers)
        # LOG.debug("payload = %s", json.dumps(data))
        if post_as_json:
            data = json.dumps(data)
        response = session.post(url, data=data, headers=headers, auth=auth,
                                verify=self.get_verification())
        response.raise_for_status()
        return response

    def get_verification(self):
        """
        Returns the value of verification.
        :return: True (Path_to_cacert in binary) / False
        """
        verify_ssl = self.settings.get('verify_ssl', True) in self.TrueValues
        if verify_ssl:
            # 'frozen' is added by PyInstaller which is necessary to learn at run-time
            # whether the app is running from source or part of bundle
            # Please refer to http://pythonhosted.org/PyInstaller/#adapting-to-being-frozen
            if getattr(sys, 'frozen', False):
                # '_MEIPASS' is added by PyInstaller which is the path variable to temp directory at run-time
                # and cacert.pem (Certified Authority) is included in building binary time (defined in PyInstaller spec)
                return os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), 'cacert.pem')
            else:
                return True
        else:
            return False


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

    def perform_sync(self, oomnitza_connector, options):
        """
        This method controls the sync process. Called from the command line script to do the work.
        :param oomnitza_connector: the Oomnitza API Connector
        :param options: right now, always {}
        :return: boolean success
        """
        try:
            self.authenticate()
        except AuthenticationError as exp:
            LOG.error("Authentication failed: %r.", exp.message)
            return False
        except requests.exceptions.ConnectionError as exp:
            LOG.exception("Authentication Failed: %r.", exp.message)
            return False

        record_count = options.get('record_count', None)
        limit_records = bool(record_count)
        records = []
        try:
            for record in self._load_records(options):
                if not isinstance(record, list):
                    record = [record]

                for rec in record:
                    if not self.keep_going:
                        break  # break out of "for rec in record"

                    if not(self.__filter__ is None or self.__filter__(rec)):
                        LOG.info("Skipping record because it did not pass the filter.")
                        continue
                    converted = self.convert_record(rec)
                    if converted:
                        records.append(converted)
                    else:
                        LOG.debug("Skipping record: %r", rec)

                    if limit_records:
                        if record_count:
                            record_count -= 1
                            LOG.info("Sending record %r to Oomnitza.", converted)
                            self.send_to_oomnitza(oomnitza_connector, converted, options)
                        else:
                            LOG.info("Done sending limited records to Oomnitza.")
                            return True
                    else:
                        if len(records) >= self.OomnitzaBatchSize:  # ToDo: make this dynamic
                            LOG.info("sending %s records to oomnitza...", len(records))
                            self.send_to_oomnitza(oomnitza_connector, records, options)
                            records = []

                if not self.keep_going:
                    LOG.warning("Upload process has been terminated forcibly.")
                    break  # break out of "for record in self._load_records(options)"

            # do one final check for records which need to be sent
            if len(records):
                LOG.info("sending final %s records to oomnitza...", len(records))
                self.send_to_oomnitza(oomnitza_connector, records, options)

            return True
        except RequestException as exp:
            raise ConfigError("Error loading records from %s: %s" % (self.MappingName, exp.message))

    def send_to_oomnitza(self, oomnitza_connector, data, options):
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
        method = getattr(
            oomnitza_connector,
            "{1}upload_{0}".format(
                self.RecordType,
                self.settings["__testmode__"] and '_test_' or ''
            )
        )
        if self.settings.get("__save_data__", False):
            try:
                try:
                    os.makedirs("./saved_data")
                except OSError as exc:
                    if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                        pass
                    else:
                        raise

                filename = "./saved_data/oom.payload{0:0>3}.json".format(self.send_counter)
                LOG.info("Saving payload data to %s.", filename)
                with open(filename, 'w') as save_file:
                    self.send_counter += 1
                    json.dump(data, save_file, indent=2)
            except:
                LOG.exception("Error saving data.")

        result = method(data, options)
        # LOG.debug("send_to_oomnitza result: %r", result)
        return result

    def test_connection(self, options):
        """
        Here to support GUI Test Connection button.
        :param options: currently always {}
        :return: Nothing
        """
        try:
            return self.do_test_connection(options)
        except Exception as exp:
            LOG.exception("Exception running %s.test_connection()." % self.MappingName)
            return {'result': False, 'error': 'Test Connection Failed: %s' % exp.message}

    def do_test_connection(self, options):
        raise NotImplemented

    def _load_records(self, options):
        """
        Performs the record retrieval of the records to be imported.
        :param options: currently always {}
        :return: nothing, but yields records wither singly or in a list
        """
        raise NotImplemented

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

        for field, specs in field_mappings.items():
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
                incoming_value = self.apply_converter(converter, source or field, incoming_record, incoming_value)

            f_type = specs.get('type', None)
            if f_type:
                incoming_value = f_type(incoming_value)

            if specs.get('required', False) in self.TrueValues and not incoming_value:
                LOG.debug("Record missing %r. Record = %r", field, incoming_record)
                missing_fields.add(field)

            outgoing_record[field] = incoming_value

        # if subrecords:
        #     outgoing_record.update(subrecords)

        if missing_fields:
            LOG.warning("Record missing fields: %r. Incoming Record: %r", list(missing_fields), incoming_record)
            return None

        return outgoing_record


    @classmethod
    def get_field_value(cls, field, data, default=None):
        """
        Will return the field value out of data.
        Field can contain '.', which will be followed.
        :param field: the field name, can contain '.'
        :param data: the data as a dict, can contain sub-dicts
        :param default: the default value to return if field can't be found
        :return: the field value, or default.
        """
        if not data:
            return default

        if '.' in field:
            current, rest = field.split('.', 1)
            if isinstance(data, list) and current.isdigit():
                return cls.get_field_value(rest, data[int(current)], default)
            if current in data:
                return cls.get_field_value(rest, data[current], default)
            return default

        return data.get(field, default)

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

        if self.settings['default_position'].lower() == 'unused':
            self.normal_position = True
        else:
            self.normal_position = False

        if 'POSITION' not in self.field_mappings and not self.normal_position:
            self.field_mappings['POSITION'] = {"setting": 'default_position'}

    def send_to_oomnitza(self, oomnitza_connector, record, options):
        if self.normal_position:
            options['normal_position'] = True

        return super(UserConnector, self).send_to_oomnitza(oomnitza_connector, record, options)


class AssetConnector(BaseConnector):
    RecordType = 'assets'
    MappingName = None

    def __init__(self, section, settings):
        super(AssetConnector, self).__init__(section, settings)

        if self.settings['sync_field'] not in self.field_mappings:
            raise ConfigError("Sync field %r is not included in the %s mappings. No records can be synced. "
                              "Please check your field mappings under System Settings > Connectors then select "
                              "'%s' from the drop down." %
                              (self.settings['sync_field'], self.MappingName, self.MappingName))

    def send_to_oomnitza(self, oomnitza_connector, record, options):
        payload = {
            "integration_id": self.MappingName,
            "sync_field": self.settings['sync_field'],
            "assets": record,
            "update_only": self.settings.get('update_only', "False"),
        }
        return super(AssetConnector, self).send_to_oomnitza(oomnitza_connector, payload, options)


class AuditConnector(BaseConnector):
    RecordType = 'audit'
    OomnitzaBatchSize = 10

    def __init__(self, section, settings):
        super(AuditConnector, self).__init__(section, settings)

        if self.settings['sync_field'] not in self.field_mappings:
            raise ConfigError("Sync field %r is not included in the %s mappings. No records can be synced. "
                              "Please check your field mappings under System Settings > Connectors then select "
                              "'%s' from the drop down." %
                              (self.settings['sync_field'], self.MappingName, self.MappingName))

    def send_to_oomnitza(self, oomnitza_connector, record, options):
        payload = {
            "agent_id": self.MappingName,
            "sync_field": self.settings['sync_field'],
            "computers": record,
            "update_only": self.settings.get('update_only', "False"),
        }
        # pprint.pprint(record)
        return super(AuditConnector, self).send_to_oomnitza(oomnitza_connector, payload, options)

