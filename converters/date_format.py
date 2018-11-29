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
        if ' ' in value:
            return arrow.get(value, "YYYY-MM-DD HH:mm:ss").timestamp
        else:
            return arrow.get(value).timestamp
    except:
        return value
