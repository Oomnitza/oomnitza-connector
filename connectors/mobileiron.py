
import base64
import logging

from requests import ConnectionError, HTTPError
from lib.connector import AssetConnector

logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class Connector(AssetConnector):
    MappingName = 'MobileIron'

    Settings = {
        'url':        {'order': 1, 'default': "https://na1.mobileiron.com"},
        'username':   {'order': 2, 'example': "trent.seed@oomnitza.com"},
        'password':   {'order': 3, 'example': "a1S2d3F490"},
        'partitions': {'order': 4, 'example': '["Drivers"]', 'is_json': True},
        'sync_field': {'order': 5, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    FieldMappings = {
        '24DCF85294E411E38A52066B556BA4EE': {'source': 'serialNumber'},
        'EB4CEBD0A68811E49E5C06283F60DC81': {'source': "currentCarrierNetwork"},
        '2992C6E4A68911E496C506283F60DC81': {'source': 'imei'},
        '384AFD88A68811E4912606283F60DC81': {'source': 'deviceModel'},
        '2814A3A6A68811E4912606283F60DC81': {'source': 'manufacturer'},
        'D2F821EEA68811E4B01E06283F60DC81': {'source': 'wifiMacAddress'},
        '82BA283E970E11E28A24525400385B84': {'source': 'platformType'},
    }

    def __init__(self, settings):
        super(Connector, self).__init__(settings)

    def get_headers(self):
        auth_string = self.settings['username'] + ":" + self.settings['password']
        headers = {
            'Authorization': b"Basic " + base64.b64encode(auth_string),
            'Accept': 'application/json'
        }
        return headers

    def test_connection(self, options):
        try:
            url = self.settings['url'] + "/api/v1/tenant/partition/device?start=0&rows=1"
            response = self.get(url)
            response.raise_for_status()
            return {'result': True, 'error': ''}
        except ConnectionError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}
        except HTTPError as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        for partition in self.fetch_all_partitions():
            if partition['name'] in self.settings['partitions']:
                for device in self.fetch_all_devices_for_partition(partition['id']):
                    yield device
            else:
                logger.debug("Skipping partition %r", partition)

    def fetch_all_partitions(self):
        """
        Fetches all available device partitions using the MobileIron REST API.
        /api/v1/tenant/partition/device
        """
        url = self.settings['url'] + "/api/v1/tenant/partition/device"
        response = self.get(url)
        response.raise_for_status()

        partitions = [{'id': x['id'], 'name': x['name']} for x in response.json()['result']['searchResults']]
        # logger.debug("partitions = %r", partitions)
        return partitions

    def fetch_all_devices_for_partition(self, partition_id, rows=500):
        """
        Fetches all available device for a provided partition using the MobileIron REST API.
        Yields response objects for all each partition offset/page.

        Note: 'offset' does not operate as the MobileIron documentation indicates. We should
        instead use 'start' and pass the latest index

        /api/v1/device?dmPartitionId=X
        """
        url = "{0}/api/v1/device?dmPartitionId={1}&rows={2}&start={3}&sortFields[0].name=id&sortFields[0].order=ASC"
        start = -1
        total_count = 0
        while start < total_count:
            if start == -1:
                start = 0
            response = self.get(url.format(self.settings['url'], partition_id, rows, start))
            response.raise_for_status()
            result = response.json()['result']
            if total_count == 0:
                total_count = result['totalCount']

            logger.info("Processing devices %s-%s of %s", start, start+len(result['searchResults']), total_count)
            yield result['searchResults']
            start += len(result['searchResults'])
