#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import argparse
import getpass
import logging
import sys

from lib import version
from lib.strongbox import save_secret_to_strongbox

LOG = logging.getLogger("strongbox.py")


class SecretPromptAction(argparse.Action):
    """
    Explicitly ask user to provide a secret value without echoing it into
    command line for security reason.
    """

    def __call__(self, parser, args, values, option_string=None):
        secret_value = getpass.getpass(prompt="Your secret: ")
        setattr(args, self.dest, secret_value)


def parse_command_line_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--version", action="store_true", help="Show the vault version."
    )
    parser.add_argument(
        "--connector",
        type=str,
        required=True,
        help="Connector name or vault alias under which secret is saved in vault.",
    )
    parser.add_argument(
        "--key", type=str, default="api_token", required=True, help="Secret key name."
    )
    parser.add_argument(
        "--value",
        type=str,
        action=SecretPromptAction,
        required=True,
        help="Secret value.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_command_line_args()

    LOG.info("Strongbox version: %s", version.VERSION)
    if args.version:
        sys.exit(0)

    save_secret_to_strongbox(args)
