import logging

from connector_gui.controllers.config import ConfigController
from connector_gui.models.config import ConfigModel

LOG = logging.getLogger("oomnitza_gui")


def main(args):
    try:
        config_model = ConfigModel(args)
        ConfigController(config_model)
    except:
        LOG.exception("Error running gui!")
