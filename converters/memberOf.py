
import logging
logger = logging.getLogger("converters/memberOf")


def converter(field, record, value, params):
    """
    Returns the first value from a list of fields.
    params:
        fields: Required: List of fields in which to look for a value.

    :param value: field value
    :return:
    """
    default = params.pop('default', None)

    try:
        for search_val, return_val in params.items():
            if search_val in value:
                return return_val

        return default
    except:
        logger.exception("Error running memberOf() converter on %r.", field)
        return None

