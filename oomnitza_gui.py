import os
import sys
import subprocess

from connector_gui.models.config import ConfigModel
from connector_gui.controllers.config import ConfigController


def main(args=None):

    config_model = ConfigModel()
    ConfigController(config_model)

if __name__ == '__main__':
    main()