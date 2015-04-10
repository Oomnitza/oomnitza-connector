
import os
import logging

from suds.client import Client
from suds.wsse import Security, UsernameToken

from lib.connector import AssetConnector, AuthenticationError

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class Connector(AssetConnector):
    MappingName = 'Jasper'

    Settings = {
        'wsdl_path':  {'order': 1, 'default': "http://api.jasperwireless.com/ws/schema/Terminal.wsdl"},
        'username':   {'order': 2, 'example': "username"},
        'password':   {'order': 3, 'example': "qwerty123"},
        'api_token':  {'order': 4, 'example': "220c9a8c-8e62-4b83-8a28-fc5b99674246"},
        'storage':    {'order': 4, 'default': "storage.db"},
        'sync_field': {'order': 5, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    FieldMappings = {
        '24DCF85294E411E38A52066B556BA4EE': {'source': 'iccid'},
        '1F331776A68911E4912606283F60DC81': {'source': "ratePlan"},
        '2992C6E4A68911E496C506283F60DC81': {'source': 'imei'},
    }

    def __init__(self, settings):
        super(Connector, self).__init__(settings)
        self.url_temlate = "%s/api/v1/mdm/devices/search?pagesize={0}&page={1}" % self.settings['wsdl_path']
        self.jasper_client = None

    def test_connection(self, options):
        try:
            self.authenticate()
            return {'result': True, 'error': ''}
        except AuthenticationError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        for id_chunk in self.get_modified_terminals():
            details = self.get_terminal_details(id_chunk)
            for detail in details:
                yield detail

    def parse_wsdl(self):
        """
        Parses WSDL file to determine available services and objects.
        Sets WSSE security object as well.
        """
        logger.debug("Parsing WSDL: %s...", self.settings['wsdl_path'])
        self.jasper_client = Client(self.settings['wsdl_path'])

        # WSSE security
        security = Security()
        token = UsernameToken(self.settings['username'], self.settings['password'])
        security.tokens.append(token)
        self.jasper_client.set_options(wsse=security, timeout=600)

    def authenticate(self):
        return self.parse_wsdl()

    def get_modified_terminals(self):
        """
        GetModifiedTerminals - SOAP Request

        Get the terminals accessible to this user which have been modified since the given time
        (not inclusive). If the "since" parameter is omitted, it means return all iccids.
        The result will be a list of iccids ordered by oldest first. This API call is useful for
        keeping client side data in sync with Jasper's.
        """
        # extracting since variable
        storage_path = '../{}'.format(self.settings['storage'])  # FixMe: fix me!
        if os.path.exists(storage_path):
            with open(storage_path, 'r') as f:
                since = unicode(f.read().strip())
        else:
            since = '2015-03-04T00:00:00Z'

        logger.debug("Fetching Modified Terminal ID(s) since %s...", since)
        _args = dict(
            since=since,
            licenseKey=self.settings['api_token']
        )
        response = self.jasper_client.service.GetModifiedTerminals(**_args)
        ids = response['iccids'][0]
        logger.debug("Found %s modified terminals.", len(ids))
        last_modified_date = since
        try:
            while ids:
                to_send, ids = ids[:10], ids[10:]
                logger.debug("yielding %r for processing.", to_send)
                yield to_send
                last_modified_date = to_send[-1]['dateModified']
        finally:
            with open(storage_path, 'w') as f:
                new_since = last_modified_date
                f.write(new_since)

    def get_terminal_details(self, iccids):
        """
        GetTerminalDetails - SOAP Request

        Get the attributes for a list of terminals (given list of iccids).
        At least one iccid should be provided, maximum limit is 50 for performance reasons.

        The returned results are not guaranteed to be in the same ordering as the request.
        Not found terminals will not be part of the result.
        """
        _args = dict(
            licenseKey=self.settings['api_token'],
            iccids={'iccid': [v for v in iccids]}
        )
        details = self.jasper_client.service.GetTerminalDetails(**_args)
        details = [self.suds_to_dict(d) for d in details.terminals[0]]

        return details

    @classmethod
    def suds_to_dict(cls, obj):
        return {v[0]: v[1] for v in obj}

    @classmethod
    def default(cls, o):
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        return None
