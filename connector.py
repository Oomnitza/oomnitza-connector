from gevent import monkey
monkey.patch_all()

import sys
import argparse
import logging.config

from constants import MODE_CLOUD_INITIATED_UPLOAD, MODE_VERSION, MODE_CLIENT_INITIATED_UPLOAD, MODE_GENERATE_INI_TEMPLATE
from lib import config, version
from modes.cloud_initiated import cloud_initiated_upload
from modes.client_initiated import client_initiated_upload
from utils.relative_path import relative_app_path


LOG = logging.getLogger("connector.py")


def get_cmd_line_args_parser(for_server=False):

    modes = (
        MODE_CLOUD_INITIATED_UPLOAD,
        MODE_CLIENT_INITIATED_UPLOAD,
        MODE_GENERATE_INI_TEMPLATE,
        MODE_VERSION,
    )

    parser = argparse.ArgumentParser()

    if for_server:
        parser.add_argument('--host', type=str, default='127.0.0.1')
        parser.add_argument('--port', type=int, default=8000)
    else:
        parser.add_argument("mode", nargs='?', default=MODE_CLOUD_INITIATED_UPLOAD, choices=modes, help="Action to perform.")
        parser.add_argument("connectors", nargs='*', default=[], help="Connectors to run. Relevant only for the `upload` mode")
        parser.add_argument('--record-count', type=int, default=None, help="Number of records to pull and process from connection. Relevant only for the `upload` mode")
        parser.add_argument('--workers', type=int, default=2, help="Number of async IO workers used to pull & push records.")
        parser.add_argument('--ignore-cloud-maintenance', action='store_true', help="Adds special behavior for the managed connectors to ignore the cloud maintenance")

    parser.add_argument('--show-mappings', action='store_true', help="Show the mappings which would be used by the connector. Relevant only for the `upload` mode")
    parser.add_argument('--testmode', action='store_true', help="Run connectors in test mode.")
    parser.add_argument('--save-data', action='store_true', help="Saves the data loaded from other system.")
    parser.add_argument('--ini', type=str, default=relative_app_path("config.ini"), help="Config file to use.")
    parser.add_argument('--logging-config', type=str, default=relative_app_path('logging.json'), help="Use to override logging config file to use.")

    return parser


def parse_command_line_args(for_server=False):

    parser = get_cmd_line_args_parser(for_server)

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

    mode_handlers = {
        MODE_VERSION:                   lambda *a: sys.exit(0),  # just exit immediately
        MODE_GENERATE_INI_TEMPLATE:     config.generate_ini_file,
        MODE_CLIENT_INITIATED_UPLOAD:   client_initiated_upload,
        MODE_CLOUD_INITIATED_UPLOAD:    cloud_initiated_upload,
    }

    try:
        mode_handlers[args.mode](args)
    except KeyboardInterrupt:
        LOG.info('Interrupted... Exiting')
