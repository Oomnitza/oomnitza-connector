import copy
import errno
import json
import xmltodict
import logging
import os
from datetime import date, datetime
from distutils.util import strtobool
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests
from constants import FATAL_ERROR_FLAG, ConfigFieldType
from gevent.pool import Pool
from lib import TrueValues
from lib.converters import Converter
from lib.error import AuthenticationError, ConfigError
from lib.filter import DynamicException
from lib.httpadapters import AdapterMap, retries
from lib.logger import ContextLoggingAdapter
from lib.renderer import _RawValue
from lib.strongbox import Strongbox, StrongboxBackend
from lib.version import VERSION
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from utils.data import get_field_value


# noinspection PyBroadException
def response_to_object(response_text):
    """
    Try to represent the response as the native object from the JSON- or XML-based response
    """
    try:
        return json.loads(response_text)
    except:
        try:
            return xmltodict.parse(response_text)
        except:
            return response_text

def run_connector(connector_cfg, options):

    LOG = logging.getLogger(connector_cfg['__name__'])

    try:
        connector_instance = connector_cfg["__connector__"]

        try:
            connector_instance.authenticate()
        except AuthenticationError as exp:
            LOG.error("Authentication failure: %s", str(exp))
            return
        except requests.HTTPError:
            LOG.exception("Error connecting to %s service.", connector_cfg['__name__'])
            return

        try:
            connector_instance.perform_sync(options)
        except ConfigError as exp:
            LOG.error(exp)
        except requests.HTTPError:
            LOG.exception("Error syncing data for %s service.", connector_cfg['__name__'])
    except DynamicException as exp:
        LOG.error("Error running filter for %s: %s", connector_cfg['__name__'], str(exp))
    except:  # pylint:disable=broad-except
        LOG.exception("Unhandled error in run_connector for %s", connector_cfg['__name__'])

bad_keywords: List[str] = [
    'not', 'self', 'False', 'None', 'True', 'false', 'true',
]
keyword_replace: Dict[str, str] = {kw: f'_{kw.upper()}_' for kw in bad_keywords}


def sanitize_jinja_call_args(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize the data passed to jinja render."""
    return {keyword_replace.get(k, k): v for k, v in data.items()}


def replace_illegal_chars(key: str) -> str:
    """Replace characters in keys that would not be valid python names."""
    replacements = {
        '.': '_DOT_',
        ':': '_COLON_',
        '-': '_DASH_',
        '#': '_HASH_',
        '$': '_DOLLAR_',
        '@': '_AT_',
        '/': '_SLASH_',
        '*': '_STAR_',
    }
    new_key = key
    for old, new in replacements.items():
        new_key = new_key.replace(old, new)
    return new_key


def escape_illegal_keys(incoming_record: Dict[str, Any]) -> Dict[str, Any]:
    """Replace keys in the root of the incoming_record with valid python names."""
    return {replace_illegal_chars(key): value for key, value in incoming_record.items()}


class BaseConnector(object):

    class ManagedConnectorProcessingException(Exception):
        """
        Special exception used to be raised in certain cases hen in the middle of the portion processing
        for the managed connector. In general when e are facing this issue we have to push an error to the cloud
        instead of the ready to process data
        """
        message_template = ''

        def __init__(self, **kwargs):
            message = self.message_template.format(**kwargs)
            super().__init__(message)

    class ManagedConnectorRecordConversionException(ManagedConnectorProcessingException):
        """
        Special exception used to be raised in certain cases when the given value
        cannot be presented according to the given managed connector mapping template
        """
        message_template = 'Failed to process the mapping value: {source}. The error is: {error}'

    class ManagedConnectorListGetInBeginningException(ManagedConnectorProcessingException):
        """
        Special exception used to be raised in certain cases when in the very beginning of processing
        the managed connector has failed to fetch the first page of data
        """
        message_template = 'Failed to fetch the first block of data. The error is: {error}. The further processing is impossible'

    class ManagedConnectorListGetEmptyInBeginningException(ManagedConnectorProcessingException):
        """
        Special exception used to be raised in certain cases when in the very beginning of processing
        the managed connector has received a empty first page of data
        """
        message_template = 'The first block of data was empty.'

    class ManagedConnectorListGetInMiddleException(ManagedConnectorProcessingException):
        """
        Special exception used to be raised in certain cases when in the middle of processing
        the managed connector has failed to fetch the new page of data
        """
        message_template = 'Failed to fetch the next block of data. The error is: {error}. The further processing is impossible'

    class ManagedConnectorDetailsGetException(ManagedConnectorProcessingException):
        """
        Special exception used to be raised in certain cases when in the middle of processing
        the managed connector has failed to fetch the details of the entity
        """
        message_template = 'Failed to fetch the details of a single item from the block. The error is: {error}'

    class ManagedConnectorSoftwareGetException(ManagedConnectorProcessingException):
        """
        Special exception used to be raised in certain cases when in the middle of processing
        the managed connector has failed to fetch the software info for the entity
        """
        message_template = 'Failed to fetch the software information. The error is: {error}'

    class ManagedConnectorSaaSGetException(ManagedConnectorProcessingException):
        """
        Special exception used to be raised in certain cases when in the middle of processing
        the managed connector has failed to fetch the software info for the entity
        """
        message_template = 'Failed to fetch the saas information. The error is: {error}'

    class ManagedConnectorListMaxIterationException(ManagedConnectorProcessingException):
        """
        Special exception to be raised in cases when the processing of a managed connector
        has iterated for MAX_ITERATIONS (1000 iterations) and would spin forever otherwise.
        """
        message_template = 'Connector exceeded processing limit. The error is: {error}'

    ConnectorID = None
    Settings = {}
    RecordType = None
    Converters = {}
    FieldMappings = {}
    MappingName = "unnamed"
    OomnitzaConnector = None
    Loggers = {}

    CommonSettings = {
        'verify_ssl':     {'order': 0, 'default': "True"},
        'cacert_file':    {'order': 1, 'default': ""},
        'cacert_dir':     {'order': 2, 'default': ""},
        'ssl_protocol':   {'order': 3, 'default': ""},
        'use_server_map': {'order': 4, 'default': "True"},
        'only_if_filled': {'order': 5, 'default': ""},
        'dont_overwrite': {'order': 6, 'default': ""},
        'insert_only':    {'order': 7, 'default': "False"},
        'update_only':    {'order': 8, 'default': "False"},
        'sync_field':     {'order': 9},
        'vault_keys':     {'order': 10, 'default': ""},
        'vault_backend':  {'order': 11, 'default': StrongboxBackend.KEYRING},
        'vault_alias':    {'order': 12, 'default': ""},
        'user_pem_file':  {'order': 13, 'default': ""}
    }

    def get_connector_name(self):
        """ Return connector name to be used for logging. """
        return self.connector_name

    def is_oomnitza_connector(self):
        return BaseConnector.OomnitzaConnector == self        

    @property
    def logger(self):
        """
        Return context based logger for a given connector name

        We cannot make the logger assignment in 
        the __init__ method due to serialization issues
        """
        name = self.get_connector_name()
        logger = BaseConnector.Loggers.get(name)
        if not logger:
            logger = ContextLoggingAdapter(logging.getLogger(name), self.context_id)
            BaseConnector.Loggers[name] = logger

        return logger

    @staticmethod
    def gen_portion_id():
        return str(uuid4())

    def __init__(self, section, settings):
        self.processed_records_counter = 0.
        self.sent_records_counter = 0.
        self.section = section
        self.settings = {'VERSION': VERSION}
        self.keep_going = True
        self.ini_field_mappings = {}
        self.__filter__ = None
        self.send_counter = 0
        self._session = None
        self.portion = self.gen_portion_id()
        self._cached_credential_details = None

        self.context_id = ContextLoggingAdapter.generate_unique_context_id()
        
        connector_name = self.MappingName.lower().replace('-', '_')
        self.connector_name = f"connectors/{connector_name}"
        
        for key, value in list(settings.items()):
            if key.startswith('mapping.'):
                # it is a field mapping from the ini
                field_name = key.split('.')[1].upper()
                # ToDo: validate mapping
                self.ini_field_mappings[field_name] = value
            # elif key.startswith('subrecord.'):
            #     ini_field_mappings[key] = value
            elif key == '__filter__':
                self.__filter__ = value
            else:
                # first, simple copy for internal __key__ values
                if key.startswith('__') and key.endswith('__'):
                    self.settings[key] = value
                    continue

                if key not in self.Settings and key not in self.CommonSettings:
                    # Should this be a warning?
                    self.logger.debug("Extra line in %r section: %r." % (section, key))
                    continue

                self.settings[key] = value

        backend_name = settings.get('vault_backend', StrongboxBackend.KEYRING)
        secret_alias = settings.get("vault_alias") or section
        self._strongbox = Strongbox(secret_alias, backend_name)
        self._preload_secrets()

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

        self.field_mappings = self.get_field_mappings(self.ini_field_mappings)
        if hasattr(self, "DefaultConverters"):
            for field, mapping in list(self.field_mappings.items()):
                source = mapping.get('source', None)
                if source in self.DefaultConverters and 'converter' not in mapping:
                    mapping['converter'] = self.DefaultConverters[source]

        if section == 'oomnitza' and not BaseConnector.OomnitzaConnector:
            BaseConnector.OomnitzaConnector = self

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

    def get_managed_mapping_from_oomnitza(self):
        """
        Connect to the cloud for the mapping (new, managed connectors)
        """
        return self.OomnitzaConnector.get_mappings_for_managed(self.ConnectorID)

    def get_mapping_from_oomnitza(self):
        """
        Connect to the cloud for the mapping (old, non-managed connectors)
        """
        return self.OomnitzaConnector.get_mappings(self.MappingName)

    def get_default_mappings(self):
        """
        Returns the default mappings, as defined in the class level FieldMappings dict.
        It supports loading mappings from Oomnitza API.
        :return: the default mappings
        """
        # NOTE: Connector mappings are stored in Oomnitza, so get them.
        default_mappings = copy.deepcopy(self.FieldMappings)

        if self.is_managed:

            server_mappings = self.get_managed_mapping_from_oomnitza()
            for field, specification in server_mappings.items():
                default_mappings[field] = {}

                if specification['type'] == 'attribute':
                    # NOTE: Fetch the value for the attribute from the data source
                    default_mappings[field]['source'] = specification['value']

                elif specification['type'] == 'value':
                    # NOTE: The value for the attribute is hardcoded and does not relate to the data source
                    default_mappings[field]['hardcoded'] = specification['value']

                elif specification['type'] in ('catalog_input', 'credential_input'):
                    # NOTE: Mappings for synthetic inputs like fields from software catalog or credential info
                    default_mappings[field]['extra_input'] = {
                        'type': specification['type'],
                        'value': specification['value']
                    }

        else:
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
                self.logger.info("Forcing SSL Protocol to: %s", protocol)
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
        session = self._get_session()
        headers = headers or self.get_headers()
        auth = auth or self.get_auth()

        if self.is_oomnitza_connector():
            # Reduce logging verbosity
            self.logger.debug("Issuing GET %s", url)
        else:
            self.logger.info("Issuing GET %s", url)
                    
        response = session.get(url, headers=headers, auth=auth,
                               verify=self.get_verification())

        try:
            response.raise_for_status()
        except Exception as ex:
            self.logger.error('Encounterd an exception. Reason [%s]', str(ex))                    
            raise ex
            
        self.logger.debug('Response code [%s]', response.status_code)                    
        return response

    def post(self, url, data, headers=None, auth=None, post_as_json=True):
        """
        Performs a HTTP GET against the passed URL using either the standard or passed headers
        :param url: the full url to retrieve.
        :param headers: optional headers to override the headers from get_headers()
        :return: the response object
        """
        session = self._get_session()
        headers = headers or self.get_headers()
        auth = auth or self.get_auth()
        
        if post_as_json:
            data = json.dumps(data, default=self.json_serializer)
            
        if self.is_oomnitza_connector():
            # Reduce logging verbosity
            self.logger.debug("Issuing GET %s", url)
        else:            
            self.logger.info("Issuing POST %s", url)
            
        response = session.post(url, data=data, headers=headers, auth=auth,
                                verify=self.get_verification())
        
        try:
            response.raise_for_status()
        except Exception as ex:
            self.logger.error('Encounterd an exception. Reason [%s]', str(ex))                    
            raise ex
            
        self.logger.debug('Response code [%s]', response.status_code)                    
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
        self.logger.debug("%s has no authenticate() method.", self.__class__.__module__)

    def stop_sync(self):
        self.keep_going = False

    def sender(self, rec, explicit_error):
        """
        This is data sender that should be executed by greenlet to make network IO operations non-blocking.
        """
        if explicit_error:
            self.send_to_oomnitza(rec, error=explicit_error)
            return

        if not (self.__filter__ is None or self.__filter__(rec)):
            self.logger.info("Skipping record %r because it did not pass the filter.", rec)
            return

        try:
            converted_record = self.convert_record(rec)
        except self.ManagedConnectorRecordConversionException as e:
            # we have failed to convert the record - issue with the mapping?
            self.send_to_oomnitza(rec, error=str(e))
        else:
            if not converted_record:
                self.logger.info("Skipping record %r because it has not been converted properly", rec)
                return
            self.send_to_oomnitza(converted_record)

    def is_authorized(self):
        """
        Check if authorized
        :return:
        """
        try:
            self.authenticate()
        except AuthenticationError as exp:
            self.logger.error("Authentication failed: %r.", str(exp))
            return False
        except requests.exceptions.ConnectionError as exp:
            self.logger.exception("Authentication Failed: %r.", str(exp))
            return False

        return True

    @property
    def is_managed(self):
        # used to represent the current connector is "managed"
        return self.ConnectorID and hasattr(self, 'jinja_string_env')

    @property
    def is_media_export(self):
        return self.is_managed and hasattr(self, 'folder_path')

    def finalize_processed_portion(self):
        self.OomnitzaConnector.finalize_portion(self.portion)

    def perform_sync(self, options):
        """
        This method controls the sync process. Called from the command line script to do the work.
        :param options: right now, always {}
        :return: boolean success
        """
        if not self.is_authorized():
            return

        limit_records = float(options.get('record_count', 'inf'))

        save_data = self.settings.get("__save_data__", False)

        if save_data:
            try:
                # TODO exists_ok=True
                os.makedirs("./saved_data")
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                    pass
                else:
                    raise

        try:
            pool_size = self.settings['__workers__']
            if pool_size == 0:
                # do not use gevent at all, for example for the testing
                connection_pool = None
            else:
                connection_pool = Pool(size=pool_size)
            for index, record in enumerate(self._load_records(options)):

                explicit_error = None
                if isinstance(record, tuple) and len(record) == 2:
                    # the first item here is the actual record and the second one is the explicit error
                    # we want to push to the cloud
                    record, explicit_error = record

                if not self.keep_going:
                    break

                if save_data:
                    filename = "./saved_data/{}.json".format(str(index))
                    with open(filename, "w") as save_file:
                        self.logger.info("Saving fetched payload data to %s.", filename)
                        json.dump(record, save_file, indent=2, default=self.json_serializer)

                if not isinstance(record, list):
                    record = [record]

                for rec in record:

                    if self.processed_records_counter < limit_records:

                        # increase records counter
                        self.processed_records_counter += 1
                        if not self.processed_records_counter % 10:
                            msg = (
                                f"Processed {self.processed_records_counter} record(s) from the source. "
                                f"Sent {self.sent_records_counter} record(s) to the destination."
                            )
                            self.logger.info(msg)

                        if not self.keep_going:
                            break

                        if connection_pool:
                            connection_pool.spawn(self.sender, *(rec, explicit_error))

                        else:
                            self.sender(rec, explicit_error)

                        # only 10 records for test connector run
                        if bool(self.settings.get('test_run')) and self.processed_records_counter == 10:
                            self.stop_sync()

            if connection_pool:
                connection_pool.join(timeout=30)  # set non-empty timeout to guarantee context switching in case of threading

            # at the end explicitly finalize the portion
            self.finalize_processed_portion()

            if not (self.is_media_export and not self.processed_records_counter):
                # it is known that the media_export connectors might have no items to process 
                # most of the time, so lets not spam the messages to the stdout and 
                # log only when we have at least one file processed
                msg = (
                    f"Finished! Processed {self.processed_records_counter} record(s). "
                    f"{self.sent_records_counter} record(s) have been sent to the destination"
                )
                self.logger.info(msg)

            return True
        except RequestException as exp:
            raise ConfigError("Error loading records from %s: %s" % (self.MappingName, str(exp)))

    def _save_data(self, payload):
        filename = "./saved_data/oom.payload{0:0>3}.json".format(self.send_counter)
        self.logger.info("Saving processed payload data to %s.", filename)
        with open(filename, 'w') as save_file:
            self.send_counter += 1
            json.dump(payload, save_file, indent=2, default=self.json_serializer)

    def _validate_insert_update_only(self, insert_only, update_only):
        if insert_only and update_only:
            raise ValueError('"insert_only" and "update_only" can not be both of True value')

    def get_multi_str_input_value(self):
        inputs_from_cloud = getattr(self, 'inputs_from_cloud', None)
        if not inputs_from_cloud:
            return

        for input_value in inputs_from_cloud.values():
            if input_value.get('type') == ConfigFieldType.MULTI_STR:
                return input_value.get('value')

    def _collect_payload(self, records, error, is_fatal=False):
        insert_only = bool(strtobool(self.settings.get('insert_only', '0')))
        update_only = bool(strtobool(self.settings.get('update_only', '0')))
        self._validate_insert_update_only(insert_only, update_only)
        payload = {
            "connector_version": VERSION,
            "sync_field": list(filter(bool, map(str.strip, self.settings.get('sync_field', '').split(',')))),
            "records": records if isinstance(records, list) else [records],
            "portion": self.portion,
            "data_type": self.RecordType,
            "insert_only": insert_only,
            "update_only": update_only,
            "error": error,
            "test_run": bool(self.settings.get('test_run')),
            "multi_str_input_value": self.get_multi_str_input_value()
        }
        # if we have the exact ID of the `service` entity at the DSS side - use it within the payload,
        # otherwise use the name set as the `MappingName`; back compatibility with the `upload` mode for the non-managed connectors
        if self.is_managed:
            payload['connector_id'] = self.ConnectorID
        else:
            payload['connector_name'] = self.MappingName

        if is_fatal:
            payload['error_type'] = FATAL_ERROR_FLAG

        return payload

    def send_to_oomnitza(self, data, error=None, is_fatal=False):
        """
        Determine which method on the Oomnitza connector to call based on type of data.

        :param data: the data to send (either single object or list)
        :param error: optional error message as the clear mark we must not process this item, but immediately accept this and store as the error
        :param is_fatal: a flag indicating the type of error and that the connector has stopped
        :return: the results of the Oomnitza method call
        """
        payload = self._collect_payload(data, error, is_fatal)

        if self.settings.get("__save_data__"):
            try:
                self._save_data(payload)
            except:
                self.logger.exception("Error saving data.")

        if self.settings['__testmode__']:
            result = self.OomnitzaConnector.test_upload(payload)
        else:
            result = self.OomnitzaConnector.upload(payload)
            self.sent_records_counter += 1

        return result

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
        for field, specs in list(field_mappings.items()):
            source = specs.get('source', None)
            extra_input = specs.get('extra_input', None)

            if source or extra_input:
                if self.is_managed:
                    try:
                        if source:
                            incoming_value = self.get_field_value_managed(source, escape_illegal_keys(incoming_record))
                        else:
                            incoming_value = self.get_extra_input_value(extra_input)

                    except Exception as e:
                        self.logger.exception('Failed to render the value given in mapping')
                        raise self.ManagedConnectorRecordConversionException(source=source, error=str(e))
                else:
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
                    self.logger.exception("Failed to run converter: %s", converter)
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
            self.logger.warning("Record missing fields: %r. Incoming Record: %r", list(missing_fields), incoming_record)
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

    # noinspection PyUnresolvedReferences
    def get_field_value_managed(self, field: str, data: dict):
        """
        Implement the value retrieval support for the managed connectors using the Jinja2 templating engine
        """
        if any(
            (
                self.jinja_native_env.block_start_string in field,
                self.jinja_native_env.block_end_string in field,
                self.jinja_native_env.variable_start_string in field,
                self.jinja_native_env.variable_end_string in field
            )
        ):
            # if the field definition contains the Jinja env control symbols - then do nothing
            field_template = field
        else:
            # fallback / simplification compatibility, treat the incoming value as the jinja2 variable
            field_template = self.jinja_native_env.variable_start_string + field + self.jinja_native_env.variable_end_string

        value = self.jinja_native_env.from_string(field_template).render(
            **sanitize_jinja_call_args(data)
        )

        if isinstance(value, _RawValue):
            return value.render()

        return value

    # noinspection PyUnresolvedReferences
    def get_extra_input_value(self, extra_inputs: str) -> Optional[str]:
        """
        Implement the value retrieval support for the managed connectors using the Jinja2 templating engine
        """
        input_type = extra_inputs['type']
        input_value = extra_inputs['value']

        value = None

        if input_type == 'catalog_input':
            value = self.render_to_string(self.inputs_from_cloud.get(input_value, {}).get('value'))

        elif input_type == 'credential_input':

            if not self._cached_credential_details:
                credential_id = self.settings['saas_authorization']['credential_id']
                self._cached_credential_details = self.OomnitzaConnector.get_credential_details(credential_id)

            value = self._cached_credential_details.get('name') if self._cached_credential_details else None

        return value

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
