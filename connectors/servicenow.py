import logging

from gevent.pool import Pool
from requests.auth import _basic_auth_str

from lib.connector import AuditConnector

LOG = logging.getLogger("connectors/servicenow")


class Connector(AuditConnector):
    """
    ServiceNow Assets integration
    """
    MappingName = 'ServiceNow'
    Settings = {
        'url':                  {'order': 1, 'example': 'https://xxx.service-now.com'},
        'username':             {'order': 2, 'example': "***", 'default': ""},
        'password':             {'order': 3, 'example': "***", 'default': "",},
        'sync_field':           {'order': 4, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }
    DefaultConverters = {

    }
    FieldMappings = {
        'APPLICATIONS':      {'source': "software"},  # <-- default mapping for APPLICATIONS
    }

    def get_headers(self):
        return {
            'Authorization': _basic_auth_str(self.settings['username'], self.settings['password']),
            'Accept': 'application/json',
        }

    @staticmethod
    def prepare_representation(record):
        """
        Extract the display value (if available) from the object representation to build 
        the simple flat key-value representation suitable for Oomnitza API
        :param record: 
        :return: 
        """
        return {key: (value if not isinstance(value, dict) else value.get('display_value')) for key, value in record.items()}

    def paginator(self, url):
        """
        API paginator, yield the dicts representing the certain item
        """
        limit = 100
        offset = 0
        while True:
            paging_query_arg = 'sysparm_limit={limit}&sysparm_offset={offset}'.format(limit=limit, offset=offset)
            _url = (url + '&' + paging_query_arg) if '?' in url else (url + '?' + paging_query_arg)
            response = self.get(_url).json()
            records = response.get('result', [])
            if not records:
                break

            for record in records:
                yield record

            offset += limit

    def get_asset_associated_software(self, asset_ci_id):
        """
        Fetch all the software installed
        """
        url = self.settings['url'] + "/api/now/table/cmdb_software_instance?" \
                                     "sysparm_query=installed_on={asset_ci_id}&" \
                                     "sysparm_fields=software.version,software.name".format(asset_ci_id=asset_ci_id)

        software = map(self.prepare_representation, list(self.paginator(url)))

        return [
                {
                    'name': record['software.name'],
                    'version': record['software.version'],
                    'path': None  # < -- to keep compatibility
                } for record in software
        ]

    def prepare_asset_payload(self, device):
        """
        Gather the software and hardware representation
        """
        ci_id = device['ci']['value']

        device_info = dict({
            'hardware': self.prepare_representation(device),
            'software': self.get_asset_associated_software(ci_id)
        })
        return device_info

    def _load_records(self, options):
        pool_size = self.settings['__workers__']

        connection_pool = Pool(size=pool_size)

        # fetch all the hardware assets ordered by asset tag value
        hardware_asset_url = self.settings['url'] + "/api/now/table/alm_hardware?" \
                                                    "sysparm_display_value=all&" \
                                                    "sysparm_query=^ORDERBYasset_tag"

        for asset in connection_pool.imap(
                self.prepare_asset_payload,
                self.paginator(hardware_asset_url),
                maxsize=pool_size):
            yield asset
