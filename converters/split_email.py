

def converter(field, record, value):
    """
    Splits a field on '@' and returns the first part.

    :param value: field value
    :return: everything before the '@'
    """
    if value:
        return value.split('@')[0]
    return value
