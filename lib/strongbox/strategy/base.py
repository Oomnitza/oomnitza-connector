#!/usr/bin/env python
# -*- coding: utf-8 -*-
class BaseStrategy(object):

    def __init__(self, default_keyring, service_name):
        self.default_keyring = default_keyring
        self.service_name = service_name

    def get_keyring_backend(self):
        raise NotImplementedError()
