import json
import logging
import re

import chef

from lib import TrueValues
from lib.connector import AssetsConnector
from utils.data import get_field_value

logger = logging.getLogger("connectors/chef")  # pylint:disable=invalid-name


class AuditFactory(object):
    """Factory class responsible for creating audits based on the node platform."""
    @staticmethod
    def create(node):
        platform = get_field_value(node, 'automatic.platform')
        if platform == 'mac_os_x':
            return MacAudit.create(node)
        if platform == 'windows':
            return WindowsAudit.create(node)
        return BaseAudit.create(node)


class BaseAudit(object):
    """Contains base audit structure and attribute lookups. Platforms with known attribute variances
    such as Mac OS X and Windows will extend this class and override the necessary class methods.
    """
    AttributeExtension = {}

    @classmethod
    def set_extensions(cls, extension):
        try:
            if extension:
                cls.AttributeExtension = json.loads(extension)
        except:
            logger.exception('error: failed to load attribute extensions')

    @classmethod
    def create(cls, node):
        hardware = {
            'name': cls.name(node),
            'ip_address': cls.ip_address(node),
            'mac_address': cls.mac_address(node),
            'hostname': cls.hostname(node),
            'fqdn': cls.fqdn(node),
            'domain': cls.domain(node),
            'platform': cls.platform(node),
            'platform_version': cls.platform_version(node),
            'serial_number': cls.serial_number(node),
            'model': cls.model(node),
            'total_memory_mb': cls.total_memory_mb(node),
            'total_hdd_mb': cls.total_hdd_mb(node),
            'cpu': cls.cpu(node),
            'cpu_count': cls.cpu_count(node),
            'uptime_seconds': cls.uptime_seconds(node),
        }

        # process configured attribute extensions
        try:
            for platform in cls.AttributeExtension:
                platforms_list = cls.get_platforms_list(node)
                if platform in platforms_list:
                    extensions = cls.AttributeExtension[platform]
                    for extension in extensions:
                        hardware[extension] = get_field_value(node, cls.AttributeExtension[platform][extension])
        except:
            logger.exception('error: exception processing attribute extensions - %r' % cls.AttributeExtension)

        return {'hardware': hardware}

    @classmethod
    def get_platforms_list(cls, node):
        platforms = ['__default__']
        if cls.platform(node):
            platforms.append(node['automatic']['platform'])
        else:
            logger.warning("Unknown 'platform' for node named - %r" % cls.name(node))
        return platforms

    @classmethod
    def name(cls, node):
        return get_field_value(node, 'name')

    @classmethod
    def fqdn(cls, node):
        return get_field_value(node, 'automatic.fqdn')

    @classmethod
    def domain(cls, node):
        return get_field_value(node, 'automatic.domain')

    @classmethod
    def platform(cls, node):
        return get_field_value(node, 'automatic.platform')

    @classmethod
    def platform_version(cls, node):
        return get_field_value(node, 'automatic.platform_version')

    @classmethod
    def hostname(cls, node):
        return get_field_value(node, 'automatic.hostname')

    @classmethod
    def ip_address(cls, node):
        return get_field_value(node, 'automatic.ipaddress')

    @classmethod
    def mac_address(cls, node):
        return get_field_value(node, 'automatic.macaddress')

    @classmethod
    def uptime_seconds(cls, node):
        return get_field_value(node, 'automatic.uptime_seconds')

    @classmethod
    def total_hdd_mb(cls, node):
        total_kb = get_field_value(node, 'automatic.filesystem.by_mountpoint./.kb_size')
        return AuditUtil.kb_to_mb(total_kb)

    @classmethod
    def total_memory_mb(cls, node):
        total_kb = get_field_value(node, 'automatic.memory.total')
        return AuditUtil.kb_to_mb(total_kb)

    @classmethod
    def cpu(cls, node):
        return get_field_value(node, 'automatic.cpu.0.model_name')

    @classmethod
    def cpu_count(cls, node):
        return get_field_value(node, 'automatic.cpu.total')

    @classmethod
    def model(cls, node):
        # TODO is there a smart default we can use?
        logger.warning('no default `model` lookup for node named - %r' % cls.name(node))
        return None

    @classmethod
    def serial_number(cls, node):
        # TODO is there a smart default we can use?
        logger.warning('no default `serial_number` lookup for node named - %r' % cls.name(node))
        return None


class MacAudit(BaseAudit):
    """Contains attribute overrides for 'mac_os_x' platform."""
    @classmethod
    def serial_number(cls, node):
        return get_field_value(node, 'automatic.hardware.serial_number')

    @classmethod
    def model(cls, node):
        return get_field_value(node, 'automatic.hardware.machine_model')

    @classmethod
    def cpu(cls, node):
        return get_field_value(node, 'automatic.cpu.model_name')

    @classmethod
    def cpu_count(cls, node):
        return get_field_value(node, 'automatic.hardware.number_processors')

    @classmethod
    def total_memory_mb(cls, node):
        total_mb = get_field_value(node, 'automatic.memory.total')
        return AuditUtil.regex_match_digits(total_mb)


class WindowsAudit(BaseAudit):
    """Contains attribute overrides for 'windows' platform."""
    @classmethod
    def model(cls, node):
        return get_field_value(node, 'automatic.kernel.cs_info.model')

    @classmethod
    def serial_number(cls, node):
        return get_field_value(node, 'automatic.kernel.os_info.serial_number')

    @classmethod
    def cpu_count(cls, node):
        return get_field_value(node, 'automatic.kernel.cs_info.number_of_processors')

    @classmethod
    def total_hdd_mb(cls, node):
        drives = get_field_value(node, 'automatic.filesystem')
        if drives and isinstance(drives, dict):
            root_drive = list(drives.values())[0]
            drive_kb = root_drive.get('kb_size')
            return AuditUtil.kb_to_mb(drive_kb)
        return None


class AuditUtil(object):
    """Contains helper methods for normalization of node audit data."""

    @staticmethod
    def regex_match_digits(v):
        """Extract the digits from an alphanumeric string.

        Parameters
        ----------
            v : basestring
                alphanumeric input e.g. '1024kB'

        Returns
        -------
            int
                the extracted numeric digits, or None

        """
        try:
            return int(re.match('[0-9]+', str(v)).group())
        except:
            return None

    @staticmethod
    def bytes_to_mb(b):
        """Converts bytes to megabytes.

        Parameters
        ----------
            b : basestring
                input bytes value e.g. '1024'

        Returns
        -------
            int
                converted value in megabytes

        """
        b = AuditUtil.regex_match_digits(b)
        if b:
            return b / 1024 / 1024
        return None

    @staticmethod
    def kb_to_mb(k):
        """Converts kilobytes to megabytes.

        Parameters
        ----------
            k : basestring
                input kilobytes value e.g. '1024' or '2048kB'

        Returns
        -------
            int
                converted value in megabytes

        """
        k = AuditUtil.regex_match_digits(k)
        if k:
            return k / 1024
        return None


class Connector(AssetsConnector):
    MappingName = 'Chef'
    Settings = {
        'url':                 {'order': 1, 'example': 'https://example.com/organizations/org'},
        'client':              {'order': 2, 'example': 'user'},
        'key_file':            {'order': 3, 'example': '/path/to/user.pem'},
        'attribute_extension': {'order': 5, 'default': ''},
    }
    DefaultConverters = {
        # "{source field}": "{converter to be applied by default}",
    }
    FieldMappings = {
        # "{source field}": {"source": "attribute.value"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.api = None

        # enable attribute extensions
        BaseAudit.set_extensions(self.settings['attribute_extension'])

    def authenticate(self):
        """
        Connect to the chef server and verify communication.
        """
        if self.api:
            return

        server = self.settings['url']
        key_file = self.settings['key_file']
        client = self.settings['client']
        verify_ssl = self.settings.get('verify_ssl', True) in TrueValues

        self.api = chef.ChefAPI(server, key_file, client, ssl_verify=verify_ssl)
        chef.Role.list(api=self.api)  # will raise error if authentication failure

    def query(self, *args):
        """
        Queries Chef API for all Nodes

        :return: Array of dictionaries, empty if error with api
        """
        try:
            return [self.build_audit(node) for node in self.chef_nodes()]
        except Exception:
            self.logger.exception("error: unable to perform query")
            return []

    def _load_records(self, options):
        """
        Generate audit payload for each unique computer resource.
        """
        for resource in self.query():
            yield resource

    def build_audit(self, node):
        """
        Creates an audit dictionary from a provided chef node dictionary.
        """
        try:
            audit = AuditFactory.create(node)

            return audit
        except Exception:
            self.logger.exception("Unhandled exception in build audit")
            return None

    def chef_nodes(self):
        """Generator method that queries the chef server and yields node dictionaries."""
        q = 'name:*'
        size = 1000
        start = 0
        while start is not None:
            response = chef.Search('node', q, rows=size, start=start, api=self.api)
            count = 0
            for node in response:
                count += 1
                yield node
            if count == 0 or count < size:
                start = None
            else:
                start += size
