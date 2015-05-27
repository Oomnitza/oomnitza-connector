import os
import sys
import json
import ConfigParser
import importlib
import pkgutil
import shutil
import logging
import logging.config
import pprint

from utils.relative_path import relative_path
from utils.relative_path import relative_app_path
from lib.connector import AuthenticationError

LOG = logging.getLogger(__name__)  # pylint:disable=invalid-name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from .filter import parse_filter
from .converters import Converter
from .error import ConfigError


def generate_ini_file(args):
    # take a backup of we will be overwriting a file.
    if os.path.exists(args.ini):
        shutil.move(args.ini, args.ini+'.bak')

    # write out the ini file.
    with open(args.ini, 'w') as ini_file:
        ini_file.write(get_default_ini())

    print "{0} has been generated.".format(args.ini)


class FilterConverter(object):
    def __init__(self, name, filter_str):
        self._name = name
        self._filter_str = filter_str

        self._filter = parse_filter(self._filter_str)

        Converter.register_converter(self._name, self)

    def __call__(self, field, record, value, params):
        LOG.debug("running FilterConverter: %s", self._name)
        result = self._filter(record)
        return self._filter.Environment.get('result', {}).get('value', None)


def parse_config(args):
    """
    Parse connector configuration and generate a result in dictionary
    format which includes integration names and the required info for
    pulling out data
    """
    connectors = {}
    try:
        config = ConfigParser.SafeConfigParser()
        if not os.path.isfile(args.ini):
            # The config file does not yet exist, so generate it.
            generate_ini_file(args)

        config.read(args.ini)
        for section in config.sections():
            cfg = {}
            if section == 'converters':
                for name, filter_str in config.items('converters'):
                    FilterConverter(name, filter_str)
            elif section == 'oomnitza' or config.has_option(section, 'enable') and config.getboolean(section, 'enable'):
                if not connectors and section != 'oomnitza':
                    raise ConfigError("Error: [oomnitza] must be the first section in the ini file.")

                if '.' in section:
                    module = section.split('.')[0]
                else:
                    module = section

                try:
                    mod = importlib.import_module("connectors.{0}".format(module))
                    connector = mod.Connector
                except ImportError:
                    raise ConfigError("Could not import connector for '%s'.")
                else:
                    LOG.debug("parse_config section: %s", section)
                    try:
                        for key, value in config.items(section):
                            if key == 'enable':
                                continue  # No processing of enable flag.
                            elif key == 'recordfilter':
                                if '__filter__' in cfg:
                                    Exception("'filter' is defined more than once in section: %s" % section)
                                cfg['__filter__'] = parse_filter(value)
                            elif key.startswith('mapping.'):
                                try:
                                    cfg[key] = json.loads(value)
                                except ValueError:
                                    # if the value is just a string, it is the name of the source field, convert to dict
                                    if isinstance(value, basestring):
                                        cfg[key] = {'source': value}
                                    else:
                                        raise ConfigError("Failed to parse json field mapping %s:%s = %r", section, key, value)

                            # elif key.startswith('subrecord.') or connector.Settings[key].get('is_json', False):
                            #     try:
                            #         cfg[key] = json.loads(value)
                            #     except ValueError:
                            #         raise ConfigError("Failed to parse json value %s:%s = %r", section, key, value)
                            else:
                                cfg[key] = value
                                if key in connector.Settings:
                                    choices = connector.Settings[key].get('choices', [])
                                    if choices and cfg[key] not in choices:
                                        raise ConfigError("Invalid value for %s: %r. Value must be one of %r", key, value, choices)

                        if 'oomnitza' in connectors:
                            cfg["__oomnitza_connector__"] = connectors['oomnitza']["__connector__"]
                        cfg["__testmode__"] = args.testmode
                        cfg["__save_data__"] = args.save_data
                        cfg["__name__"] = module
                        cfg["__connector__"] = connector(cfg)

                        connectors[section] = cfg
                    except ConfigError:
                        raise
                    except AuthenticationError as exp:
                        raise ConfigError("Authentication failure: %s" % exp.message)
                    except KeyError as exp:
                        raise ConfigError("Unknown ini setting: %r" % exp.message)
                    except Exception as exp:
                        LOG.exception("Error initializing connector: %r" % section)
                        raise ConfigError("Error initializing connector: %r" % section)

            else:
                LOG.debug("Skipping connector '%s' as it is not enabled.", section)
                pass
    except IOError:
        LOG.exception("Could not open config file.")
        raise ConfigError("Could not open config file.")

    if len(connectors) <= 1:
        raise ConfigError("No connectors have been enabled.")

    if args.show_mappings:
        for name, connector in connectors.items():
            if name == 'oomnitza':
                continue
            print connector["__connector__"].MappingName, "Mappings"
            pprint.pprint(connector["__connector__"].field_mappings)
        exit(0)

    return connectors


def get_default_ini():
    """
    uses pkgutil.iter_modules to find all the connectors defined.
    Calls example_ini_settings() on each found connector.
    :return: the contents of the INI file.
    """
    sections = {}
    import connectors
    prefix = connectors.__name__ + '.'

    # pkgutil.iter_modules iterates over the modules in the path
    for importer, modname, ispkg in pkgutil.iter_modules([relative_path('connectors')], prefix):
        # Don't process these as they are internal
        if modname in ['connectors.base'] or modname.startswith('connectors.test'):
            continue

        name = modname.split('.')[-1]
        LOG.debug("Found connector module {0}".format(name))

        try:
            module = __import__(modname, fromlist="dummy")
            sections[name] = module.Connector.example_ini_settings()
        except ImportError as exp:
            sections[name] = [('enable', 'False'), ("# Missing Required Package: {0}".format(exp.message), None)]
        except AttributeError as exp:
            sections[name] = [('enable', 'False'), ("# AttributeError: {0}".format(exp.message),None)]

    return format_sections_for_ini(sections)


def format_sections_for_ini(sections):
    parts = []
    for section in ['oomnitza'] + sorted([section for section in sections.keys() if section != 'oomnitza']):
        parts.append('[{0}]'.format(section))
        for key, value in sections[section]:
            if value:
                parts.append("{0} = {1}".format(key, value))
            else:
                parts.append("{0}".format(key))
        parts.append('')

    return '\n'.join(parts)


class RotateHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, maxBytes, backupCount, filename, encoding):
        filename = relative_app_path(filename)

        if not os.path.isfile(filename):
            open(filename, 'w').close()

        super(RotateHandler, self).__init__(filename=filename, mode='a',
                                            maxBytes=maxBytes, backupCount=backupCount,
                                            encoding=encoding, delay=0)


def setup_logging(args):
    """
    Setup logging configuration
    """
    if args.logging_config == "USE_DEFAULT":
        config_file = relative_app_path('logging.json')
    else:
        config_file = os.path.abspath(args.logging_config)

    try:
        with open(config_file, 'r') as config:
            logging.config.dictConfig(json.load(config))

        logging.captureWarnings(True)
    except IOError:
        if args.logging_config == "USE_DEFAULT":
            sys.stderr.write("Error opening {0}!\n".format(config_file))
        else:
            sys.stderr.write("Error opening logging.json!\n")
        sys.exit(1)

