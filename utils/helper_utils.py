import json
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
