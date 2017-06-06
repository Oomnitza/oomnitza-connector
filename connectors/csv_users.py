from __future__ import absolute_import

from lib.connector import UserConnector
from lib.file_connector import CsvConnectorMixin


class Connector(UserConnector, CsvConnectorMixin):
    MappingName = 'CSV_users'
    Settings = {
        'filename':   {'order': 1, 'example': "/some/path/to/file/users.csv", 'default': ''},
        'directory':  {'order': 2, 'example': "/some/path/to/files/", 'default': ''},
        'default_role': {'order': 3, 'example': 25, 'type': int},
        'default_position': {'order': 4, 'example': 'Employee'},
    }

    FieldMappings = {
    }
