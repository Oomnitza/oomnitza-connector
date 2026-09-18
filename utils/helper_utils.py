import json
from datetime import date, datetime

import xmltodict

import logging
logger = logging.getLogger(__name__)


# noinspection PyBroadException
def response_to_object(response_text):
    """
    Try to represent the response as the native object from the JSON- or XML-based response
    """
    try:
        return json.loads(response_text)
    except:
        try:
            return xmltodict.parse(response_text)
        except:
            logger.warning(f"Failed to parse to json and xml, returning response data.")
            return response_text

def json_serializer(value):
    """
    In the `--save-data` mode and anywhere we use JSON to send data, we are dumping the data to the JSON notation.
    So we should pre-process the values to be sure these can be represented as the
    JSON (https://docs.python.org/2/library/json.html#py-to-json-table)
    """
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    logger.warning("Value of type %s cannot be serialised and is being sent as null.",
                   type(value).__name__)
