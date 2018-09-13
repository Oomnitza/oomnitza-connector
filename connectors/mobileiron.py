import base64
import logging
import math
import time

from enum import Enum

from lib.connector import AuditConnector

LOG = logging.getLogger("connectors/mobileiron")

Version = Enum('Version', ['v1', 'v2'])  # TODO: set proper cases


class Connector(AuditConnector):
    MappingName = 'MobileIron'
    RetryCount = 10

    Settings = {
        'url':        {'order': 1, 'default': "https://na1.mobileiron.com"},
        'username':   {'order': 2, 'example': "username@example.com"},
        'password':   {'order': 3, 'example': "change-me"},
        'partitions': {'order': 4, 'example': '["Drivers"]', 'is_json': True},
        'sync_field': {'order': 5, 'example': '24DCF85294E411E38A52066B556BA4EE'},
        'api_version': {'order': 6, 'example': '1', 'default': '1'}
    }

    api_version = None

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        if self.settings.get('api_version') == '2':
            self.api_version = Version.v2
        else:
            self.api_version = Version.v1
        self._retry_counter = 0

    def get_headers(self):
        auth_string = self.settings['username'] + ":" + self.settings['password']
        headers = {
            'Authorization': b"Basic " + base64.b64encode(auth_string),
            'Accept': 'application/json'
        }
        return headers

    def load_devices_api_v1(self, *a, **kw):
        for partition in self.fetch_all_partitions():
            if self.settings['partitions'] == "All" or partition['name'] in self.settings['partitions']:
                for device in self.fetch_all_devices_for_partition(partition['id']):
                    yield device
            else:
                LOG.debug("Skipping partition %r", partition)

    def load_spaces_api_v2(self):
        url = self.settings['url'] + "/api/v2/device_spaces/mine?limit={limit}&offset={offset}"

        response = self.get(url)
        spaces = response.json()['results']

        for space in spaces:
            yield space['id']

    def load_space_fields_api_v2(self, space):
        url = self.settings['url'] + "/api/v2/device_spaces/criteria?adminDeviceSpaceId={space}".format(space=space)

        response = self.get(url)
        fields = response.json()['results']

        return [_['name'] for _ in fields]

    def load_devices_api_v2(self, *a, **kw):

        url_template = self.settings['url'] + "/api/v2/devices?adminDeviceSpaceId={space}&fields={fields}&labelId=-1&limit={limit}&offset={offset}"

        for space in self.load_spaces_api_v2():

            limit = 50
            offset = 0

            fields = ','.join(self.load_space_fields_api_v2(space))
            while True:
                response = self.get(url_template.format(limit=limit, offset=offset, space=space, fields=fields))
                response_body = response.json()
                devices = response_body['results']

                for device in devices:
                    yield device

                if not response_body['hasMore']:
                    break

                offset += limit

    def _load_records(self, options):
        generator = {

            Version.v1: self.load_devices_api_v1(),
            Version.v2: self.load_devices_api_v2()

        }[self.api_version]

        # noinspection PyTypeChecker
        for device in generator:
            yield device

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
        url = "{0}/api/v1/device?dmPartitionId={1}&rows={2}&start={3}&sortFields[0].name=lastCheckin&sortFields[0].order=DESC"
        start = -1
        total_count = 0
        cutoff = int((time.time()-(60*60*24*1.5))*1000)  # 60*60*24*3 is 1.5 days in seconds.

        LOG.info("cutoff has been set to: %s", cutoff)
        while start < total_count:
            if self._retry_counter > Connector.RetryCount:
                LOG.error("Retry limit of %s attempts has been exceeded.", Connector.RetryCount)
                break
            if start == -1:
                start = 0
            try:
                response = self.get(url.format(self.settings['url'], partition_id, rows, start))
                result = response.json()['result']
                if total_count == 0:
                    total_count = result['totalCount']

                LOG.info("Processing devices %s-%s of %s", start, start+len(result['searchResults']), total_count)
                # yield result['searchResults']
                results = [r for r in result['searchResults'] if r['lastCheckin'] >= cutoff]
                if results:
                    yield results
                else:
                    LOG.info("No more records found after cutoff date.")
                    break  # we have run out of records to process. The rest will be before the cutoff date.
                start += len(result['searchResults'])
            except:
                LOG.exception("Error getting devices for partition. Attempt #%s failed.", self._retry_counter+1)
                self._retry_counter += 1
                sleep_secs = math.pow(2, min(self._retry_counter, 8))
                LOG.warning("Sleeping for %s seconds.", sleep_secs)
                time.sleep(sleep_secs)
