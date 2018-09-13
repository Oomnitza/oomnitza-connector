#!/usr/bin/env python
# -*- coding: utf-8 -*-
from lib.error import ConfigError
from lib.strongbox.strategy.base import BaseStrategy
from lib.strongbox.backend.vault import VaultKeyring


class VaultStrategy(BaseStrategy):
    keyring_backend_class = VaultKeyring

    def get_keyring_backend(self):
        server_url, access_token = self.get_options()
        return self.keyring_backend_class(server_url, access_token)

    def get_options(self):
        server_url = self.get_secret(self.service_name, 'vault_url')
        access_token = self.get_secret(self.service_name, 'vault_token')
        return [server_url, access_token]

    def get_secret(self, service_name, secret_name):
        secret_value = self.default_keyring.get_password(
            service_name, secret_name
        )
        if secret_value is None:
            self._raise_error(service_name, secret_name)
        return secret_value

    def _raise_error(self, service_name, secret_name):
        raise ConfigError(
            "Unable to find secret in keyring, ensure secret "
            "key/value pair has been inserted before starting "
            "connector:\n\t"
            "python strongbox.py --connector={} --key={} --value=".format(
                service_name, secret_name
            )
        )
