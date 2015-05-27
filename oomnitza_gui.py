import os

from lib.config import generate_ini_file
from connector_gui.models.config import ConfigModel
from connector_gui.controllers.config import ConfigController
from utils.utilize_connector import utilize_connector
from utils.relative_path import relative_app_path


def main(args=None):
    if not os.path.exists(relative_app_path('config.ini')):
        utilize_connector(target=generate_ini_file)
    config_model = ConfigModel()
    ConfigController(config_model)

if __name__ == '__main__':
    main()