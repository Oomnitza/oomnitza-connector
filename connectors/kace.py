import logging

from lib.connector import AssetsConnector

LOG = logging.getLogger("connectors/kace")


class Connector(AssetsConnector):
    """
    KACE SMA integration
    """
    MappingName = 'KACE'
    Settings = {
        'url':                  {'order': 1, 'example': 'https://KACE_SMA', 'default': ''},
        'username':             {'order': 2, 'example': '***', 'default': ''},
        'password':             {'order': 3, 'example': '***', 'default': ''},
        'organization_name':    {'order': 4, 'example': 'Default', 'default': 'Default'},
        'api_version':          {'order': 5, 'example': '8', 'default': '8'},
    }

    FieldMappings = {
        'APPLICATIONS':      {'source': "software"},  # <-- default mapping for APPLICATIONS
    }

    DefaultConverters = {
        "Last_inventory":   "timestamp",
        "Last_sync":        "timestamp",
    }

    csrf_token = None

    def __init__(self, *args, **kwargs):
        super(Connector, self).__init__(*args, **kwargs)
        self.settings['url'] = self.settings['url'].rstrip('/')

    def authorize(self):
        """authorize in the KACE SMA"""
        auth_url = '{url}/ams/shared/api/security/login'.format(url=self.settings['url'])

        response = self.post(
            auth_url,
            headers={
                'Content-Type': 'application/json'
            },
            data={
                'userName': self.settings['username'],
                'password': self.settings['password'],
                'organizationName': self.settings['organization_name']
            },
        )

        self.csrf_token = response.headers['x-dell-csrf-token']

    def get_headers(self):
        if self.csrf_token:
            return {
                'x-dell-api-version': self.settings['api_version'],
                'x-dell-csrf-token': self.csrf_token
            }
        else:
            self.authorize()
            return self.get_headers()

    @staticmethod
    def prepare_asset_payload(record):
        """
        For some reason KACE API is returning the magic "empty" word for the certain attributes 
        instead of just empty string. Also for the certain date time values it can return "0000-00-00 00:00:00"
        if the value is unknown
        :return: 
        """
        magic_to_cleanup = (
            "empty",
            "0000-00-00 00:00:00"
        )

        all_installed_software = record.pop('Software')

        cleaned_record = {
            k: '' if v in magic_to_cleanup else v for k, v in record.items()
        }

        cleaned_record['software'] = [
            {
                'name': software['DISPLAY_NAME'],
                'version': software['DISPLAY_VERSION'],
                'path': None  # < -- to keep compatibility
            } for software in all_installed_software
        ]

        return cleaned_record

    def paginator(self, url, keyword):
        limit = 100
        offset = 0
        while True:
            paging_query_arg = 'paging=limit {limit} offset {offset}'.format(limit=limit, offset=offset)
            _url = (url + '&' + paging_query_arg) if '?' in url else (url + '?' + paging_query_arg)
            response = self.get(_url).json()
            records = response.get(keyword, [])
            if not records:
                break

            for record in records:
                yield record

            offset += limit

    def _load_records(self, options):

        url = '{url}/api/inventory/machines?shaping=machine all,software standard'.format(url=self.settings['url'])

        for record in self.paginator(url, 'Machines'):
            yield self.prepare_asset_payload(record)
