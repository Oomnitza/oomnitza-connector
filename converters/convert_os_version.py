import logging

logger = logging.getLogger("converters/macos_version")
logger.setLevel(logging.ERROR)

MACOS_VERSION = (
    (10, 0, 0, 'Cheetah'),
    (10, 1, 0, 'Puma'),
    (10, 2, 0, 'Jaguar'),
    (10, 3, 0, 'Panther'),
    (10, 4, 0, 'Tiger'),
    (10, 5, 0, 'Leopard'),
    (10, 6, 0, 'Snow Leopard'),
    (10, 7, 0, 'Lion'),
    (10, 8, 0, 'Mountain Lion'),
    (10, 9, 0, 'Mavericks'),
    (10, 10, 0, 'Yosemite'),
    (10, 11, 0, 'El Capitan'),
    (10, 12, 0, 'Sierra'),
    (10, 13, 0, 'High Sierra'),
    (10, 14, 0, 'Mojave'),
    (10, 15, 0, 'Catalina'),
    (11, 0, 0, 'Big Sur'),
    (12, 0, 0, 'Monterey'),
    (13, 0, 1, 'Ventura'),
)


def converter(field, record, value, params):
    """
    Convert macOS version to human-readable string.
    :param os_version: field value
    :return: string with capitalized first letter
    """

    base_os = record.get('Platform','').lower()
    os_version = record.get(field)
    if 'apple' in base_os or 'macos' in base_os or "osx" in base_os:
        try:
            version = os_version.split('.')
            logger.debug("macOS version: %s", version)
            for v in MACOS_VERSION:
                logger.debug("resolved macOS version: %s", v)
                if version[0] == str(v[0]) and version[1] == str(v[1]):
                    return f"{v[3]} ({os_version})"
                elif version[0] == str(v[0]) and int(version[0]) > 10: # Seems the pattern after 10 is major version gets a name
                    return f"{v[3]} ({os_version})"
        except:
            logger.debug("Unable to convert macOS version %s. Setting to empty string.", os_version, exc_info=True)
    elif 'win' in base_os:
        logger.debug("Windows OS detected.")
        return f"Windows ({os_version})"
    return os_version
