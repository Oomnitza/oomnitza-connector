# mode which just used to show the connectors version and exit
MODE_VERSION = 'version'

# mode which generates an example config.ini file.
MODE_GENERATE_INI_TEMPLATE = 'generate-ini'

# mode which pulls data from remote system and push to Oomnitza.
MODE_CLIENT_INITIATED_UPLOAD = 'upload'

# mode which set the connector in the "managed" mode where the connector is managed by the cloud. The default mode starting from 2.2.0
MODE_CLOUD_INITIATED_UPLOAD = 'managed'

FATAL_ERROR_FLAG = 'Fatal Error'


class MTLSType:
    PFX = 'pfx'
    CERT_KEY = 'cert_key'


class ConfigFieldType:
    STR = 'str'
    MULTI_STR = 'multi_str'
