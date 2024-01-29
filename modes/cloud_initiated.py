import logging
import sys
from time import sleep
from threading import Thread

from requests.exceptions import RetryError

from lib import config
from lib.connector import run_connector

LOG = logging.getLogger("connector.py")


def run_the_managed_sync(cloud_config, cmdline_args):
    """
    Start the new sync and run it within the separate process to not block the parallel execution of multiple
    """
    try:
        is_report_service = cloud_config.get('reports_service')
        connector_section = f'managed_reports.{cloud_config["id"]}' if is_report_service else f'managed.{cloud_config["id"]}'
        connector_config = config.parse_connector_config_for_cloud_initiated(
            connector_section,
            cloud_config,
            cmdline_args
        )
    except KeyboardInterrupt:
        raise
    except Exception:
        LOG.exception("Error processing configuration")
        sys.exit(1)

    run_connector(connector_config, {})


def cloud_initiated_upload(cmdline_args):

    try:
        oomnitza_config = config.parse_base_config_for_cloud_initiated(cmdline_args)
    except config.ConfigError as exp:
        LOG.error("Error loading config.ini: %s", str(exp))
        sys.exit(1)
    except KeyboardInterrupt:
        raise
    except Exception:
        LOG.exception("Error processing config.ini file.")
        sys.exit(1)

    while True:
        try:
            cloud_configs = oomnitza_config['__connector__'].check_managed_cloud_configs()
        except RetryError:
            if oomnitza_config['__ignore_cloud_maintenance__']:
                # if we are ignoring the cloud maintenance we have be very tolerant to retry errors
                LOG.warning('Oomnitza maintenance detected... will retry later')
                sleep(2)
                continue
            raise

        for cloud_config in cloud_configs:
            Thread(target=run_the_managed_sync, args=(cloud_config, cmdline_args)).start()

        # sleep between checks
        sleep(10)
