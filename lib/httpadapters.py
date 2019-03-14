import ssl

from requests.adapters import HTTPAdapter, DEFAULT_POOLBLOCK
from urllib3 import Retry, PoolManager

retries = Retry(total=10,
                backoff_factor=0.5,
                method_whitelist=False,
                status_forcelist=[500, 502, 503, 504])


class BaseHttpAdapter(HTTPAdapter):
    """base "Transport adapter" that allows us to force protocol use."""
    Protocol = None

    def init_poolmanager(self, connections, maxsize, block=DEFAULT_POOLBLOCK, **pool_kwargs):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=self.Protocol)


class Sslv23HttpAdapter(BaseHttpAdapter):
    """"Transport adapter" that allows us to force protocol to SSLv23."""
    Protocol = ssl.PROTOCOL_SSLv23


class Tlsv1HttpAdapter(BaseHttpAdapter):
    """"Transport adapter" that allows us to force protocol to TLSv1."""
    Protocol = ssl.PROTOCOL_TLSv1


AdapterMap = {
    'ssl': Sslv23HttpAdapter,
    'sslv23': Sslv23HttpAdapter,
    'tls': Tlsv1HttpAdapter,
    'tls1': Tlsv1HttpAdapter,
}

if getattr(ssl, '_SSLv2_IF_EXISTS', False):
    class Sslv2HttpAdapter(BaseHttpAdapter):
        """"Transport adapter" that allows us to force protocol to SSLv2."""
        Protocol = ssl.PROTOCOL_SSLv2

    AdapterMap['sslv2'] = Sslv2HttpAdapter
