#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import keyring
import hvac
from keyring.backend import KeyringBackend
from keyring.errors import PasswordSetError, PasswordDeleteError

from .error import ConfigError


logging.basicConfig()
LOG = logging.getLogger("lib/strongbox")


class StrongboxBackend:
    VAULT = 'vault'
    KEYRING = 'keyring'


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
            LOG.info(
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


class Strongbox(object):
    """
    Base class for secret storage used to manage service secrets.
    """

    def __init__(self, service_name, backend_name):
        self._service_name = service_name

        keyring_backend = keyring.get_keyring()

        if backend_name == StrongboxBackend.KEYRING:
            LOG.info(
                "The keyring backend is used as the secret storage "
                "for {}".format(service_name)
            )
        elif backend_name == StrongboxBackend.VAULT:
            LOG.info(
                "The vault backend is selected to access the "
                "secret storage for {}".format(service_name)
            )

            LOG.info(
                "Get the vault URL from system keyring "
                "for {}".format(service_name)
            )
            vault_url = keyring_backend.get_password(
                service_name, 'vault_url'
            )
            if vault_url is None:
                self._raise_config_error(key='vault_url')

            LOG.info(
                "Get the vault token from system keyring "
                "for {}".format(service_name)
            )
            vault_token = keyring_backend.get_password(
                service_name, 'vault_token'
            )
            if vault_token is None:
                self._raise_config_error(key='vault_token')

            keyring_backend = VaultKeyring(
                vault_url=vault_url, vault_token=vault_token
            )
            LOG.info(
                "The vault backend is used to access the secret storage "
                "for {}".format(service_name)
            )
        else:
            raise ConfigError(
                "Invalid strongbox backend: '{}', e.g. only 'keyring' "
                "and 'vault' values are allowed".format(backend_name)
            )

        self._keyring_backend = keyring_backend

    def _raise_config_error(self, key):
        raise ConfigError(
            "Unable to find secret in keyring, ensure secret "
            "key/value pair has been inserted before starting "
            "connector:\n\t"
            "python strongbox.py --connector={} --key={} --value=".format(
                self._service_name, key
            )
        )

    def set_secret(self, key, value):
        """
        Set secret key/value pairs into a secret storage.
        """
        try:
            self._keyring_backend.set_password(self._service_name, key, value)
        except PasswordSetError:
            LOG.exception("Unable to save secret on strongbox")
            return

        LOG.info(
            "Secret key '{}' for service '{}' has been saved".format(
                key, self._service_name))

    def get_secret(self, key):
        """
        Retrieve secret value for a key from secret storage.
        """
        return self._keyring_backend.get_password(self._service_name, key)


def _get_strongbox_attrs(args):
    connector_name= args.connector
    secret_key = args.key
    secret_value = args.value
    return connector_name, secret_key, secret_value


def save_secret_to_strongbox(args):
    service_name, secret_key, secret_value = _get_strongbox_attrs(args)

    strongbox = Strongbox(service_name, backend_name=StrongboxBackend.KEYRING)
    strongbox.set_secret(secret_key, secret_value)
