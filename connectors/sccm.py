import os
import errno
import logging
import json
import pyodbc
from lib.connector import AuditConnector

logger = logging.getLogger("connectors/sccm")  # pylint:disable=invalid-name


class Connector(AuditConnector):
    MappingName = 'SCCM'
    Settings = {
        'server':            {'order': 1, 'example': 'server.example.com'},
        'database':          {'order': 2, 'default': 'CM_DCT'},
        'username':          {'order': 3, 'example': 'change-me'},
        'password':          {'order': 4, 'example': 'change-me'},
        'authentication':    {'order': 5, 'default': "SQL Server", 'choices': ("SQL Server", "Windows")},
        'sync_field':        {'order': 6, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }
    DefaultConverters = {
        # FORMAT: "{source field}": "{converter to be applied by default}",
    }
    FieldMappings = {
        'APPLICATIONS':      {'source': "software"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.db = self.perform_connect()

    def do_test_connection(self, options):
        try:
            self.perform_connect()
            return {'result': True, 'error': ''}
        except Exception as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def _load_records(self, options):
        """
        Generate audit payload for each unique computer resource.
        """
        for resource in self.get_distinct_computer_resource_ids():
            # logger.info("processing resource %s" % str(resource['ResourceID']))
            yield self.build_audit(resource['ResourceID'])

    def perform_connect(self):
        """
        Connect to the database using Windows or SQL Server authentication
        :return: Connection object
        """
        connect_args = {
            "driver": "{SQL Server}",
            "server": self.settings['server'],
            "database": self.settings['database'],
            "user": self.settings['username'],
            "password": self.settings['password']
        }
        if self.settings['authentication'] == "Windows":
            connect_args['trusted_connection'] = "yes"

        return pyodbc.connect(**connect_args)

    def query(self, sql, *args):
        """
        Performs a database query with connected database.
        :param sql: SQL query
        :return: Array of dictionaries
        """
        try:
            cursor = self.db.cursor()
            results = cursor.execute(sql, args)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in results.fetchall()]
        except Exception as exception:
            logger.error("Unable to perform query: %s" % (exception))
            return []

    def get_distinct_computer_resource_ids(self):
        """
        Determines the unique ResourceIds to query additional tables.
        :return: Array of dictionaries
        """
        return self.query(u"select distinct ResourceID from dbo.v_GS_COMPUTER_SYSTEM;")

    def build_audit(self, resource_id):
        """
        Creates an audit object using several related tables in SCCM.
        :return: Dictionary
        """
        try:
            # lookup resource values
            disk_info = self.get_disk_info(resource_id)
            enclosure_info = self.get_system_enclosure_info(resource_id)
            memory_info = self.get_memory_info(resource_id)
            net_adapter_info = self.get_net_adapter_info(resource_id)
            os_info = self.get_os_info(resource_id)
            processor_info = self.get_processor_info(resource_id)
            system_info = self.get_system_info(resource_id)

            # prepare audit structure
            audit = {
                "hardware": {
                    "cpu": processor_info.get('Name0'),
                    "computer_name": system_info.get('Name0'),
                    "domain_name": system_info.get('Domain0'),
                    "hdd_total_mb": disk_info.get('Size0'),
                    "ipv4_address": net_adapter_info.get('IPAddress0'),
                    "mac_address": net_adapter_info.get('MACAddress0'),
                    "make": system_info.get('Manufacturer0'),
                    "memory_total_kb": memory_info.get("TotalPhysicalMemory0"),
                    "model": system_info.get('Model0'),
                    "os_version": os_info.get('Caption0'),
                    "platform": system_info.get('SystemType0'),
                    "resource_id": resource_id,
                    "serial_number": enclosure_info.get('SerialNumber0'),
                    "user_name": system_info.get('UserName0')
                },
                "software": self.get_installed_software(resource_id) +
                            self.get_installed_software_x64(resource_id)
            }

            if self.settings.get("__save_data__", False):
                try:
                    os.makedirs("./saved_data")
                except OSError as exc:
                    if exc.errno == errno.EEXIST and os.path.isdir("./saved_data"):
                        pass
                    else:
                        raise
                with open("./saved_data/{}.json".format(str(resource_id)), "w") as save_file:
                    save_file.write(json.dumps(audit))

            return audit
        except Exception as e:
            logger.exception("Unhandled exception in build audit")
            return None

    def get_installed_software(self, resource_id):
        """
        Fetches the installed software (x86) that is registered in Add or Remove Programs
        :return: Array of dictionaries
        """
        installed_software = []
        results = self.query(u"""
          select * from dbo.v_GS_ADD_REMOVE_PROGRAMS where ResourceID=?
        """, resource_id)
        for software in results:
            try:
                software_name = software.get('DisplayName0')
                if software_name in [None, ""]:
                    continue
                installed_software.append({
                    "name": software_name,
                    "version": software.get("Version0"),
                    "publisher": software.get("Publisher0"),
                    "path": None
                })
            except Exception as exception:
                logger.info("Exception in get_installed_software: %s" % (exception))
        return installed_software

    def get_installed_software_x64(self, resource_id):
        """
        Get info about 64-bit software installed that is registered in Add or Remove Programs
        https://technet.microsoft.com/en-us/library/dd334659.aspx
        :return: Array of dictionaries
        """
        installed_software_x64 = []
        results = self.query(u"""
            select * from dbo.v_GS_ADD_REMOVE_PROGRAMS_64 where ResourceID=?
        """, resource_id)
        for software in results:
            try:
                software_name = software.get('DisplayName0')
                if software_name in [None, ""]:
                    continue
                installed_software_x64.append({
                    "name": software_name,
                    "version": software.get("Version0"),
                    "publisher": software.get("Publisher0"),
                    "path": None
                })
            except Exception as exception:
                logger.info("Exception in get_installed_software_x64: %s" % (exception))
        return installed_software_x64

    def get_disk_info(self, resource_id):
        """
        Fetches the resource's disk information.
        https://technet.microsoft.com/en-us/library/dd334659.aspx
        :return: Dictionary
        """
        info = self.query(u"""
            select * from dbo.v_GS_DISK where ResourceID=?
        """, resource_id)
        if len(info) > 1:
            return info[0]
        return {}

    def get_memory_info(self, resource_id):
        """
        Fetches the resource's memory information.
        https://technet.microsoft.com/en-us/library/dd334659.aspx
        :return: Dictionary
        """
        info = self.query(u"""
            select * from dbo.v_GS_X86_PC_MEMORY where ResourceID=?
        """, resource_id)
        if len(info) > 1:
            return info[0]
        return {}

    def get_os_info(self, resource_id):
        """
        Fetches the resource's operating system information.
        :return: Dictionary
        """
        info = self.query(u"""
            select * from dbo.v_GS_OPERATING_SYSTEM where ResourceID=?
        """, resource_id)
        if len(info) > 1:
            return info[0]
        return {}

    def get_net_adapter_info(self, resource_id):
        """
        Fetches the resource's network adapter information.
        :return: Dictionary
        """
        info = self.query(u"""
            select * from dbo.v_GS_NETWORK_ADAPTER_CONFIGURATION
            where ResourceID=? and MACAddress0 is not null and IPAddress0 is not null;
        """, resource_id)
        if len(info) > 1:
            return info[0]
        return {}

    def get_processor_info(self, resource_id):
        """
        Fetches the resource's processor information.
        https://technet.microsoft.com/en-us/library/dd334659.aspx
        :return: Dictionary
        """
        info = self.query(u"""
            select * from dbo.v_GS_PROCESSOR where ResourceID=?
        """, resource_id)
        if len(info) > 1:
            return info[0]
        return {}

    def get_system_info(self, resource_id):
        """
        Fetches the resource's system information.
        https://technet.microsoft.com/en-us/library/dd334659.aspx
        :return: Dictionary
        """
        info = self.query(u"""
            select * from dbo.v_GS_COMPUTER_SYSTEM where ResourceID=?
        """, resource_id)
        if len(info) > 1:
            return info[0]
        return {}

    def get_system_enclosure_info(self, resource_id):
        """
        Fetches the resource's system enclosure information.
        https://technet.microsoft.com/en-us/library/dd334659.aspx
        :param resource_id:
        :return: Dictionary
        """
        info = self.query(u"""
            select * from dbo.v_GS_SYSTEM_ENCLOSURE where ResourceID=?
        """, resource_id)
        if len(info) > 1:
            return info[0]
        return {}
