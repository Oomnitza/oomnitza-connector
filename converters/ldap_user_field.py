
import logging
logger = logging.getLogger(__file__)


def converter(field, record, value):
    """
    Attempts to load the value from the defined field. Falls back to sAMAccountName if no value.

    :param value: field value
    :return: value from defined source, value from sAMAccountName, or None.
    """
    logger.debug("converter(%r, %r, %r)", field, record, value)
    if value:
        return value

    return record.get('sAMAccountName', [None])[0]
