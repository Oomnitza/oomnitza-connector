import os
import sqlite3
from contextlib import contextmanager

import arrow

from connectors.managed import Connector as ManagedConnector
from lib import TrueValues
from lib.error import ConfigError


class PersistentStateKeeper:
    """
    The responsibility of this object is to keep the information about the last processed / downloaded file from the cloud
    in some persistent storage
    """

    def __init__(self, data_source_type, data_source_id):
        self.data_source_type = data_source_type
        self.data_source_id = data_source_id
        # create the table to keep the info about the processed media files
        with self.connection_manager() as db_connection:
            cursor = db_connection.cursor()
            cursor.execute(
                "create table if not exists `media_storage_state` "
                "(`data_source_type` text, `data_source_id` text, `creation_date` int, "
                "primary key (`data_source_type`, `data_source_id`))")

    @staticmethod
    def get_db_name():
        return 'state.db'

    @contextmanager
    def connection_manager(self):
        connection = sqlite3.connect(self.get_db_name())
        try:
            yield connection
            connection.commit()
        except:
            connection.rollback()
            raise
        finally:
            connection.close()

    def mark_as_processed(self, creation_date: int):
        with self.connection_manager() as db_connection:
            cursor = db_connection.cursor()
            cursor.execute(f"replace into `media_storage_state` (`data_source_type`,`data_source_id`,`creation_date`) values (?,?,?)",
                           (self.data_source_type, self.data_source_id, creation_date))

    def get_last_processed(self) -> int:
        with self.connection_manager() as db_connection:
            cursor = db_connection.cursor()
            cursor.execute(f"select `creation_date` from `media_storage_state` where `data_source_type` = ? and `data_source_id` = ?",
                           (self.data_source_type, self.data_source_id))
            record = cursor.fetchone()
            if record:
                return record[0]

            return 0


class Connector(ManagedConnector):
    """
    The subset of the managed connectors with the very unique behavior.
    Instead of pulling the data from external data source and pushing it further to Oomnitza
    it downloads the reports from the Oomnitza and store them locally
    """
    current_state_keeper = None

    def __init__(self, section, settings):
        self.folder_path = settings.pop('folder_path', None)
        if not os.path.isdir(self.folder_path):
            try:
                os.mkdir(self.folder_path)
            except FileExistsError:
                raise ConfigError('The specified folder path already occupied by the file with the same name')

        self.overwrite_reports = settings.pop('overwrite_reports', False) in TrueValues
        self.data_sources = settings.pop('data_sources', [])
        super().__init__(section, settings)

        # force the save_data to be false just because of the nature of the connector - it cannot dumps the content of the file to the JSON
        self.settings["__save_data__"] = False

    def convert_record(self, incoming_record):
        """
        Explicitly override the convert_record method to DO NOTHING because the managed reports connector deals with the files that must not be processed / converted
        """
        return incoming_record

    def saas_authorization_loader(self):
        """
        This connector does not deal with the external SaaS, so there is no need to handle the credentials - and we in fact do not have them
        """
        return

    def finalize_processed_portion(self):
        """
        Because the logic of the "sync sessions" creation for the managed reports connector is different we will not explicitly finalize the portion here
        :return:
        """
        return

    def get_field_mappings(self, *args):
        """
        Explicitly override the mapping retrieval method to DO NOTHING because this connector does not have mapping / mapping concept is not applicable here
        """
        return {}

    def writer(self, file_name, content):
        with open(os.path.join(self.folder_path, file_name), 'wb') as report:
            report.write(content)

    def file_fetcher(self, url):
        return self.get(url).content

    def mark_the_file_as_downloaded(self, uid, success=True, error_message=None):
        if success:
            self.OomnitzaConnector.create_synthetic_finalized_successful_portion(self.ConnectorID, uid)
        else:
            self.OomnitzaConnector.create_synthetic_finalized_failed_portion(self.ConnectorID, uid, error_message)

    def send_to_oomnitza(self, data):
        """
        Override this method to just store the file locally in the specified folder instead of preparing the payload and sending it over the network to somewhere
        """
        try:
            if self.overwrite_reports:
                filename = data['filename']
            else:
                filename = f"{arrow.get(data['creation_date']).format('YYYYMMDDHHmmss')}_{data['filename']}"

            binary_content = self.file_fetcher(data['url'])

            self.writer(filename, binary_content)
        except Exception as exc:
            self.mark_the_file_as_downloaded(data['uid'], success=False, error_message=str(exc))
            raise
        else:
            self.mark_the_file_as_downloaded(data['uid'], success=True)
        finally:
            self.current_state_keeper.mark_as_processed(data['creation_date'])

    def _load_records(self, options):
        """
        Download the reports one by one from the cloud
        """
        oomnitza_access_token = self.get_oomnitza_auth_for_sync()
        self.OomnitzaConnector.settings['api_token'] = oomnitza_access_token
        self.OomnitzaConnector.authenticate()

        data_sources = self.data_sources
        if not data_sources:
            # fallback compatibility with the media storage concept to the default sources
            data_sources = [
                {'type': 'reports_connectors', 'id': self.ConnectorID}
            ]

        for data_source in data_sources:
            data_source_type = data_source['type']
            data_source_id = data_source['id']
            self.current_state_keeper = PersistentStateKeeper(data_source_type, data_source_id)
            last_processed = self.current_state_keeper.get_last_processed()

            media_files = self.OomnitzaConnector.get_media_storage_files(
                last_processed,
                data_source_type,
                data_source_id
            )

            for media_file in media_files:
                yield media_file
