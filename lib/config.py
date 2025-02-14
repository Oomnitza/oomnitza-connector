import importlib
import json
import logging
import logging.config
import os
import pprint
import shutil
import sys
from constants import ENABLED_CONNECTORS
from configparser import ParsingError, MissingSectionHeaderError, DEFAULTSECT, NoSectionError, ConfigParser
from copy import deepcopy
from logging.handlers import RotatingFileHandler

from lib.error import AuthenticationError
from utils.relative_path import relative_app_path

LOG = logging.getLogger("lib/config")


from .filter import DynamicConverter, parse_filter
from .error import ConfigError


class SpecialConfigParser(ConfigParser):
    def _interpolate(self, section, option, rawval, vars):
        """
        Disabled ConfigParser Interpolation of values.
        :param section:
        :param option:
        :param rawval:
        :param vars:
        :return: rawval
        """
        return rawval

    def _read(self, fp, fpname):
        """Parse a sectioned setup file.

        The sections in setup file contains a title line at the top,
        indicated by a name in square brackets (`[]'), plus key/value
        options lines, indicated by `name: value' format lines.
        Continuations are represented by an embedded newline then
        leading whitespace.  Blank lines, lines beginning with a '#',
        and just about everything else are ignored.
        """
        cursect = None                        # None, or a dictionary
        optname = None
        lineno = 0
        e = None                              # None, or an exception
        while True:
            line = fp.readline()
            line = line.replace('%', '%%')  # python 3 uses % as system symbol, if it is double percent "%%" it automatically replaces to "%"
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            if line.strip() == '' or line[0] in '#;':
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip('\n')
                if value:
                    cursect[optname].append(value)
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    if sectname in self._sections:
                        cursect = self._sections[sectname]
                    elif sectname == DEFAULTSECT:
                        cursect = self._defaults
                    else:
                        cursect = self._dict()
                        cursect['__name__'] = sectname
                        self._sections[sectname] = cursect
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self._optcre.match(line)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        optname = self.optionxform(optname.rstrip())
                        # This check is fine because the OPTCRE cannot
                        # match if it would set optval to None
                        if optval is not None:
                            if vi in ('=', ':') and ';' in optval:
                                # ';' is a comment delimiter only if it follows
                                # a spacing character
                                pos = optval.find(';')
                                if pos != -1 and optval[pos-1].isspace():
                                    optval = optval[:pos]
                            optval = optval.strip()
                            # allow empty values
                            if optval == '""':
                                optval = ''
                            cursect[optname] = [optval]
                        else:
                            # valueless option handling
                            cursect[optname] = optval
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(fpname)
                        e.append(lineno, repr(line))
        # if any parsing errors occurred, raise an exception
        if e:
            raise e

        # join the multi-line values collected while reading
        all_sections = [self._defaults]
        all_sections.extend(list(self._sections.values()))
        for options in all_sections:
            for name, val in options.items():
                if isinstance(val, list):
                    options[name] = '\n'.join(val)


def generate_ini_file(args):
    # take a backup of we will be overwriting a file.
    if os.path.exists(args.ini):
        shutil.move(args.ini, args.ini+'.bak')

    # write out the ini file.
    with open(args.ini, 'w') as ini_file:
        ini_file.write(get_default_ini())

    LOG.info("{0} has been generated.".format(args.ini))


def init_connector_from_configuration(connector_name, configuration, cmdline_args, extra_cfg=None):
    """
    Initialize the connector with some extra information using the given configuration
    """

    cfg = {}
    cfg.update(**(extra_cfg or {}))

    if '.' in connector_name:
        module_ = connector_name.split('.')[0]
    else:
        module_ = connector_name

    try:
        mod = importlib.import_module("connectors.{0}".format(module_))
        connector = mod.Connector
    except ImportError:
        LOG.exception("Could not import connector for '%s'.", connector_name)
        raise ConfigError("Could not import connector for '%s'." % connector_name)
    else:
        try:
            for key, value in configuration:
                if key == '__name__':
                    continue
                if key == 'enable':
                    continue  # No processing of enable flag.
                elif key == 'recordfilter':
                    if '__filter__' in cfg:
                        Exception("'filter' is defined more than once in section: %s" % connector_name)
                    cfg['__filter__'] = parse_filter(value)
                elif key.startswith('mapping.'):
                    try:
                        cfg[key] = json.loads(value)
                    except ValueError:
                        # if the value is just a string, it is the name of the source field, convert to dict
                        if isinstance(value, str):
                            cfg[key] = {'source': value}
                        else:
                            raise ConfigError(
                                "Failed to parse json field mapping %s:%s = %r" % (connector_name, key, value)
                            )

                else:
                    if key in connector.Settings:
                        setting = connector.Settings[key]
                    elif key in connector.CommonSettings:
                        setting = connector.CommonSettings[key]
                    else:
                        LOG.warning("Invalid setting in %r section: %r.", connector_name, key)
                        continue

                    cfg[key] = value

                    choices = setting.get('choices', [])
                    if choices and cfg[key] not in choices:
                        raise ConfigError(
                            "Invalid value for %s: %r. Value must be one of %r" % (key, value, choices)
                        )

            cfg["__testmode__"] = cmdline_args.testmode
            cfg["__save_data__"] = cmdline_args.save_data
            cfg["__ignore_cloud_maintenance__"] = cmdline_args.ignore_cloud_maintenance
            try:
                cfg["__workers__"] = cmdline_args.workers
            except:
                cfg["__workers__"] = 4

            cfg["__name__"] = cfg.get('name') or module_
            cfg["__connector__"] = connector(connector_name, cfg)

            return cfg
        except ConfigError:
            raise
        except AuthenticationError as exp:
            raise ConfigError("Authentication failure: %s" % str(exp))
        except KeyError as exp:
            raise ConfigError("Unknown ini setting: %r" % str(exp))
        except KeyboardInterrupt:
            raise
        except:
            LOG.exception("Error initializing connector: %r" % connector_name)
            raise ConfigError("Error initializing connector: %r" % connector_name)


def parse_config_for_client_initiated(args):
    """
    Parse connector configuration and generate a result in dictionary
    format which includes integration names and the required info for
    pulling out data
    """
    connectors = {}
    try:
        config = SpecialConfigParser()
        if not os.path.isfile(args.ini):
            # The config file does not yet exist, so generate it.
            # generate_ini_file(args)
            raise ConfigError("Error: unable to open ini file: %r" % args.ini)

        config.read(args.ini)
        for section in config.sections():
            if section == 'converters':
                for name, filter_str in config.items('converters'):
                    DynamicConverter(name, filter_str)
            elif section == 'oomnitza' or config.has_option(section, 'enable') and config.getboolean(section, 'enable'):
                if not connectors and section != 'oomnitza':
                    raise ConfigError("Error: [oomnitza] must be the first section in the ini file.")

                cfg = init_connector_from_configuration(section, config.items(section), args)
                connectors[section] = cfg
            else:
                LOG.debug("Skipping connector '%s' as it is not enabled.", section)
                pass
    except IOError:
        raise ConfigError("Could not open config file.")

    if len(connectors) <= 1:
        raise ConfigError("No connectors have been enabled.")

    if args.show_mappings:
        for name, connector in connectors.items():
            if name == 'oomnitza':
                continue
            print(connector["__connector__"].section, "Mappings")
            pprint.pprint(connector["__connector__"].field_mappings)
        exit(0)

    return connectors


def parse_base_config_for_cloud_initiated(args):
    """
    Read only common info from the ini file for now - the `oomnitza` and `converters` sections
    """
    try:
        config = SpecialConfigParser()
        if not os.path.isfile(args.ini):
            # The config file does not yet exist, so generate it.
            # generate_ini_file(args)
            raise ConfigError("Error: unable to open ini file: %r" % args.ini)

        config.read(args.ini)
        for section in config.sections():
            if section == 'converters':
                for name, filter_str in config.items('converters'):
                    DynamicConverter(name, filter_str)
            elif section == 'oomnitza':
                return init_connector_from_configuration(section, config.items(section), args)

    except IOError:
        raise ConfigError("Could not open config file.")


def parse_connector_config_for_cloud_initiated(connector_name, extra_cfg, args):
    """
    Read and init the specific connector by its given `section` identifier
    """
    try:
        config = ConfigParser()
        if not os.path.isfile(args.ini):
            # The config file does not yet exist, so generate it.
            # generate_ini_file(args)
            raise ConfigError("Error: unable to open ini file: %r" % args.ini)

        config.read(args.ini)
        # That is possible that there will be no content within the .ini file - especially for the cloud installation.
        # So, init the connector config without the data from ini file
        try:
            configuration = config.items(connector_name)
        except NoSectionError:
            configuration = []
        initialized_connector_configuration = init_connector_from_configuration(connector_name, configuration, args, extra_cfg=extra_cfg)
        # ensure the instance of the connector class initiated for the cloud based connector has its own copy of OomnitzaConnector and not sharing it
        # among other threads
        initialized_connector_configuration['__connector__'].OomnitzaConnector = deepcopy(initialized_connector_configuration['__connector__'].OomnitzaConnector)
        return initialized_connector_configuration
    except IOError:
        raise ConfigError("Could not open config file.")


def get_default_ini():
    """
    uses pkgutil.iter_modules to find all the connectors defined.
    Calls example_ini_settings() on each found connector.
    :return: the contents of the INI file.
    """

    sections = {}
    prefix = 'connectors.'

    for modname in [prefix+name for name in ENABLED_CONNECTORS]:
        # Don't process these as they are internal
        if modname in ['connectors.base'] or modname.startswith('connectors.test'):
            continue

        name = modname.split('.')[-1]
        LOG.debug("Found connector module {0}".format(name))

        try:
            module_ = importlib.import_module(modname)
            sections[name] = module_.Connector.example_ini_settings()
        except ImportError as exp:
            if name == 'sccm':
                continue
            sections[name] = [('enable', 'False'), ("# Missing Required Package: {0}".format(str(exp)), None)]
        except AttributeError as exp:
            sections[name] = [('enable', 'False'), ("# AttributeError: {0}".format(str(exp)), None)]
        except Exception as exp:
            sections[name] = [('enable', 'False'), ("# Exception: {0}".format(str(exp)), None)]

    return format_sections_for_ini(sections, ENABLED_CONNECTORS)


def format_sections_for_ini(sections, enabled_connectors):
    parts = []

    for connector, config in sorted(enabled_connectors.items(), key=lambda x: x[1]['order']):

        connector_label = config.get('label', connector)
        parts.append('[{0}]'.format(connector_label))

        for key, value in sections[connector]:
            if not isinstance(value, str):
                value = json.dumps(value)

            tpl = "{0} = {1}"
            if '\n' in value:
                tpl = "{0}:{1}"

            parts.append(tpl.format(key, value))
        parts.append('')

    return '\n'.join(parts)


class RotateHandler(RotatingFileHandler):
    def __init__(self, maxBytes, backupCount, filename, encoding):
        filename = relative_app_path(filename)

        if not os.path.isfile(filename):
            open(filename, 'w').close()

        super(RotateHandler, self).__init__(filename=filename, mode='a',
                                            maxBytes=maxBytes, backupCount=backupCount,
                                            encoding=encoding, delay=False)


def setup_logging(args):
    """
    Setup logging configuration
    """
    config_file = os.path.abspath(args.logging_config)

    try:
        with open(config_file, 'r') as config:
            cfg_json = json.load(config)
            try:
                logging.config.dictConfig(cfg_json)
                LOG.debug("Loaded logging configuration from file [%s] [%s]", config_file, cfg_json)
            except Exception as exc:
                LOG.error("Unable to configure logging using configuration [%s]", cfg_json)

        logging.captureWarnings(True)
    except IOError as e:
        err_msg = f"Error opening logging config file: {config_file}! Reason:{str(e)}"
        sys.stderr.write(err_msg)
        sys.exit(1)
