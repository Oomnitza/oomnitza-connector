from lib.connector import AuditConnector


class Connector(AuditConnector):
    """
    Netbox devices connector 
    """
    MappingName = 'Netbox'
    Settings = {
        'url':          {'order': 1, 'example': 'https://NETBOX', 'default': ""},
        'auth_token':   {'order': 2, 'example': '*******', 'default': ""},
        'sync_field':   {'order': 3, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    def get_headers(self):
        return {
            "Accept": "application/json",
            "Authorization": "Token %s" % self.settings['auth_token']
        }

    def _fetcher(self, url):
        data = self.get(url)
        for record in data['results']:
            yield record

    def _load_records(self, options):

        next_url = self.settings['url'].rstrip('/') + '/api/dcim/devices/'
        while next_url:
            response = self.get(next_url).json()
            for record in response['results']:
                yield record

            next_url = response['next']
