
import logging
logger = logging.getLogger("converters/concat")


def converter(field, record, value, params):
    """
    Concatenates the supplied values.

    params:
        values: Required: List of fields and values to concat.

    Notes:
        String values must be wrapped in single or double quotes. If not, it will be treated as a field name.

    :return:
        concatenated value
    """
    try:
        parts = []
        values = params.get('values', "")
        if not values:
            return None
        values = values.split(',')
        for value in values:
            if value[0] == value[-1] and value[0] in ('"', "'"):
                parts.append(value[1:-1])
            else:
                parts.append(record.get(value, '').strip())
        return "".join(parts)
    except:
        logger.debug("Error running concat() converter on %r.", field)
        return None

