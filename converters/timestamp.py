import logging

import arrow

logger = logging.getLogger("converters/timestamp")  # pylint:disable=invalid-name


def converter(field, record, value, params):
    """
    Converts a string to the UNIX timestamp
    """
    if value is not None:
        try:
            return arrow.get(value).timestamp
        except:
            logger.error("String conversion to UNIX timestamp failed. String value '%s'" % value)

    return value
