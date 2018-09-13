#!/usr/bin/env python
# -*- coding: utf-8 -*-
from lib.strongbox.strategy.base import BaseStrategy


class DefaultStrategy(BaseStrategy):

    def get_keyring_backend(self):
        return self.default_keyring
