
import logging
logger = logging.getLogger("converters/capitalize")


def converter(field, record, value, params):
    """
    Capitalize the first letter of field value.
    :param value: field value
    :return: string with capitalized first letter
    """

    if not value:
        return value
    try:
        return value.capitalize()
    except Exception:
        logger.error("Error running capitalize() converter.")
        return value
