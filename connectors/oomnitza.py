
import base64
import logging
import pprint
from socket import gaierror

from requests import RequestException

from lib.connector import BaseConnector, AuthenticationError
from lib.error import ConfigError

LOG = logging.getLogger("connectors/oomnitza")  # pylint:disable=invalid-name


class Connector(BaseConnector):
    Settings = {
        'url':       {'order': 1, 'example': "https://example.oomnitza.com"},
        'api_token': {'order': 2, 'example': "ZZZZXXXXCCCCC", 'default': ""},
        'username':  {'order': 3, 'example': "oomnitza-sa", 'default': ""},
        'password':  {'order': 4, 'example': "ThePassword", 'default': ""},

    }
    # no FieldMappings for oomnitza connector
    FieldMappings = {}

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self._test_headers = []
        self.authenticate()

    def _test_site_connection(self):
        pass

    def get_field_mappings(self, extra_mappings):
        """ Override base to always return an empty mapping set.
        :param extra_mappings:
        :return: an empty dict()
        """
        return {}

    def get_headers(self):
        # LOG.debug("get_headers(): self.settings['api_token'] = %r", self.settings['api_token'])
        return {'contentType': 'application/json', 'Authorization2': self.settings['api_token']}

    def authenticate(self):
        # LOG.debug("authenticate(0): self.settings['api_token'] = %r", self.settings['api_token'])
        if not self.settings['api_token']:
            if not self.settings['username'] or not self.settings['password']:
                raise ConfigError("Oomnitza section needs either: api_token or username & password.")

        try:
            if self.settings['api_token']:
                self.get("{url}/api/v2/mappings?name=AuthTest".format(**self.settings))
                return

            auth_url = "{url}/api/request_token".format(**self.settings)
            response = self.post(
                auth_url,
                {'login': self.settings['username'],
                 'password': self.settings['password']},
                post_as_json=False,
            )
            self.settings['api_token'] = response.json()["token"]
        except RequestException as exp:
            if isinstance(exp.message, basestring):
                raise AuthenticationError("{} returned {}.".format(self.settings['url'], exp.message))
            if isinstance(exp.message.args[1], gaierror):
                msg = "Unable to connect to {} ({}).".format(self.settings['url'], exp.message.args[1].errno)
                if exp.message.args[1].errno == 8:
                    msg = "Unable to get address for {}.".format(self.settings['url'])
                raise AuthenticationError(msg)
            raise AuthenticationError(str(exp))
        # LOG.debug("authenticate(1): self.settings['api_token'] = %r", self.settings['api_token'])

    def upload_assets(self, assets, options):
        # logger.debug("upload_assets( %r )", assets)
        url = "{url}/api/v2/bulk/assets".format(**self.settings)
        response = self.post(url, assets)
        # logger.debug("response = %r", response.text)
        return response

    def upload_users(self, users, options):
        # logger.debug("upload_users( %r )", users)
        url = "{url}/api/v2/bulk/users".format(**self.settings)
        response = self.post(url, users)
        # logger.debug("response = %r", response.text)
        return response

    def upload_audit(self, computers, options):
        # logger.debug("upload_users( %r )", users)
        url = "{url}/api/v2/bulk/audit".format(**self.settings)
        response = self.post(url, computers)
        # logger.debug("response = %r", response.text)
        return response

    def _test_upload_assets(self, assets, options):
        LOG.warning("upload_assets() = %r", assets)

    def _test_upload_users(self, users, options):
        if not isinstance(users, list):
            users = [users]
        if not self._test_headers:
            self._test_headers = users[0].keys()
            print("\t".join(self._test_headers))
        for user in users:
            print("\t".join([repr(user[f]) or '""' for f in self._test_headers]))

    def _test_upload_audit(self, computers, options):
        pprint.pprint(computers)

    def perform_sync(self, oomnitza_connector, options):
        raise RuntimeError("Can't call perform_sync on Oomnitza connector.")

    def do_test_connection(self, options):
        self.authenticate()
        assert self.settings['api_token'], "Failed to get api_token."

    @classmethod
    def example_ini_settings(cls):
        settings = super(Connector, cls).example_ini_settings()
        return settings[1:]

    def get_mappings(self, name):
        url = "{0}/api/v2/mappings?name={1}".format(self.settings['url'], name)
        response = self.get(url)
        # logger.debug("%s mapping: %r", name, response.json())
        return response.json()
