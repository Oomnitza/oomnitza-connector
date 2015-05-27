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

import requests

from lib import config
from lib import connector
from utils.relative_path import relative_app_path

LOG = logging.getLogger(__name__)
root_logger = logging.getLogger("")


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
    # if args.datafile:
    #     options['datafile'] = os.path.abspath(args.datafile)
    #     if not os.path.isfile(options['datafile']):
    #         logger.error("Invalid data file. %r does not exist.", options['datafile'])
    #         sys.exit(1)
    if args.record_count:
        options['record_count'] = args.record_count

    for name in args.connectors:
        LOG.info("Running connector: %s", name)
        if name not in connectors:
            LOG.error("Connector '%s' is not enabled.", name)
        else:
            connector.run_connector(oomnitza_connector, connectors[name], options)

    LOG.info("Done.")


if __name__ == "__main__":
    action_default = None
    action_nargs = 1
    if getattr(sys, 'frozen', False):
        action_default = 'gui'
        action_nargs = '?'

    parser = argparse.ArgumentParser()
    parser.add_argument("action", default=action_default, nargs=action_nargs, choices=['gui', 'upload', 'generate-ini'], help="Action to perform.")
    parser.add_argument("connectors", nargs='*', default=[], help="Connectors to run.")
    parser.add_argument('--show-mappings', action='store_true', help="Show the mappings which would be used by the connector.")
    parser.add_argument('--testmode', action='store_true', help="Run connectors in test mode.")
    parser.add_argument('--save_data', action='store_true', help="Saves the data loaded from other system.")
    parser.add_argument('--ini', type=str, default=relative_app_path("config.ini"), help="Config file to use.")
    parser.add_argument('--logging-config', type=str, default="USE_DEFAULT", help="Use to override logging config file to use.")
    parser.add_argument('--record-count', type=int, default=None, help="Number of records to pull and process from connection.")
    # parser.add_argument('--datafile', type=str, default=None, help="Data file to use for connector in place of live request.")
    args = parser.parse_args()

    config.setup_logging(args)

    if args.testmode:
        LOG.info("Connector started in Test Mode.")

    if args.action == 'generate-ini':
        config.generate_ini_file(args)

    elif args.action == 'gui':
        try:
            from oomnitza_gui import main
            main(args)
        except ImportError:
            LOG.exception("Error loading gui.")

    else:
        if not args.connectors:
            LOG.error("No connectors specified.")
            sys.exit(1)

        main(args)

