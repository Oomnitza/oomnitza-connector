# mode which just used to show the connectors version and exit
MODE_VERSION = 'version'

# mode which generates an example config.ini file.
MODE_GENERATE_INI_TEMPLATE = 'generate-ini'

# mode which pulls data from remote system and push to Oomnitza.
MODE_CLIENT_INITIATED_UPLOAD = 'upload'

# mode which set the connector in the "managed" mode where the connector is managed by the cloud. The default mode starting from 2.2.0
MODE_CLOUD_INITIATED_UPLOAD = 'managed'

FATAL_ERROR_FLAG = 'Fatal Error'

# Boolean Constants.
TRUE_VALUES = ['TRUE', 'True', 'true', True, '1', 1, 'YES', 'Yes', 'yes', 'Y', 'y']
FALSE_VALUES = ['FALSE', 'False', 'false', False, '0', 0, 'NO', 'No', 'no', 'N', 'n']

ENABLED_CONNECTORS = {
    'oomnitza': {
        'label': 'oomnitza',
        'order': 1
    },
    'managed': {
        'label': 'managed.xxx',
        'order': 2
    },
    'chef': {
        'label': 'chef',
        'order': 3
    },
    'csv_assets': {
        'label': 'csv_assets',
        'order': 4
    },
    'csv_users': {
        'label': 'csv_users',
        'order': 5
    },
    'jasper': {
        'label': 'jasper',
        'order': 6
    },
    'ldap': {
        'label': 'ldap',
        'order': 7
    },
    'ldap_assets': {
        'label': 'ldap_assets',
        'order': 8
    },
    'mobileiron': {
        'label': 'mobileiron',
        'order': 9
    },
    'netbox': {
        'label': 'netbox',
        'order': 10
    },
    'open_audit': {
        'label': 'open_audit',
        'order': 11
    },
    'sccm': {
        'label': 'sccm',
        'order': 12
    },
    'tanium': {
        'label': 'tanium',
        'order': 13
    },
    'vcenter': {
        'label': 'vcenter',
        'order': 14
    },
    'workspaceone_devicesoftware': {
        'label': 'workspaceone_devicesoftware',
        'order': 15
    },
    'munki_report': {
        'label': 'munki_report',
        'order': 16
    },
    'insight': {
        'label': 'insight',
        'order': 17
    },
    'dell_asset_order_status': {
        'label': 'dell_asset_order_status',
        'order': 18
    },
    'dnac_network_devices': {
        'label': 'dnac_network_devices',
        'order': 19
    }
}


class MTLSType:
    PFX = 'pfx'
    CERT_KEY = 'cert_key'


class ConfigFieldType:
    STR = 'str'
    MULTI_STR = 'multi_str'
