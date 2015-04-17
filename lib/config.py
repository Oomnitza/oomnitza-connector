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

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_ini_file(args):
    # take a backup of we will be overwriting a file.
    if os.path.exists(args.ini):
        shutil.move(args.ini, args.ini+'.bak')

    # write out the ini file.
    with open(args.ini, 'w') as ini_file:
        ini_file.write(get_default_ini())

    print "{0} has been generated.".format(args.ini)


def parse_config(args):
    """
    Parse connector configuration and generate a result in dictionary
    format which includes integration names and the required info for
    pulling out data
    """
    connectors = {}
    errors = False
    try:
        config = ConfigParser.ConfigParser()
        if not os.path.isfile(args.ini):
            # The config file does not yet exist, so generate it.
            generate_ini_file(args)

        config.read(args.ini)
        for section in config.sections():
            cfg = {}
            if section == 'oomnitza' or \
               config.has_option(section, 'enable') and config.getboolean(section, 'enable'):
                if not connectors and section != 'oomnitza':
                    raise RuntimeError("Error: [oomnitza] must be the first section in the ini file.")

                if '.' in section:
                    module = section.split('.')[0]
                else:
                    module = section

                try:
                    mod = importlib.import_module("connectors.{0}".format(module))
                    connector = mod.Connector
                except ImportError:
                    errors = True
                    logger.exception("Could not import connector for '%s'.", section)
                else:
                    logger.debug("parse_config section: %s", section)
                    try:
                        for key, value in config.items(section):
                            if key == 'enable':
                                continue  # No processing of enable flag.
                            elif key.startswith('mapping.'):
                                try:
                                    cfg[key] = json.loads(value)
                                except ValueError:
                                    # if the value is just a string, it is the name of the source field, convert to dict
                                    if isinstance(cfg[key], basestring):
                                        cfg[key] = {'source': cfg[key]}
                                    else:
                                        errors = True
                                        logger.error("Failed to parse json field mapping %s:%s = %r", section, key, value)

                            # elif key.startswith('subrecord.') or connector.Settings[key].get('is_json', False):
                            #     try:
                            #         cfg[key] = json.loads(value)
                            #     except ValueError:
                            #         errors = True
                            #         logger.error("Failed to parse json value %s:%s = %r", section, key, value)
                            else:
                                cfg[key] = value
                                if key in connector.Settings:
                                    choices = connector.Settings[key].get('choices', [])
                                    if choices and cfg[key] not in choices:
                                        errors = True
                                        logger.error("Invalid value for %s: %r. Value must be one of %r", key, value, choices)

                        if 'oomnitza' in connectors:
                            cfg["__oomnitza_connector__"] = connectors['oomnitza']["__connector__"]
                        cfg["__testmode__"] = args.testmode
                        cfg["__name__"] = module
                        cfg["__connector__"] = connector(cfg)

                        connectors[section] = cfg
                    except KeyError as exp:
                        errors = True
                        logger.error("Unknown ini setting: %r", exp.message)
            else:
                # logger.debug("Skipping connector '%s' as it is not enabled.", section)
                pass
    except IOError:
        errors = True
        logger.exception("Could not open config file.")

    if len(connectors) <= 1:
        errors = True
        logger.error("No connectors have been enabled. Aborting.")

    if args.show_mappings:
        for name, connector in connectors.items():
            if name == 'oomnitza':
                continue
            print connector["__connector__"].MappingName, "Mappings"
            pprint.pprint(connector["__connector__"].field_mappings)
        exit(0)

    if errors:
        sys.exit(1)
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
    for importer, modname, ispkg in pkgutil.iter_modules(connectors.__path__, prefix):
        # Don't process these as they are internal
        if modname in ['connectors.base']:
            continue

        name = modname.split('.')[-1]
        logger.debug("Found connector module {0}".format(name))

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


def setup_logging(args):
    """
    Setup logging configuration
    """
    if args.logging_config == "USE_DEFAULT":
        config_file = os.path.join(ROOT, 'logging.json')
    else:
        config_file = os.path.abspath(args.logging_config)

    try:
        with open(config_file, 'r') as config:
            logging.config.dictConfig(json.load(config))
    except IOError:
        if args.logging_config == "USE_DEFAULT":
            sys.stderr.write("Error opening {0}!\n".format(config_file))
        else:
            sys.stderr.write("Error opening logging.json!\n")
        sys.exit(1)

