
import base64
import logging
import pprint
from socket import gaierror

from requests import RequestException

from lib.connector import BaseConnector, AuthenticationError

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class Connector(BaseConnector):
    Settings = {
        'url':      {'order': 1, 'example': "https://example.oomnitza.com"},
        'username': {'order': 2, 'example': "python"},
        'password': {'order': 3, 'example': "ThePassword"},
        'is_sso':   {'order': 4, 'default': "False"},
    }
    # no FieldMappings for oomnitza connector
    FieldMappings = {}

    def __init__(self, settings):
        super(Connector, self).__init__(settings)
        self._auth_token = None
        self.authenticate()
        self._test_headers = []

    def _test_site_connection(self):
        pass

    def get_field_mappings(self, extra_mappings):
        """ Override base to always return an empty mapping set.
        :param extra_mappings:
        :return: an empty dict()
        """
        return {}

    def get_headers(self):
        if self.settings['is_sso'] in self.TrueValues:
            return {'contentType': 'application/json', 'Authorization1': self._auth_token}
        return {'contentType': 'application/json', 'Authorization2': self._auth_token}

    def authenticate(self):
        if self._auth_token:
            return
        if self.settings['is_sso'] in self.TrueValues:
            logger.info("No Oomnitza Authentication with is_sso = True.")
            self._auth_token = "Basic " + base64.encodestring(
                "{0}:{1}".format(self.settings['username'], self.settings['password'])
            ).strip()  # Weird, but it was adding a \n to the end of the string, which kinda breaks HTTP.
        else:
            try:
                auth_url = "{url}/api/request_token".format(**self.settings)
                response = self.post(
                    auth_url,
                    {'login': self.settings['username'],
                     'password': self.settings['password']},
                    post_as_json=False,
                )
                self._auth_token = response.json()["token"]
            except RequestException as exp:
                if isinstance(exp.message, basestring):
                    raise AuthenticationError("{} returned {}.".format(self.settings['url'], exp.message))
                if isinstance(exp.message.args[1], gaierror):
                    msg = "Unable to connect to {} ({}).".format(self.settings['url'], exp.message.args[1].errno)
                    if exp.message.args[1].errno == 8:
                        msg = "Unable to get address for {}.".format(self.settings['url'])
                    raise AuthenticationError(msg)
                raise AuthenticationError(str(exp))

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
        logger.warning("upload_assets() = %r", assets)

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

    def test_connection(self, options):
        self.authenticate()
        assert self._auth_token, "Failed to get auth_token."

    @classmethod
    def example_ini_settings(cls):
        settings = super(Connector, cls).example_ini_settings()
        return settings[1:]

    def get_mappings(self, name):
        url = "{0}/api/v2/mappings?name={1}".format(self.settings['url'], name)
        response = self.get(url)
        # logger.debug("%s mapping: %r", name, response.json())
        return response.json()
