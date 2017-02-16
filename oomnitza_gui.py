import os
import logging

from lib.config import generate_ini_file
from connector_gui.models.config import ConfigModel
from connector_gui.controllers.config import ConfigController
from utils.utilize_connector import utilize_connector
from utils.relative_path import relative_app_path

LOG = logging.getLogger("oomnitza_gui")

def main(args):
    try:
        config_model = ConfigModel(args)
        ConfigController(config_model)
    except:
        LOG.exception("Error running gui!")

