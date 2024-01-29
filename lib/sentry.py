import logging
import sentry_sdk

from lib.config import SpecialConfigParser


class SentryConfiguration:
    dsn = ''
    rate = 0.0
    environment = ''
    instance = ''

    def __init__(self, ini_file_path: str):
        config_file = SpecialConfigParser()
        config_file.read(ini_file_path)

        if config_file.has_option('oomnitza', 'SENTRY_DSN_CONNECTOR'):
            self.dsn = config_file.get('oomnitza', 'SENTRY_DSN_CONNECTOR').strip()
        if config_file.has_option('oomnitza', 'SENTRY_RATE_CONNECTOR'):
            self.rate = config_file.getfloat('oomnitza', 'SENTRY_RATE_CONNECTOR')
        if config_file.has_option('oomnitza', 'IS_DEVELOPMENT'):
            self.environment = (
                "development"
                if config_file.getboolean('oomnitza', 'IS_DEVELOPMENT')
                else "production"
            )
        if config_file.has_option('oomnitza', 'SUBDOMAIN'):
            self.instance = config_file.get('oomnitza', 'SUBDOMAIN').strip()


def init_sentry(config: SentryConfiguration):
    if len(config.dsn) > 0 and config.rate:
        logging.info(
            "Using Sentry %s with a sample rate of %d%% (%s, %s)",
            config.dsn,
            config.rate * 100,
            config.environment,
            config.instance
        )
        sentry_sdk.init(
            dsn=config.dsn,
            sample_rate=config.rate,
            traces_sample_rate=config.rate,
            environment=config.environment,
        )
        sentry_sdk.set_tag('instance', config.instance)
