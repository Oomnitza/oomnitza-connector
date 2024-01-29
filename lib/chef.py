import base64
import datetime
import hashlib
import re
from typing import Optional

from Cryptodome.PublicKey import RSA
from Cryptodome.PublicKey.RSA import RsaKey
from Cryptodome.Util import number


def load_private_key(key_path: str) -> RsaKey:
    with open(key_path, "r") as key_file:
        return RSA.import_key(key_file.read())


def rsa_private_encrypt(key: RsaKey, data: str) -> bytes:
    """The chef server is only accepting the output of RSA_private_encrypt.
    This function is recreating the behaviour of RSA_private_encrypt
    and will always produce the same signature for a given input data
    See: https://stackoverflow.com/questions/72686682/implementing-openssl-private-encrypt-in-latest-python-3-versions
    """
    encoded_data = data.encode("UTF-8")

    mod_bits = number.size(key.n)
    k = number.ceil_div(mod_bits, 8)

    ps = b'\xFF' * (k - len(data) - 3)
    em = b'\x00\x01' + ps + b'\x00' + encoded_data

    em_int = number.bytes_to_long(em)
    m_int = key._decrypt(em_int)
    signature = number.long_to_bytes(m_int, k)

    return signature


def _ruby_b64encode(value):
    """The Ruby function Base64.encode64 automatically breaks things up
    into 60-character chunks.
    """
    b64 = base64.b64encode(value)
    for i in range(0, len(b64), 60):
        yield b64[i:i + 60].decode()


def ruby_b64encode(value):
    return '\n'.join(_ruby_b64encode(value))


def sha1_base64(value):
    """An implementation of Mixlib::Authentication::Digester."""
    return ruby_b64encode(hashlib.sha1(value.encode()).digest())


class UTC(datetime.tzinfo):
    """UTC timezone stub."""

    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return 'UTC'

    def dst(self, dt):
        return self.ZERO


utc = UTC()


def canonical_time(timestamp):
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone(utc).replace(tzinfo=None)
    return timestamp.replace(microsecond=0).isoformat() + 'Z'


canonical_path_regex = re.compile(r'/+')


def canonical_path(path):
    path = canonical_path_regex.sub('/', path)
    if len(path) > 1:
        path = path.rstrip('/')
    return path


def canonical_request(http_method, path, hashed_body, timestamp, user_id):
    # Canonicalize request parameters
    http_method = http_method.upper()
    path = canonical_path(path)
    if isinstance(timestamp, datetime.datetime):
        timestamp = canonical_time(timestamp)
    hashed_path = sha1_base64(path)
    return (f'Method:{http_method}\n'
            f'Hashed Path:{hashed_path}\n'
            f'X-Ops-Content-Hash:{hashed_body}\n'
            f'X-Ops-Timestamp:{timestamp}\n'
            f'X-Ops-UserId:{user_id}')


def sign_request(key_path: str, http_method: str, path: str, body: Optional[str], timestamp, user_id: str):
    """Generate the needed headers for the Opscode authentication protocol."""
    timestamp = canonical_time(timestamp)
    hashed_body = sha1_base64(body or '')

    # Simple headers
    headers = {
        'x-ops-sign': 'version=1.0',
        'x-ops-userid': user_id,
        'x-ops-timestamp': timestamp,
        'x-ops-content-hash': hashed_body,
    }

    # Create RSA signature
    key = load_private_key(key_path)
    req = canonical_request(http_method, path, hashed_body, timestamp, user_id)
    sig = _ruby_b64encode(rsa_private_encrypt(key, req))

    for i, line in enumerate(sig, start=1):
        headers[f'x-ops-authorization-{i}'] = line

    return headers
