import datetime

import arrow


def converter(field, record, value, params):
    """
    Converts a date field to epoch time.

    :param value: field value
    :return: epoch time
    """
    if isinstance(value, datetime.datetime):
        return arrow.get(value).timestamp

    try:
        if 'T' in value:
            return arrow.get(value).timestamp
        elif ' ' in value:
            return arrow.get(value, "YYYY-MM-DD HH:mm:ss").timestamp
    except:
        return value
