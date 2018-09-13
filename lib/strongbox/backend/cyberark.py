#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from keyring.backend import KeyringBackend
from keyring.errors import PasswordSetError, PasswordDeleteError

from lib.cyberark_client import CyberArkClient


LOG = logging.getLogger(__name__)


class CyberArkKeyring(KeyringBackend):
    """
    CyberArk keyring backend.

    Implements secrets management via local or remote CyberArk Conjur server.
    """

    priority = 9

    def __init__(self, server_url, access_token, account):
        super(CyberArkKeyring, self).__init__()
        self.client = CyberArkClient(server_url, access_token, account)

    def get_password(self, service, key):
        """
        Get secret of the key for the service.
        """
        try:
            ret = self.client.read('secrets/{service}/variable/{key}'.format(
                service=service, key=key
            ))
            return ret.text
        except:
            LOG.error(
                "Unable to get secret key for the service: "
                "service={} key={}".format(service, key)
            )
            return None

    def set_password(self, service, key, value):
        """
        Set secret for the key of the service
        """
        raise PasswordSetError(
            "Write secret to cyberark backend is disabled"
        )

    def delete_password(self, service, key):
        """
        Delete the secret for the key of the service.
        """
        raise PasswordDeleteError(
            "Delete secret from cyberark backend is disabled"
        )
