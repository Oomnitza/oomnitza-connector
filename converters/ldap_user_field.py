
import logging
logger = logging.getLogger("converters/ldap_user_field")


def converter(field, record, value, params):
    """
    Attempts to load the value from the defined field. Falls back to sAMAccountName if no value.

    :param value: field value
    :return: value from defined source, value from sAMAccountName, or None.
    """
    if value:
        return value

    return record.get('sAMAccountName', None)
