import glob
import hashlib
import inspect
import logging
import os
import sqlite3

from unicodecsv import DictReader as UnicodeDictReader

from lib.connector import BaseConnector


LOGGER = logging.getLogger("connectors/file")


def md5(file_name):
    """
    Memory efficient MD5 hash calculation for files
     
    :type file_name: basestring
    :param file_name: name of file
    :return: 
    """
    hash_md5 = hashlib.md5()
    with open(file_name, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def persistence_decorator(db_name):
    """
    Decorator around generator that has to yield records from the file 
    and mark then this file in the local sqlite DB as processed to skip it later
    
    :param db_name: db name used to keep signatures of processed files
    :return: 
    """

    def decorator(func):

        if not inspect.isgeneratorfunction(func):
            raise AssertionError("This decorator should be used only for the generators")

        def wrapper(*args, **kwargs):

            connector_object, file_name = args[:2]
            connection = None

            try:

                if connector_object.settings.get("__testmode__", False):
                    # do not use DB in the test mode
                    for _ in func(*args, **kwargs):
                        yield _

                else:

                    md5_signature = md5(file_name)

                    connection = sqlite3.connect(db_name)
                    cursor = connection.cursor()

                    # check if the table exists
                    cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='main';""")
                    if not cursor.fetchone():
                        # create table
                        cursor.execute("""CREATE TABLE main (md5_char CHAR(32))""")
                        connection.commit()
                        cursor.execute("""CREATE INDEX md5_index ON main (md5_char);""")
                        connection.commit()

                    cursor.execute("""SELECT EXISTS(SELECT 1 FROM main WHERE md5_char="%s" LIMIT 1);""" % md5_signature)
                    if cursor.fetchone()[0]:
                        LOGGER.info("Skipping input file because already processed: %s", file_name)
                        return

                    for _ in func(*args, **kwargs):
                        yield _

                    cursor.execute("""INSERT INTO main VALUES ("%s")""" % md5_signature)
                    connection.commit()

            except:
                raise

            finally:
                if connection:
                    connection.close()

        return wrapper

    return decorator


class FileConnectorMixin(BaseConnector):
    """
    Base mixin class designed to read files
    """

    source = None
    source_type = None
    file_mask = "*"

    class FileTestException(Exception):
        pass

    def __init__(self, section, settings):

        super(FileConnectorMixin, self).__init__(section, settings)

        filename = self.settings.get('filename')
        directory = self.settings.get('directory')

        if filename and directory:
            raise Exception("File and directory are mutually exclusive")

        if not(filename or directory):
            raise Exception("Data source is not set")

        self.source = os.path.abspath(directory or filename)
        if filename:
            self.source_type = 'file'
        else:
            self.source_type = 'directory'

    def test_income_data(self):
        if self.source_type == 'file':
            if not os.path.isfile(self.source):
                raise self.FileTestException('%r is not a file.' % self.source)
        else:
            if not os.path.isdir(self.source):
                raise self.FileTestException('%r is not a directory.' % self.source)

    def do_test_connection(self, options):

        try:
            self.test_income_data()
        except self.FileTestException as err:
            return {'result': False, 'error': str(err)}

        return {'result': True, 'error': ''}

    def _load_records(self, options):

        self.test_income_data()

        if self.source_type == 'file':
            for row in self._load_file(self.source):
                yield row

        for filename in glob.glob(os.path.join(self.source, self.file_mask)):
            for row in self._load_file(filename):
                yield row

    def _load_file(self, filename):
        raise NotImplementedError


class CsvConnectorMixin(FileConnectorMixin):
    """
    CSV parser mixin class.
    """
    file_mask = "*.csv"

    @persistence_decorator('csv_persistence.sqlite')
    def _load_file(self, filename):
        with open(filename, 'rb') as input_file:
            LOGGER.info("Processing input file: %s", filename)
            reader = UnicodeDictReader(input_file)
            for row in reader:
                yield row
