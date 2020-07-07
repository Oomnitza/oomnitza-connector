#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import logging
import requests
from requests.exceptions import HTTPError


logger = logging.getLogger(__name__)


class CyberArkClient(object):
    """
    Implements client to access CyberArk API.
    """

    def __init__(self, server_url, api_token, account):
        """
        :param server_url: The cyberark conjur server url
        :type server_url: string
        :param api_token: The api token used to authorize API requests
        :type api_token: string
        :param account: The cyberark account name
        :type account: string
        """
        self.session = requests.Session()
        self.account = account
        self.api_token = api_token
        self.server_url = server_url
        self._token = None

    def read(self, path):
        """
        :param path: The path to read
        :type path: string
        :return:
        :rtype: response
        """
        try:
            return self._get(path)
        except Exception as exc:
            logger.error(exc);
            return None

    def authenticate(self):
        """
        Acquire short-lived access token for current session.
        """
        try:
            self._token = self._lookup_token()
        except:
            raise HTTPError(
                "Unable to get short-lived access token for cyberark storage"
            )

    def is_authenticated(self):
        """
        Helper method which returns the authentication status of the client.

        :return: Authentication status of the client
        :rtype: bool
        """
        if self._token is None:
            self.authenticate()

        return self._token is not None

    def _lookup_token(self):
        """
        Gets a short-lived access token, which can be used to authenticate
        requests to the rest of the Conjur API.

        :return: Access token
        :rtype: string
        """
        path = '/authn/{account}/{login}/authenticate'.format(
            account=self.account, login='admin'
        )
        res = self._post(path, data=self.api_token, skip_auth=True)
        return base64.b64encode(res.text)

    def _get_auth_header(self):
        """
        :return: Authentication header string used to access CyberArk API
        :rtype: string
        """
        return 'Token token="{token}"'.format(token=self._token)

    def _get(self, url, **kwargs):
        """
        :param url: The API endpoint url
        :type url: string
        :param kwargs: Additional request arguments
        :type kwargs: dict
        :return:
        :rtype: response
        """
        return self.__request('get', url, **kwargs)

    def _post(self, url, **kwargs):
        """
        :param url: The API endpoint url
        :type url: string
        :param kwargs: Additional request arguments
        :type kwargs: dict
        :return:
        :rtype: response
        """
        return self.__request('post', url, **kwargs)

    def __request(self, method, url, headers=None, skip_auth=False, **kwargs):
        """
        :param method: The request method, e.g. GET, POST, etc
        :type method: string
        :param url: The request URL
        :type url: string
        :param headers: The request headers
        :type headers: dict
        :param skip_auth: Flag to skip auth headers
        :type skip_auth: bool
        :param kwargs: Additional request arguments
        :type kwargs: dict
        :return:
        :rtype: response
        """
        url = '/'.join([str(x).strip('/') for x in (self.server_url, url)])

        if not headers:
            headers = {}

        if not skip_auth and self.is_authenticated():
            headers['Authorization'] = self._get_auth_header()

        response = self.session.request(
            method, url, headers=headers, allow_redirects=False, **kwargs
        )
        response.raise_for_status()

        return response
