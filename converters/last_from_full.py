

def converter(field, record, value):
    """
    Splits a field on ' ' and returns the last part.

    :param value: field value
    :return: everything after the ' '
    """
    if value:
        return value.split(' ')[-1]
    return value
