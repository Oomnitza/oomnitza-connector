#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import keyring
from keyring.errors import PasswordSetError

from lib.error import ConfigError
from lib.strongbox.strategy import (
    DefaultStrategy, VaultStrategy, CyberArkStrategy
)


logging.basicConfig()
LOG = logging.getLogger("lib/strongbox")


class StrongboxBackend:
    VAULT = 'vault'
    KEYRING = 'keyring'
    CYBERARK = 'cyberark'


class Strongbox(object):
    """
    Base class for secret storage used to manage service secrets.
    """

    def __init__(self, service_name, backend_name):
        self._service_name = service_name

        keyring_backend = keyring.get_keyring()

        if backend_name == StrongboxBackend.KEYRING:
            Strategy = DefaultStrategy
        elif backend_name == StrongboxBackend.VAULT:
            Strategy = VaultStrategy
        elif backend_name == StrongboxBackend.CYBERARK:
            Strategy = CyberArkStrategy
        else:
            raise ConfigError(
                "Invalid strongbox backend: '{}', e.g. only 'keyring' "
                "'vault' and 'cyberark' values are allowed".format(backend_name)
            )

        LOG.info(
            "The {backend_name} backend is used as the secret storage "
            "for {service_name}".format(
                backend_name=backend_name, service_name=service_name
            )
        )
        strategy = Strategy(keyring_backend, service_name)
        self._keyring_backend = strategy.get_keyring_backend()

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
    return (connector_name, secret_key, secret_value)


def save_secret_to_strongbox(args):
    service_name, secret_key, secret_value = _get_strongbox_attrs(args)

    strongbox = Strongbox(service_name, backend_name=StrongboxBackend.KEYRING)
    strongbox.set_secret(secret_key, secret_value)
