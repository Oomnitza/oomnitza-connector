
import os
import sys
import requests
import json
import logging
import importlib
import pprint

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name
root_logger = logging.getLogger('')

LastInstalledHandler = None


def run_connector(oomnitza_connector, connector, options):
    global LastInstalledHandler
    if LastInstalledHandler:
        root_logger.removeHandler(LastInstalledHandler)
    LastInstalledHandler = logging.FileHandler("{}.log".format(connector['__name__']))
    LastInstalledHandler.setLevel(logging.INFO)
    root_logger.addHandler(LastInstalledHandler)

    conn = connector["__connector__"]
    try:
        conn.authenticate()
    except AuthenticationError as exp:
        logger.error("Authentication failure: %s", exp.message)
        return
    except requests.HTTPError:
        logger.exception("Error connecting to %s service.", connector['__name__'])
        return

    try:
        conn.perform_sync(oomnitza_connector, options)
    except requests.HTTPError:
        logger.exception("Error syncing data for %s service.", connector['__name__'])


class AuthenticationError(RuntimeError):
    pass


class BaseConnector(object):
    CaCert = os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), 'cacert.pem')
    Converters = {}
    FieldMappings = {}
    MappingName = "unnamed"
    OomnitzaBatchSize = 100

    TrueValues = ['True', 'true', '1', 'Yes', 'yes']
    FalseValues = ['False', 'false', '0', 'No', 'no']

    def __init__(self, settings):
        self.settings = {}
        ini_field_mappings = {}

        for key, value in settings.items():
            if key.startswith('mapping.'):
                # it is a field mapping from the ini
                field_name = key.split('.')[1].upper()
                # ToDo: validate mapping
                ini_field_mappings[field_name] = value
            # elif key.startswith('subrecord.'):
            #     ini_field_mappings[key] = value
            else:
                # first, simple copy for internal __key__ values
                if key.startswith('__') and key.endswith('__'):
                    self.settings[key] = value
                    continue

                try:
                    # grab the setting, which gets us the default for later
                    # but also makes sure we are not passed extra fields....
                    setting = self.Settings[key]
                except KeyError:
                    raise RuntimeError("Unknown setting %s." % key)

                if value:
                    self.settings[key] = value

        # loop over settings definitions, setting default values
        for key, setting in self.Settings.items():
            if not self.settings.get(key, None):
                default = setting.get('default', None)
                if default:
                    self.settings[key] = default
                else:
                    raise RuntimeError("Missing setting value for %s." % key)

        self.field_mappings = self.get_field_mappings(ini_field_mappings)
        if hasattr(self, "DefaultConverters"):
            for field, mapping in self.field_mappings.items():
                source = mapping.get('source', None)
                if source in self.DefaultConverters and 'converter' not in mapping:
                    mapping['converter'] = self.DefaultConverters[source]

        self._session = None

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
        server_mappings = self.settings['__oomnitza_connector__'].get_mappings(self.MappingName)

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

    def get(self, url, headers=None, auth=None):
        """
        Performs a HTTP GET against the passed URL using either the standard or passed headers
        :param url: the full url to retrieve.
        :param headers: optional headers to override the headers from get_headers()
        :return: the response object
        """
        logger.debug("getting url: %s", url)
        if not self._session:
            self._session = requests.Session()
        headers = headers or self.get_headers()
        auth = auth or self.get_auth()
        # logger.debug("headers: %r", headers)
        response = self._session.get(url, headers=headers, auth=auth,
                                     verify=self.settings.get('verify_ssl', True) in self.TrueValues)
        response.raise_for_status()
        return response

    def post(self, url, data, headers=None, auth=None):
        """
        Performs a HTTP GET against the passed URL using either the standard or passed headers
        :param url: the full url to retrieve.
        :param headers: optional headers to override the headers from get_headers()
        :return: the response object
        """
        logger.debug("posting url: %s", url)
        if not self._session:
            self._session = requests.Session()
        headers = headers or self.get_headers()
        auth = auth or self.get_auth()
        # logger.debug("headers: %r", headers)
        # logger.debug("payload = %s", json.dumps(data))
        response = self._session.post(url, data=json.dumps(data), headers=headers, auth=auth,
                                      verify=self.settings.get('verify_ssl', True) in self.TrueValues)
        response.raise_for_status()
        return response

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
        logger.warning("Unable to test authentication for %s", self.__class__.__module__)

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
            logger.error("Authentication failed: %r.", exp.message)
            return False
        except requests.exceptions.ConnectionError as exp:
            logger.exception("Authentication Failed: %r.", exp.message)
            return False

        record_count = options.get('record_count', None)
        limit_records = bool(record_count)
        records = []
        for record in self._load_records(options):
            if not isinstance(record, list):
                record = [record]

            for rec in record:
                converted = self.convert_record(rec)
                if converted:
                    records.append(converted)
                else:
                    logger.debug("Skipping record: %r", rec)

                if limit_records:
                    if record_count:
                        record_count -= 1
                        logger.info("Sending record %r to Oomnitza.", converted)
                        self.send_to_oomnitza(oomnitza_connector, converted)
                    else:
                        logger.info("Done sending limited records to Oomnitza.")
                        return True
                else:
                    if len(records) >= self.OomnitzaBatchSize:  # ToDo: make this dynamic
                        logger.info("sending %s records to oomnitza...", len(records))
                        self.send_to_oomnitza(oomnitza_connector, records)
                        records = []

        # do one final check for records which need to be sent
        if len(records):
            logger.info("sending final %s records to oomnitza...", len(records))
            self.send_to_oomnitza(oomnitza_connector, records)

        return True

    def send_to_oomnitza(self, oomnitza_connector, data):
        """
        Determine which method on the Oomnitza connector to call based on type of data
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
        result = method(data)
        # logger.debug("send_to_oomnitza result: %r", result)
        return result

    def test_connection(self, options):
        """
        Here to support GUI Test Connection button.
        :param options: currently always {}
        :return: Nothing
        """
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
        # logger.debug("incoming_record = %r", incoming_record)
        return self._convert_record(incoming_record, self.field_mappings)

    def _convert_record(self, incoming_record, field_mappings):
        """
        Convert the passed incoming_record using passed field mappings.
        :param incoming_record: the incoming record, as a dict
        :param field_mappings: the field mappings to use
        :return: the outgoing record as a dict
        """
        outgoing_record = {}
        # subrecords = {}

        for field, specs in field_mappings.items():
            # First, check if this is a subrecord. If so, re-enter _convert_record
            # logger.debug("%%%% %r: %r", field, specs)
            # if field.startswith('subrecord.'):
            #     logger.debug("**** processing subrecord %s: %r", field, specs)
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
                    if hardcoded:
                        incoming_value = hardcoded
                    else:
                        raise RuntimeError("Field %s is not configured correctly.", field)

            converter = specs.get('converter', None)
            if converter:
                incoming_value = self.apply_converter(converter, field, incoming_record, incoming_value)

            f_type = specs.get('type', None)
            if f_type:
                incoming_value = f_type(incoming_value)

            if specs.get('required', False) in self.TrueValues and not incoming_value:
                logger.info("Record missing %r, skipping: %r", field, incoming_record, incoming_record)
                return None

            outgoing_record[field] = incoming_value

        # if subrecords:
        #     outgoing_record.update(subrecords)

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
        converter = cls.Converters.get(converter_name, None)
        if not converter:
            # the converter has not been loaded yet, so load it and save it into cls.Converters
            mod = importlib.import_module("converters.{0}".format(converter_name))
            converter = mod.converter
            cls.Converters[converter_name] = converter
        return converter(field, record, value)


class UserConnector(BaseConnector):
    RecordType = 'users'

    def __init__(self, settings):
        super(UserConnector, self).__init__(settings)


class AssetConnector(BaseConnector):
    RecordType = 'assets'
    MappingName = None

    def __init__(self, settings):
        super(AssetConnector, self).__init__(settings)

    def send_to_oomnitza(self, oomnitza_connector, record):
        payload = {
            "integration_id": self.MappingName,
            "sync_field": self.settings['sync_field'],
            "assets": record
        }
        return super(AssetConnector, self).send_to_oomnitza(oomnitza_connector, payload)


class AuditConnector(BaseConnector):
    RecordType = 'audit'
    OomnitzaBatchSize = 10

    def __init__(self, settings):
        super(AuditConnector, self).__init__(settings)

    def send_to_oomnitza(self, oomnitza_connector, record):
        payload = {
            "agent_id": self.MappingName,
            "sync_field": self.settings['sync_field'],
            "computers": record
        }
        # pprint.pprint(record)
        return super(AuditConnector, self).send_to_oomnitza(oomnitza_connector, payload)

