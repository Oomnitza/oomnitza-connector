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
        'api_token': {'order': 2, 'example': "", 'default': ""},
        'username':  {'order': 3, 'example': "oomnitza-sa", 'default': ""},
        'password':  {'order': 4, 'example': "ThePassword", 'default': ""},

    }
    # no FieldMappings for oomnitza connector
    FieldMappings = {}

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self._test_headers = []
        self.authenticate()

    def get_field_mappings(self, extra_mappings):
        """ Override base to always return an empty mapping set.
        :param extra_mappings:
        :return: an empty dict()
        """
        return {}

    def get_headers(self):
        if self.settings['api_token']:
            return {'Content-Type': 'application/json; charset=utf-8', 'Authorization2': self.settings['api_token']}
        # these empty headers because of the old implementation of request_token endpoint, body SHOULD NOT be interpreted as JSON here!
        return {}

    def authenticate(self):
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
            if len(exp.message.args) > 2 and isinstance(exp.message.args[1], gaierror):
                msg = "Unable to connect to {} ({}).".format(self.settings['url'], exp.message.args[1].errno)
                if exp.message.args[1].errno == 8:
                    msg = "Unable to get address for {}.".format(self.settings['url'])
                raise AuthenticationError(msg)
            raise AuthenticationError(str(exp))
        # LOG.debug("authenticate(1): self.settings['api_token'] = %r", self.settings['api_token'])

    def upload_users(self, users, options):
        # logger.debug("upload_users( %r )", users)
        url = "{url}/api/v2/bulk/users?VERSION={VERSION}".format(**self.settings)
        if 'normal_position' in options:
            url += "&normal_position={}".format(options['normal_position'])
        url += "&agent_id={}".format(options.get('agent_id', 'Unknown'))

        response = self.post(url, users)
        # logger.debug("response = %r", response.text)
        return response

    def upload_audit(self, computers, options):
        # logger.debug("upload_users( %r )", users)
        url = "{url}/api/v2/bulk/audit?VERSION={VERSION}".format(**self.settings)
        response = self.post(url, computers)
        # logger.debug("response = %r", response.text)
        return response

    @staticmethod
    def _test_upload_users(users, options):
        pprint.pprint(users)

    @staticmethod
    def _test_upload_audit(computers, options):
        pprint.pprint(computers)

    def perform_sync(self, oomnitza_connector, options):
        """
        Can't call perform_sync on Oomnitza connector because perform_sync in the
        other connectors is what is called to sync to oomnitza. Calling this would
        basically be asking: 'please sync the oomnitza data with oomnitza.'
        """
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
        return response.json()

    def get_location_mappings(self, id_field, label_field):
        try:
            url = "{0}/api/v3/locations".format(self.settings['url'])
            response = self.get(url)
            mappings = {loc[label_field]: loc[id_field] for loc in response.json() if loc.get(id_field, None) and loc.get(label_field, None)}
            LOG.debug("Location Map to %s: External Value -> Oomnitza ID", id_field)
            for name in sorted(mappings.keys()):
                LOG.info(u"    %s -> %s" % (name, mappings[name]))
            return mappings
        except:
            LOG.exception("Failed to load Locations from Oomnitza.")
            return {}

    def get_settings(self, connector, *keys):
        try:
            url = "{0}/api/v3/settings/{1}/{2}".format(
                self.settings['url'],
                connector,
                '/'.join(keys)
            )
            response = self.get(url)
            return response.json()['value']  ##!!!!!
        except:
            LOG.exception("Failed to load settings from Oomnitza.")
            raise

    def get_setting(self, key):
        try:
            url = "{0}/api/v3/settings/{1}".format(
                self.settings['url'],
                key
            )
            response = self.get(url)
            return response.json()['value']
        except:
            LOG.exception("Failed to load setting from Oomnitza.")
            raise
