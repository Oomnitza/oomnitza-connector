import logging
import sys

from lib import config
from lib.connector import run_connector

from lib.converters import Converter

LOG = logging.getLogger("connector.py")


def client_initiated_upload(cmdline_args):
    """
    Main entry point for Oomnitza connector for the "upload" connector mode
    """
    if not cmdline_args.connectors:
        LOG.error("No connectors specified. Exiting")
        sys.exit(0)

    try:
        connectors = config.parse_config_for_client_initiated(cmdline_args)
    except config.ConfigError as exp:
        LOG.error("Error loading config.ini: %s", str(exp))
        sys.exit(1)
    except KeyboardInterrupt:
        raise
    except:
        LOG.exception("Error processing config.ini file.")
        sys.exit(1)

    options = {}
    if cmdline_args.record_count:
        options['record_count'] = cmdline_args.record_count

    for name in cmdline_args.connectors:
        LOG.info("Running connector: %s", name)
        if name not in connectors:
            LOG.error("Connector '%s' is not enabled.", name)
        else:
            run_connector(connectors[name], options)

    Converter.run_all_cleanups()

    LOG.info("Done.")
