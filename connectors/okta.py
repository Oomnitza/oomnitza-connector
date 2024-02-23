from lib import TrueValues
from lib.connector import UserConnector

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################


class Connector(UserConnector):
    MappingName = 'Okta'
    Settings = {
        'url':              {'order': 1, 'default': "https://example-admin.okta.com"},
        'api_token':        {'order': 2, 'example': "YOUR Okta API TOKEN"},
        'default_role':     {'order': 3, 'example': 25, 'type': int},
        'default_position': {'order': 4, 'example': 'Employee'},
        'deprovisioned':    {'order': 5, 'default': 'false', 'example': 'false'},
    }

    FieldMappings = {
        'USER':           {'source': "profile.login"},
        'FIRST_NAME':     {'source': "profile.firstName"},
        'LAST_NAME':      {'source': "profile.lastName"},
        'EMAIL':          {'source': "profile.email"},
        'PHONE':          {'source': "profile.mobilePhone"},
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'SSWS %s' % self.settings['api_token']
        }

    def not_deprovisioned_users_generator(self, options):
        """
        Generator returning the users with status != 'DEPROVISIONED'
        
        See the https://developer.okta.com/docs/api/resources/users.html#list-all-users for details
         """
        page = "{0}/api/v1/users?limit={1}".format(self.settings['url'], options.get('limit', 100))
        index = 0
        while page:
            response = self.get(page)
            for user in response.json():
                index += 1
                yield user

            page = response.links.get('next', {}).get('url', None)

    def deprovisioned_users_generator(self, options):
        """
        Generator returning the users with status == 'DEPROVISIONED'

        See the https://developer.okta.com/docs/api/resources/users.html#list-users-with-a-filter for details
         """
        page = '{0}/api/v1/users?limit={1}&filter=status eq "DEPROVISIONED"'.format(self.settings['url'], options.get('limit', 100))
        index = 0
        while page:
            response = self.get(page)
            for user in response.json():
                index += 1
                yield user

            page = response.links.get('next', {}).get('url', None)

    def _load_records(self, options):
        self.logger.warning(
            f"{__name__.split('.')[1].upper()} has been DEPRECATED, this will be removed in the next major release!!")

        for user in self.not_deprovisioned_users_generator(options):
            yield user

        if self.settings.get('deprovisioned') in TrueValues:
            for user in self.deprovisioned_users_generator(options):
                yield user

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################
