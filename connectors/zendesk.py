from lib.connector import UserConnector
from requests.auth import _basic_auth_str

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################


class Connector(UserConnector):
    MappingName = 'Zendesk'
    Settings = {
        'system_name':        {'order': 1, 'example': "oomnitza"},
        'api_token':          {'order': 2, 'example': "YOUR Zendesk API TOKEN"},
        'username':           {'order': 3, 'example': "username@example.com"},
        'default_role':       {'order': 4, 'example': 25, 'type': int},
        'default_position':   {'order': 5, 'example': 'Employee'},
        'load_organizations': {'order': 6, 'default': False},
    }

    FieldMappings = {
        'USER':           {'source': "email"},
        'FIRST_NAME':     {'source': "name", 'converter': "first_from_full"},
        'LAST_NAME':      {'source': "name", 'converter': "last_from_full"},
        'EMAIL':          {'source': "email"},
        'PHONE':          {'source': "phone"},
        'PERMISSIONS_ID': {'setting': "default_role"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.url_template = "https://%s.zendesk.com/api/{0}" % self.settings['system_name']

    def get_headers(self):
        return {
            'Accept': 'application/json',
            'Authorization':  _basic_auth_str(f"{self.settings['username']}/token", self.settings['api_token'])
        }

    def _load_records(self, options):
        self.logger.warning(
            f"{__name__.split('.')[1].upper()} has been DEPRECATED, this will be removed in the next major release!!")

        organization_map = self._load_organizations_if_needed()
        url = self.url_template.format("v2/users.json")
        while url:
            response = self.get(url)
            response = response.json()
            if 'users' not in response:
                # The 'users' key doesn't exist.
                # We've likely gotten all the users we're going to get
                url = None
            else:
                for user in response['users']:
                    if organization_map:
                        org = organization_map.get(user['organization_id'], None)
                        if org:
                            user['organization'] = org
                        else:
                            user['organization'] = {}
                    yield user
                url = response['next_page']

    def _load_organizations_if_needed(self):
        """Loads and returns the Zendesk organizations if 'organization_id' is a source field.

        Checks the field_mappings to see if 'organization_id' is a source field.

        Returns
        -------
            dict
                A dict mapping organization_id -> organization_name, or None if 'organization_id' is not a source field.

        """
        if not self.settings.get('load_organizations'):
            return None

        self.logger.info("Loading Zendesk Organizations...")

        organization_map = {}
        url = self.url_template.format("v2/organizations.json")
        while url:
            response = self.get(url)
            response = response.json()
            if 'organizations' not in response:
                # The 'organizations' key doesn't exist.
                # We've likely gotten all the organizations we're going to get
                url = None
            else:
                for organization in response['organizations']:
                    organization_map[organization["id"]] = organization
                url = response['next_page']

        self.logger.info("Loaded %s organizations.", len(organization_map))
        return organization_map

###########################################################################
###                                                                     ###
###   This File is Deprecated and will be removed in the next release   ###
###   Please do not use this file for fetching data.                    ###
###                                                                     ###
###########################################################################
