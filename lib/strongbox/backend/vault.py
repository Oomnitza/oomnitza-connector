#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import hvac
from keyring.backend import KeyringBackend
from keyring.errors import PasswordSetError, PasswordDeleteError


LOG = logging.getLogger(__name__)


class VaultKeyring(KeyringBackend):
    """
    Vault-based implementation of keyring.

    It uses the python HashiCorp Vault API to manage the secrets
    directly in the local or remote server.
    """

    priority = 9

    def __init__(self, vault_url, vault_token):
        super(VaultKeyring, self).__init__()

        self.client = hvac.Client(
            url=vault_url, token=vault_token
        )

    def get_password(self, service, key):
        """
        Get secret of the key for the service
        """
        try:
            ret = self.client.read('secret/{}'.format(service))
            return ret['data'][key]
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
            "Write secret to vault backend is disabled"
        )

    def delete_password(self, service, key):
        """
        Delete the secret for the key of the service.
        """
        raise PasswordDeleteError(
            "Delete secret from vault backend is disabled"
        )
