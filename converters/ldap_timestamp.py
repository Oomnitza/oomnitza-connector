from datetime import datetime, timedelta
import time

import logging
logger = logging.getLogger("converters/ldap_timestamp")


# http://meinit.nl/convert-active-directory-lastlogon-time-to-unix-readable-time
def converter(field, record, value, params):
    """
    Attempts to load the value from the defined field. Falls back to sAMAccountName if no value.

    :param value: field value
    :return: value from defined source, value from sAMAccountName, or None.
    """
    if value and value.isdigit():
        value = int(value)
        epoch_start = datetime(year=1601, month=1, day=1)
        seconds_since_epoch = value/10**7
        try:
            as_date = epoch_start + timedelta(seconds=seconds_since_epoch)
        except OverflowError:
            as_date = datetime.max
        dtt = as_date.timetuple()
        return int(time.mktime(dtt))

    return value
