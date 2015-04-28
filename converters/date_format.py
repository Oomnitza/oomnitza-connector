
import time
import datetime


def converter(field, record, value, params):
    """
    Converts a date field to epoch time.

    :param value: field value
    :return: epoch time
    """
    if isinstance(value, datetime.datetime):
        return int((value - datetime.datetime(1970, 1, 1)).total_seconds())

    if value not in [None, '', ' ']:
        if 'T' in value:
            value = value.split('T')[0]
        elif ' ' in value:
            value = value.split(' ')[0]
        return int(time.mktime(time.strptime(value, "%Y-%m-%d")))
    else:
        return value
