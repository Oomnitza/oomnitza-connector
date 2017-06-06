from __future__ import absolute_import

from lib.connector import AuditConnector
from lib.file_connector import CsvConnectorMixin


class Connector(AuditConnector, CsvConnectorMixin):
    MappingName = 'CSV_assets'
    Settings = {
        'filename':   {'order': 1, 'example': "/some/path/to/file/assets.csv", 'default': ''},
        'directory':  {'order': 2, 'example': "/some/path/to/files/", 'default': ''},
        'sync_field': {'order': 3, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    FieldMappings = {
    }
