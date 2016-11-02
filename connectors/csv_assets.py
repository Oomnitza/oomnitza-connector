from __future__ import absolute_import

import os
import logging
import json
import glob

from lib.connector import AuditConnector
from lib.csv import UnicodeDictReader

LOGGER = logging.getLogger("connectors/csv_assets")  # pylint:disable=invalid-name


class Connector(AuditConnector):
    MappingName = 'JSON-assets'
    Settings = {
        'filename':   {'order': 1, 'example': "/Users/daniel/Documents/development/Oomnitza/Connector/test_data/assets.csv"},
        'directory':  {'order': 2, 'example': "/Users/daniel/Documents/development/Oomnitza/Connector/test_data/assets/"},
        'sync_field': {'order': 3, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }

    FieldMappings = {
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)

        filename = self.settings.get('filename')
        directory = self.settings.get('directory')
        if filename and directory:
            raise Exception("filename and directory are mutually exclusive.")
        if filename:
            self.source = os.path.abspath(filename)
            self.source_type = 'file'
        else:
            self.source = os.path.abspath(directory)
            self.source_type = 'directory'

    def do_test_connection(self, options):
        if self.source_type == 'file':
            if os.path.isfile(self.source):
                return {'result': True, 'error': ''}
            else:
                return {'result': False, 'error': '%r is not a file.' % self.source}
        else:
            if not os.path.isdir(self.source):
                return {'result': False, 'error': '%r is not a directory.' % self.source}
            fields = None
            errors = []
            for filename in glob.glob(os.path.join(self.source, '*.csv')):
                with open(filename, 'rb') as test_file:
                    reader = UnicodeDictReader(test_file)
                    if not fields:
                        fields = set(reader.fieldnames)
                    else:
                        if set(reader.fieldnames) != fields:
                            errors.append("Different file headers found in %s." % filename)
            if errors:
                return {'result': False, 'errors': errors}
            return {'result': True, 'error': ''}

    def _load_records(self, options):
        if self.source_type == 'file':
            yield self._load_file(options, self.source)

        for filename in glob.glob(os.path.join(self.source, '*.csv')):
            yield self._load_file(options, filename)

    def _load_file(self, options, filename):
        with open(filename, 'rb') as input_file:
            LOGGER.info("Processing input file: %s", filename)
            reader = UnicodeDictReader(input_file)
            for row in reader:
                yield row


