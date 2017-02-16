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
            value = value.split('T')[0]
        elif ' ' in value:
            value = value.split(' ')[0]

        return arrow.get(value, "YYYY-MM-DD").timestamp
    except:
        return value
