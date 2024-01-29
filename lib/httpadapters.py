import base64
import ssl
import tempfile
from typing import Optional

import OpenSSL
from requests.adapters import DEFAULT_POOLBLOCK
from requests.adapters import HTTPAdapter
from urllib3 import Retry, PoolManager
from urllib3.util.ssl_ import create_urllib3_context

from constants import MTLSType

retries = Retry(
    total=10,
    backoff_factor=0.5,
    allowed_methods=False,
    status_forcelist=[500, 502, 503, 504]
)


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


class SSLAdapter(HTTPAdapter):
    def __init__(self, certfile, keyfile=None, password=None, *args, **kwargs):
        self._certfile = certfile
        self._keyfile = keyfile
        self._password = password

        super(self.__class__, self).__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        self._add_ssl_context(kwargs)
        return super(self.__class__, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        self._add_ssl_context(kwargs)
        return super(self.__class__, self).proxy_manager_for(*args, **kwargs)

    def _add_ssl_context(self, kwargs):
        context = create_urllib3_context()
        context.load_cert_chain(
            certfile=self._certfile,
            keyfile=self._keyfile,
            password=str(self._password)
        )
        kwargs['ssl_context'] = context


def init_pfx_ssl_adapter(pfx_bytes: bytes, pfx_password: str) -> SSLAdapter:
    with tempfile.NamedTemporaryFile(suffix='.pem') as cert_pem:
        p12 = OpenSSL.crypto.load_pkcs12(pfx_bytes, pfx_password)

        cert_pem = open(cert_pem.name, 'wb')
        cert_pem.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, p12.get_privatekey()))
        cert_pem.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, p12.get_certificate()))

        ca = p12.get_ca_certificates()
        if ca is not None:
            for cert in ca:
                cert_pem.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert))

        cert_pem.close()

        ssl_adapter = SSLAdapter(
            certfile=cert_pem.name,
            max_retries=retries
        )

    return ssl_adapter


def init_cert_key_ssl_adapter(cert_str: str, key_str: str, key_password: str) -> SSLAdapter:
    with tempfile.NamedTemporaryFile(suffix='.pem') as cert_pem,\
         tempfile.NamedTemporaryFile(suffix='.pem') as key_pem:

        cert_pem = open(cert_pem.name, 'w')
        cert_pem.write(cert_str)
        cert_pem.close()

        key_pem = open(key_pem.name, 'w')
        key_pem.write(key_str)
        key_pem.close()

        ssl_adapter = SSLAdapter(
            certfile=cert_pem.name,
            keyfile=key_pem.name,
            password=key_password,
            max_retries=retries
        )

    return ssl_adapter


def init_mtls_ssl_adapter(credential_certificate: dict) -> Optional[SSLAdapter]:
    ssl_adapter = None
    cert_type = credential_certificate['type']

    if cert_type == MTLSType.PFX:
        ssl_adapter = init_pfx_ssl_adapter(
            pfx_bytes=base64.b64decode(credential_certificate['pfx']),
            pfx_password=credential_certificate['password']
        )

    elif cert_type == MTLSType.CERT_KEY:
        ssl_adapter = init_cert_key_ssl_adapter(
            cert_str=base64.b64decode(credential_certificate['cert']).decode('utf-8'),
            key_str=base64.b64decode(credential_certificate['key']).decode('utf-8'),
            key_password=credential_certificate['password']
        )

    return ssl_adapter
