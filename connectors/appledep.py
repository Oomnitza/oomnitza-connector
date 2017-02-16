import json
import logging

from requests import Request, Session
from requests_oauthlib import OAuth1Session

from lib.connector import AuditConnector

logger = logging.getLogger("connectors/appledep")  # pylint:disable=invalid-name


class DEPException(Exception):
    """Base exception class for DEP integration"""
    pass


class DEPTokenException(DEPException):
    """Exception class for token initialization"""
    pass


class DEPAuthException(DEPException):
    """Exception class for auth problems"""
    pass


class DEPUrlException(DEPException):
    """Exception class for DEP endpoint configuration problems"""
    pass


class DEPInputException(DEPException):
    """Exception class for calling DEP service with improper data"""
    pass


class DEPOutputException(DEPException):
    """Exception class for raising when server responded with strange response structure"""
    pass


class DEPCore(object):
    """
    Based on the https://github.com/bruienne/depy/blob/master/depy.py
    """
    auth_session_token = 'i_am_not_valid_token_and_will_be_updated_on_the_first_api_call'
    dep_api_url = None
    oauth = None

    def __init__(self, server_token, dep_api_url):
        """
        Set proper token and DEP endpoint

        Parameters
        ----------
        server_token
            server token used for communication between DEP and Oomnitza
        dep_api_url
            url of the DEP endpoint
        """
        if not server_token:
            raise DEPTokenException('Token not set during the initialization')
        if not dep_api_url:
            raise DEPUrlException('DEP endpoint not set during the initialization')

        # Verify that the token data is somewhat sane, i.e. has the required
        # keys and their values start with expected prepends.
        try:
            server_token = json.loads(server_token)
            for k, prefix in (('consumer_secret', 'CS_'),
                              ('access_token', 'AT_'),
                              ('consumer_key', 'CK_'),
                              ('access_secret', 'AS_')):
                if not server_token.get(k).startswith(prefix):
                    raise DEPTokenException('Token key %s has improper prefix' % k)

        except ValueError:
            raise DEPTokenException('Token should be encoded as valid JSON')

        except AttributeError:
            raise DEPTokenException('Token has improper structure')

        # Set the required OAuth1 keys from the source token
        self.oauth = OAuth1Session(client_key=server_token['consumer_key'],
                                   client_secret=server_token['consumer_secret'],
                                   resource_owner_key=server_token['access_token'],
                                   resource_owner_secret=server_token['access_secret'],
                                   realm='ADM')

        # Set endpoint
        self.dep_api_url = dep_api_url

    def dep_prep_for_auth(self, endpoint, method):
        """Generate requests.models.PreparedRequest for auth_token obtaining"""

        req = Request(
            method=method,
            url=self.dep_api_url + endpoint
        )

        prep = self.oauth.prepare_request(req)

        prep.headers['X-Server-Protocol-Version'] = '2'
        prep.headers['Content-Type'] = 'application/json;charset=UTF8'

        return prep

    def dep_prep_standard(self, endpoint, method, json_data=None, params_data=None):
        """Generate requests.models.PreparedRequest for standard calls"""

        req = Request(
            method=method,
            url=self.dep_api_url + endpoint,
            json=json_data,
            params=params_data
        )

        prep = req.prepare()

        # Set proper auth token header
        prep.headers['X-ADM-Auth-Session'] = self.auth_session_token

        prep.headers['X-Server-Protocol-Version'] = '2'

        # set any string here for user-agent
        prep.headers['User-Agent'] = 'Oomnitza-connector-1.0'

        if not params_data:
            prep.headers['Content-Type'] = 'application/json;charset=UTF8'

        return prep

    def refresh_auth_token(self):
        """
        Retrieves an auth_session_token using DEP server token data prepared as an OAuth1Session() instance during initialization.
        """
        # Retrieve session auth token
        get_session = self.dep_prep_for_auth('/session', 'get')
        response = self.oauth.send(get_session)

        # Extract the auth session token from the JSON reply
        if response.status_code != 200:
            raise DEPTokenException('Server token is incorrect, MDM server did not accept token')

        self.auth_session_token = response.json()['auth_session_token']

    def send_request(self, endpoint, method, json_data=None, params_data=None):
        """
        Common method to call with

        Parameters
        ----------
        endpoint
            endpoint part, that identify the object of DEP API we want to work with
        method
            HTTP method
        json_data
            json data
        params_data
            params data

        Returns
        -------
            response from DEP
        """

        s = Session()

        prepped = self.dep_prep_standard(endpoint, method, json_data, params_data)
        response = s.send(prepped)

        # Check the status code returned in the response, if it's 401 or 403 our
        # auth session expired or wasn't accepted so we request a new one and retry
        # the same HTTP request again. Otherwise we move on.
        if response.status_code in (401, 403):

            self.refresh_auth_token()
            return self.send_request(endpoint, method, json_data=json_data, params_data=params_data)

        else:

            try:
                return response.json()
            except ValueError:
                return response.content


class AppleDEP(object):
    """
    Main class for the Apple DEP communication. Contains all the useful services

    Usage example:

        token = json.dumps({
          "consumer_key": "CK_48dd68d198350f51258e885ce9a5c37ab7f98543c4a697323d75682a6c10a32501cb247e3db08105db868f73f2c972bdb6ae77112aea803b9219eb52689d42e6",
          "consumer_secret": "CS_34c7b2b531a600d99a0e4edcf4a78ded79b86ef318118c2f5bcfee1b011108c32d5302df801adbe29d446eb78f02b13144e323eb9aad51c79f01e50cb45c3a68",
          "access_token": "AT_927696831c59ba510cfe4ec1a69e5267c19881257d4bca2906a99d0785b785a6f6fdeb09774954fdd5e2d0ad952e3af52c6d8d2f21c924ba0caf4a031c158b89",
          "access_secret": "AS_c31afd7a09691d83548489336e8ff1cb11b82b6bca13f793344496a556b1f4972eaff4dde6deb5ac9cf076fdfa97ec97699c34d515947b9cf9ed31c99dded6ba",
        })
        url = 'http://localhost:8080/'

        apple_dep = AppleDEP(token, url)

        if apple_dep.is_configured_properly():

            for d in apple_dep.get_devices():
                print d

    """
    connector = None

    def __init__(self, server_token, dep_api_url):
        self.connector = DEPCore(server_token, dep_api_url)

    def api_call(self, endpoint, method, json_data=None, params_data=None):
        return self.connector.send_request(endpoint, method, json_data, params_data)

    def is_configured_properly(self):
        """
        Can be used as identifier that everything is OK and credentials set properly.
        Call the account info as identifier that everything is OK
        """
        resp = self.api_call('/account', 'GET')
        if isinstance(resp, dict):
            return True

        return False

    def get_device_info(self, serial_number):
        """
        Returns the info about device by its unique serial number. Returns more info then just a call to the list of devices

        Parameters
        ----------
        serial_number
            serial number of device or list of serial numbers

        Returns
        -------
            list of dicts with device info
        """
        try:
            if isinstance(serial_number, basestring):
                json_data = {'devices': [serial_number.upper()]}
            elif isinstance(serial_number, list):
                json_data = {'devices': [_.upper() for _ in serial_number]}
            else:
                raise AttributeError
        except AttributeError:
            raise DEPInputException('Given number must be string or a list of strings')
        try:
            return self.api_call('/devices', 'POST', json_data=json_data)['devices'].values()
        except KeyError:
            raise DEPOutputException('Server response structure for `get_device_info` call differs from a documented one')

    def get_devices(self, verbose=True):
        """
        Generator that returns the device list

        Parameters
        ----------
        verbose
            special flag, specifies should we call additional request for the devices info
             to return the complete info about device
            NOTE: tests against locally deployed simulator showed that with calling this additional API
             we slowed down this API by ~ 15 %. If the execution time is not super critical for you, it is recommended
             to keep verbose=True

        Returns
        -------
            yielding dicts in a loop one by one
        """
        _limit = 50
        _cursor = None

        try:
            while True:

                resp = self.api_call('/server/devices', 'POST', json_data={'limit': _limit, 'cursor': _cursor})
                if not resp:
                    break

                device_info = resp['devices']
                if not device_info:
                    break

                # if we are in verbose mode, we have to gather all the serial numbers and call another API to retrieve info about this devices
                # and only then return them
                if verbose:
                    full_device_info = self.get_device_info([_['serial_number'] for _ in device_info])
                    for device in full_device_info:
                        if device['response_status'] == 'SUCCESS':
                            yield device
                else:
                    for device in device_info:
                        yield device

                if resp['more_to_follow']:
                    _cursor = resp['cursor']
                else:
                    break

        except KeyError:
            raise DEPOutputException('Server response structure for `get_devices` call differs from a documented one')


class Connector(AuditConnector):
    """
    Connector class for external web Apple DEP API
    """
    MappingName = 'AppleDEP'

    Settings = {
        'url':          {'order': 1, 'default': "https://mdmenrollment.apple.com"},
        'api_token':    {'order': 2, 'example': "YOUR APPLE DEP SERVER TOKEN"},
        'sync_field':   {'order': 3, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    DefaultConverters = {
        "device_assigned_date": "timestamp",
        "profile_assign_time":  "timestamp",
        "profile_push_time":    "timestamp",
    }

    def do_test_connection(self, options):
        try:
            return AppleDEP(self.settings['api_token'], self.settings['url']).is_configured_properly()
        except BaseException as e:
            logger.error(e.message)
            return

    def _load_records(self, options):
        try:
            for device in AppleDEP(self.settings['api_token'], self.settings['url']).get_devices():
                yield device
        except BaseException as e:
            logger.error(e.message)
            return
