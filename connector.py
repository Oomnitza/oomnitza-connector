"""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from gevent import monkey
monkey.patch_all(thread=False)

import os
import sys
import argparse
import logging.config

import requests

from lib import config
from lib import connector
from lib import version

from utils.relative_path import relative_app_path, relative_path
from utils.single_instance import SingleInstance
from lib.converters import Converter

LOG = logging.getLogger("connector.py")
root_logger = logging.getLogger("")

try:
    from oomnitza_gui import main as gui_main
    HAVE_GUI = True
except ImportError:
    LOG.debug("Looks like wxPython is not installed.")
    HAVE_GUI = False


# The import below needs to be enabled when building the binary!!!
# This is s a holding comment until this is resolved as part of the build automation process.
# Pull out pyodbc when building Mac binary!!
# import ldap, suds, csv, pyodbc  # number 2


def prepare_connector(cmdline_args):
    """
    Prepare the connector stuff
    """
    try:
        connectors = config.parse_config(cmdline_args)
    except config.ConfigError as exp:
        LOG.error("Error loading config.ini: %s", exp.message)
        sys.exit(1)

    except:
        LOG.exception("Error processing config.ini file.")
        sys.exit(1)

    oomnitza_connector = connectors.pop('oomnitza')["__connector__"]
    try:
        oomnitza_connector.authenticate()
    except (connector.AuthenticationError, requests.HTTPError, requests.ConnectionError) as exp:
        LOG.error("Error connecting to Oomnitza API: %s", exp.message)
        sys.exit(1)

    options = {}
    if cmdline_args.record_count:
        options['record_count'] = cmdline_args.record_count

    return connectors, oomnitza_connector, options


def main(cmdline_args):
    """
    Main entry point for Oomnitza connector
    """
    non_oomnitza_connectors, oomnitza_connector, options = prepare_connector(cmdline_args)

    for name in cmdline_args.connectors:
        LOG.info("Running connector: %s", name)
        if name not in non_oomnitza_connectors:
            LOG.error("Connector '%s' is not enabled.", name)
        else:
            connector.run_connector(oomnitza_connector, non_oomnitza_connectors[name], options)

    Converter.run_all_cleanups()

    LOG.info("Done.")


def parse_command_line_args(for_server=False):

    action_default = None
    action_nargs = None
    logging_setting_path = relative_app_path('logging.json')

    if getattr(sys, 'frozen', False):
        action_default = 'gui'
        action_nargs = '?'
        logging_setting_path = relative_path('logging.json')

    actions = [
        'upload',      # action which pulls data from remote system and push to Oomnitza.
        'generate-ini' # action which generates an example config.ini file.
    ]
    if HAVE_GUI:
        # action which runs the gui.
        actions.append('gui')

    parser = argparse.ArgumentParser()

    if for_server:
        parser.add_argument('--host', type=str, default='127.0.0.1')
        parser.add_argument('--port', type=int, default=8000)
    else:
        parser.add_argument("action", default=action_default, nargs=action_nargs, choices=actions, help="Action to perform.")
        parser.add_argument("connectors", nargs='*', default=[], help="Connectors to run.")
        parser.add_argument('--record-count', type=int, default=None, help="Number of records to pull and process from connection.")
        parser.add_argument('--singleton', type=int, default=1, help="Control the behavior of connector. Limiting the number of "
                                                                     "simultaneously running connectors")
        parser.add_argument('--workers', type=int, default=10, help="Number of async IO workers used to pull & push records.")

    parser.add_argument('--version', action='store_true', help="Show the connector version.")
    parser.add_argument('--show-mappings', action='store_true', help="Show the mappings which would be used by the connector.")
    parser.add_argument('--testmode', action='store_true', help="Run connectors in test mode.")
    parser.add_argument('--save-data', action='store_true', help="Saves the data loaded from other system.")
    # parser.add_argument('--load-data', default="", help="Directory from which to load data.")
    parser.add_argument('--ini', type=str, default=relative_app_path("config.ini"), help="Config file to use.")
    parser.add_argument('--logging-config', type=str, default=logging_setting_path, help="Use to override logging config file to use.")

    cmdline_args = parser.parse_args()

    config.setup_logging(cmdline_args)

    if for_server:
        # region COMPATIBILITY WITH CONFIG PARSER
        cmdline_args.record_count = None
        # endregion

    return cmdline_args


if __name__ == "__main__":

    args = parse_command_line_args()

    LOG.info("Connector version: %s", version.VERSION)
    if args.version:
        sys.exit(0)

    if args.testmode:
        LOG.info("Connector started in Test Mode.")

    with SingleInstance(bool(args.singleton), "Connector is already running."):
        if args.action == 'generate-ini':
            config.generate_ini_file(args)
        elif args.action == 'gui' and HAVE_GUI:
            if not os.path.exists(args.ini):
                # ensure the gui has a config.ini file to load. Generate it if missing.
                config.generate_ini_file(args)
            gui_main(args)
        else:
            if not args.connectors:
                LOG.error("No connectors specified.")
                sys.exit(1)

            main(args)
