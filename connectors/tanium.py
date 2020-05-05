import logging

from lib.connector import AssetsConnector

LOG = logging.getLogger("connectors/tanium")


class Connector(AssetsConnector):
    MappingName = 'Tanium'
    Settings = {
        'url':              {'order': 1, 'example': 'https://TANIUM_SERVER', 'default': ''},
        'username':         {'order': 2, 'example': '***', 'default': ''},
        'password':         {'order': 3, 'example': '***', 'default': ''},
        'domain':           {'order': 4, 'example': '', 'default': ''},
        'view':             {'order': 5, 'example': '', 'default': ''},
    }

    FieldMappings = {
        'APPLICATIONS':     {'source': "oomnitza_software"},  # <-- default mapping for APPLICATIONS
    }

    session_token = None

    def __init__(self, *args, **kwargs):
        super(Connector, self).__init__(*args, **kwargs)
        self.settings['url'] = self.settings['url'].rstrip('/')

    def authorize(self):
        """authorize in the Tanium"""
        auth_url = '{url}/api/v2/session/login'.format(url=self.settings['url'])

        response = self.post(
            auth_url,
            headers={
                'Content-Type': 'application/json'
            },
            data={
                'username': self.settings['username'],
                'password': self.settings['password'],
                'domain': self.settings['domain']
            },
        ).json()

        self.session_token = response['data']['session']

    def get_headers(self):

        if not self.session_token:
            self.authorize()

        return {
            'session': self.session_token
        }

    def asset_api_paginator(self, url):
        limit = 100
        minimumAssetId = 1
        while True:
            _url = '{url}?limit={limit}&minimumAssetId={minimumAssetId}'.format(url=url, limit=limit, minimumAssetId=minimumAssetId)
            if self.settings['view']:
                _url += '&viewId={view}'.format(view=self.settings['view'])
            response = self.get(_url).json()
            data = response['data']
            if not data:
                break

            for device in data:
                yield device

            minimumAssetId = response['meta']['nextAssetId']

    def get_assets(self):
        assets_url = '{url}/plugin/products/asset/v1/assets'.format(url=self.settings['url'])
        return self.asset_api_paginator(assets_url)

    @staticmethod
    def prepare_asset_payload(device_info):
        device_info['oomnitza_software'] = [
            {
                'name': software['name'],
                'version': software['version'],
                'path': None  # < -- to keep compatibility
            } for software in (device_info.get('ci_installed_application') or [])
        ]
        return device_info

    def _load_records(self, options):
        for device in self.get_assets():
            yield self.prepare_asset_payload(device)
