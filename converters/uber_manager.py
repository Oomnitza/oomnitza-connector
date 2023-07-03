
import re
import logging
logger = logging.getLogger("converters/uber_manager")


ExtractRE = re.compile("uid=([^,]+).*")


def converter(field, record, value, params):
    """
    Uber's `manager` field in LDAP is an OU. This will extract the username.

    :param value: OU value
    :return: username from OU or None
    """
    if not value:
        return None

    matches = ExtractRE.match(value)
    if not matches:
        logger.error("Unable to extract username from manager OU: '{}'.", value)
        return value

    return matches.groups()[0]
