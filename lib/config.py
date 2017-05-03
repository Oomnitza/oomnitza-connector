import os
import sys
import json
from ConfigParser import SafeConfigParser, ParsingError, MissingSectionHeaderError, DEFAULTSECT
import importlib
import pkgutil
import shutil
import logging
import logging.config
import pprint

from utils.relative_path import relative_path
from utils.relative_path import relative_app_path
from lib.error import AuthenticationError

LOG = logging.getLogger("lib/config")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from .filter import DynamicConverter, parse_filter
from .error import ConfigError


class SpecialConfigParser(SafeConfigParser):
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
        all_sections.extend(self._sections.values())
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


def parse_config(args):
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
            cfg = {}
            if section == 'converters':
                for name, filter_str in config.items('converters'):
                    DynamicConverter(name, filter_str)
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
                    LOG.exception("Could not import connector for '%s'.", section)
                    raise ConfigError("Could not import connector for '%s'." % section)
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
                                        raise ConfigError(
                                            "Failed to parse json field mapping %s:%s = %r" % (section, key, value)
                                        )

                            # elif key.startswith('subrecord.') or connector.Settings[key].get('is_json', False):
                            #     try:
                            #         cfg[key] = json.loads(value)
                            #     except ValueError:
                            #         raise ConfigError("Failed to parse json value %s:%s = %r" % (section, key, value))
                            else:
                                if key in connector.Settings:
                                    setting = connector.Settings[key]
                                elif key in connector.CommonSettings:
                                    setting = connector.CommonSettings[key]
                                else:
                                    #raise ConfigError("Invalid setting in %r section: %r." % (section, key))
                                    LOG.warning("Invalid setting in %r section: %r.", section, key)
                                    continue

                                cfg[key] = value

                                choices = setting.get('choices', [])
                                if choices and cfg[key] not in choices:
                                    raise ConfigError(
                                        "Invalid value for %s: %r. Value must be one of %r" % (key, value, choices)
                                    )

                        #ToDo: look into making this generic: env_FIELD so any setting can be an environment variable.
                        if 'env_password' in cfg and cfg['env_password']:
                            LOG.info(
                                "Loading password for %s from environment variable %r.", section, cfg['env_password']
                            )
                            try:
                                cfg['password'] = os.environ[cfg['env_password']]
                            except KeyError:
                                raise ConfigError(
                                    "Unable to load password for %s from environment "
                                    "variable %r." % (section, cfg['env_password'])
                                )

                        if 'oomnitza' in connectors:
                            cfg["__oomnitza_connector__"] = connectors['oomnitza']["__connector__"]
                        cfg["__testmode__"] = args.testmode
                        cfg["__save_data__"] = args.save_data
                        if 'workers' in args:
                            cfg["__workers__"] = args.workers
                        # cfg["__load_data__"] = args.load_data
                        cfg["__name__"] = module
                        cfg["__connector__"] = connector(section, cfg)

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
            print connector["__connector__"].section, "Mappings"
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
    from connectors import EnabledConnectors
    prefix = 'connectors.'

    # pkgutil.iter_modules iterates over the modules in the path
    # Note(daniel): pkgutil.iter_modules stopped working when built with pyinstaller.
    #               I don't know why and it was easier to switch to a hardcoded set of values.
    # for importer, modname, ispkg in pkgutil.iter_modules([relative_path('connectors')], prefix):
    for modname in [prefix+name for name in EnabledConnectors]:
        # Don't process these as they are internal
        if modname in ['connectors.base'] or modname.startswith('connectors.test'):
            continue

        name = modname.split('.')[-1]
        LOG.debug("Found connector module {0}".format(name))

        try:
            module = __import__(modname, fromlist="dummy")
            sections[name] = module.Connector.example_ini_settings()
        except ImportError as exp:
            if name == 'sccm':
                continue
            sections[name] = [('enable', 'False'), ("# Missing Required Package: {0}".format(exp.message), None)]
        except AttributeError as exp:
            sections[name] = [('enable', 'False'), ("# AttributeError: {0}".format(exp.message), None)]
        except Exception as exp:
            sections[name] = [('enable', 'False'), ("# Exception: {0}".format(exp.message), None)]


    return format_sections_for_ini(sections)


def format_sections_for_ini(sections):
    parts = []
    for section in ['oomnitza'] + sorted([section for section in sections.keys() if section != 'oomnitza']):
        parts.append('[{0}]'.format(section))
        for key, value in sections[section]:
            if not isinstance(value, basestring):
                value = json.dumps(value)

            tpl = "{0} = {1}"
            if '\n' in value:
                tpl = "{0}:{1}"
            parts.append(tpl.format(key, value))
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
    config_file = os.path.abspath(args.logging_config)

    try:
        with open(config_file, 'r') as config:
            logging.config.dictConfig(json.load(config))

        logging.captureWarnings(True)
    except IOError:
        sys.stderr.write("Error opening logging config file: {0}!\n".format(config_file))
        sys.exit(1)



