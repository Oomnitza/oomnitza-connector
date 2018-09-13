#!/usr/bin/env python
# -*- coding: utf-8 -*-
from lib.strongbox.strategy.vault import VaultStrategy
from lib.strongbox.backend.cyberark import CyberArkKeyring


class CyberArkStrategy(VaultStrategy):
    keyring_backend_class = CyberArkKeyring

    def get_keyring_backend(self):
        server_url, access_token = self.get_options()
        return self.keyring_backend_class(
            server_url, access_token, self.service_name
        )
