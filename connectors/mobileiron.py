
import base64
import logging
import time
import math

from requests import ConnectionError, HTTPError
from lib.connector import AuditConnector

LOG = logging.getLogger("connectors/mobileiron")


class Connector(AuditConnector):
    MappingName = 'MobileIron'
    RetryCount = 10

    Settings = {
        'url':        {'order': 1, 'default': "https://na1.mobileiron.com"},
        'username':   {'order': 2, 'example': "username@example.com"},
        'password':   {'order': 3, 'example': "change-me"},
        'partitions': {'order': 4, 'example': '["Drivers"]', 'is_json': True},
        'sync_field': {'order': 5, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self._retry_counter = 0

    def get_headers(self):
        auth_string = self.settings['username'] + ":" + self.settings['password']
        headers = {
            'Authorization': b"Basic " + base64.b64encode(auth_string),
            'Accept': 'application/json'
        }
        return headers

    def do_test_connection(self, options):
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
            if self.settings['partitions'] == "All" or partition['name'] in self.settings['partitions']:
                for device in self.fetch_all_devices_for_partition(partition['id']):
                    yield device
            else:
                LOG.debug("Skipping partition %r", partition)

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
                response.raise_for_status()
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
