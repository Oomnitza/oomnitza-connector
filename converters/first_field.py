
import logging
logger = logging.getLogger("converters/first_field")


def converter(field, record, value, params):
    """
    Returns the first value from a list of fields.
    params:
        fields: Required: List of fields in which to look for a value.

    :param value: field value
    :return:
    """
    if value:  # We have a value, don't need to look at the other fields...
        return value

    try:
        fields = params.get('fields', "")
        if not fields:
            return None
        fields = fields.split(',')
        for field in fields:
            val = record.get(field, '').strip()
            if val:
                return val
        return None
    except:
        logger.error("Error running first_field() converter on %r.", field)
        return None

