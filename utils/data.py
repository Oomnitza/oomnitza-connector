
import logging

LOGGER = logging.getLogger(__name__)


def get_field_value(data, field, default=None):
    """
    Will return the field value out of data.
    Field can contain '.', which will be followed.
    :param field: the field name, can contain '.'
    :param data: the data as a dict, can contain sub-dicts
    :param default: the default value to return if field can't be found
    :return: the field value, or default.
    """
    if not data:
        return default

    try:
        if '.' in field:
            current, rest = field.split('.', 1)
            if isinstance(data, list) and current.isdigit():
                return get_field_value(data[int(current)], rest, default)
            if current in data:
                return get_field_value(data[current], rest, default)

        return data.get(field, default)
    except:
        LOGGER.exception("failed to get_field_value()")
        return None
