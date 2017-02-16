import logging

import arrow

logger = logging.getLogger("converters/ldap_timestamp")


def converter(field, record, value, params):
    """
    Attempts to load the value from the defined field. Falls back to sAMAccountName if no value.

    :param value: field value
    :return: value from defined source, value from sAMAccountName, or None.
    """
    try:
        value = int(value)
        try:
            # http://meinit.nl/convert-active-directory-lastlogon-time-to-unix-readable-time
            return arrow.get(1601, 1, 1).replace(seconds=value / 10 ** 7).timestamp
        except OverflowError:
            return arrow.get().max.timestamp

    except:
        return value
