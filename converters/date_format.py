import datetime

import arrow


def converter(field, record, value, params):
    """
    Converts a date field to epoch time.

    :param value: field value
    :return: epoch time
    """
    # float_timestamp rather than the timestamp property: arrow 1.0 turned
    # timestamp into a method, so reading it returns a bound method that
    # json.dumps emits as null, losing the date silently. float_timestamp is a
    # property on every release; int_timestamp only exists from 0.17.0, and the
    # on-premise requirements.txt still pins 0.12.1.
    if isinstance(value, datetime.datetime):
        return int(arrow.get(value).float_timestamp)

    try:
        if ' ' in value:
            return int(arrow.get(value, "YYYY-MM-DD HH:mm:ss").float_timestamp)
        else:
            return int(arrow.get(value).float_timestamp)
    except:
        return value
