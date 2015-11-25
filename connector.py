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
import os
import sys
import argparse
import logging
import logging.config

import decimal  # this is needed here to get the connector to work when compiled/frozen.

import requests
# I think something like the following is required to fully secure SSL connections.
# However, it does not seem to want to install correctly (it seems to be missing dependancies).
# ToDo: turn this back on.
# import urllib3.contrib.pyopenssl
# urllib3.contrib.pyopenssl.inject_into_urllib3()

from lib import config
from lib import connector
from lib import version

from utils.relative_path import relative_app_path, relative_path

LOG = logging.getLogger("connector.py")
root_logger = logging.getLogger("")

try:
    from oomnitza_gui import main as gui_main
    HAVE_GUI = True
except ImportError:
    LOG.debug("Looks like wxPython is not installed.")
    HAVE_GUI = False

from lib.converters import Converter

# The import below needs to be enabled when building the binary!!!
# This is s a holding comment until this is resolved as part of the build automation process.
# Pull out pyodbc when building Mac binary!!
# import ldap, suds, csv, pyodbc  # number 2

def main(args):
    """
    Main entry point for Oomnitza connector
    """
    try:
        connectors = config.parse_config(args)
    except config.ConfigError as exp:
        LOG.error("Error loading config.ini: %s", exp.message)
        return
    except Exception:
        LOG.exception("Error processing config.ini file.")
        return

    oomnitza_connector = connectors.pop('oomnitza')["__connector__"]
    try:
        oomnitza_connector.authenticate()
    except (connector.AuthenticationError, requests.HTTPError, requests.ConnectionError) as exp:
        LOG.error("Error connecting to Oomnitza API: %s", exp.message)
        return

    options = {}
    if args.record_count:
        options['record_count'] = args.record_count

    for name in args.connectors:
        LOG.info("Running connector: %s", name)
        if name not in connectors:
            LOG.error("Connector '%s' is not enabled.", name)
        else:
            connector.run_connector(oomnitza_connector, connectors[name], options)

    Converter.run_all_cleanups()

    LOG.info("Done.")


if __name__ == "__main__":
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
    parser.add_argument("action", default=action_default, nargs=action_nargs, choices=actions, help="Action to perform.")
    parser.add_argument("connectors", nargs='*', default=[], help="Connectors to run.")
    parser.add_argument('--version', action='store_true', help="Show the connector version.")
    parser.add_argument('--show-mappings', action='store_true', help="Show the mappings which would be used by the connector.")
    parser.add_argument('--testmode', action='store_true', help="Run connectors in test mode.")
    parser.add_argument('--save-data', action='store_true', help="Saves the data loaded from other system.")
    # parser.add_argument('--load-data', default="", help="Directory from which to load data.")
    parser.add_argument('--ini', type=str, default=relative_app_path("config.ini"), help="Config file to use.")
    parser.add_argument('--logging-config', type=str, default=logging_setting_path, help="Use to override logging config file to use.")
    parser.add_argument('--record-count', type=int, default=None, help="Number of records to pull and process from connection.")

    args = parser.parse_args()

    config.setup_logging(args)

    LOG.info("Connector version: %s", version.VERSION)
    if args.version:
        exit()

    if args.testmode:
        LOG.info("Connector started in Test Mode.")

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

