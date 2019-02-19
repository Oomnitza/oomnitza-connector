import adal

from lib.version import VERSION


class GraphAPIResourceFetcher(object):
    """
    Fetches data from Micorosoft Graph API
    https://docs.microsoft.com/en-us/graph/use-the-api?toc=./ref/toc.json&view=graph-rest-beta
    """
    __resource = "https://graph.microsoft.com"
    __authority_base_url = 'https://login.microsoftonline.com'

    headers = None

    def __init__(self, version='v1.0'):
        self.version = version

    def get_headers(self, tenant, client_id, secret):
        if self.headers is not None:
            return self.headers

        context = adal.AuthenticationContext(self.__authority_base_url + '/' + tenant)
        token = context.acquire_token_with_client_credentials(
            self.__resource,
            client_id,
            secret
        )

        self.headers = {
            'User-Agent': 'OomnitzaConnector v.{version}'.format(version=VERSION),
            'Authorization': 'Bearer {0}'.format(token["accessToken"]),
        }

        return self.headers

    def pagination_wrapper(self, fetcher, url):
        """
        Iteratively goes through the results of the page and fetches the new pages if those are available
        """
        url_to_fetch = self.__resource + '/{version}/'.format(version=self.version) + url
        while True:
            response = fetcher(url_to_fetch).json()
            records = response['value']
            next_url = response.get('@odata.nextLink')

            for record in records:
                yield record

            url_to_fetch = next_url
            if not url_to_fetch:
                raise StopIteration
