from lib.connector import AssetsConnector

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################


class Connector(AssetsConnector):
    """
    Netbox devices connector 
    """
    MappingName = 'Netbox'
    Settings = {
        'url':          {'order': 1, 'example': 'https://NETBOX', 'default': ""},
        'auth_token':   {'order': 2, 'example': '*******', 'default': ""},
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
        self.logger.warning(f"{self.MappingName} has been DEPRECATED, this will be removed in the next release!!")

        next_url = self.settings['url'].rstrip('/') + '/api/dcim/devices/'
        while next_url:
            response = self.get(next_url).json()
            for record in response['results']:
                yield record

            next_url = response['next']

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################
