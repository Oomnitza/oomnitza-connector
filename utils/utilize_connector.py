import argparse

from utils.relative_path import relative_app_path


def utilize_connector(target=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs='?', default='gui', choices=['gui', 'upload', 'generate-ini'], help="Action to perform.")
    parser.add_argument("connectors", nargs='*', default=[], help="Connectors to run.")
    parser.add_argument('--show-mappings', action='store_true', help="Show the mappings which would be used by the connector.")
    parser.add_argument('--testmode', action='store_true', help="Run connectors in test mode.")
    parser.add_argument('--save_data', action='store_true', help="Saves the data loaded from other system.")
    parser.add_argument('--ini', type=str, default=relative_app_path('config.ini'), help="Config file to use.")
    parser.add_argument('--logging-config', type=str, default="USE_DEFAULT", help="Use to override logging config file to use.")
    parser.add_argument('--record-count', type=int, default=None, help="Number of records to pull and process from connection.")
    args = parser.parse_args()

    return target(args)
