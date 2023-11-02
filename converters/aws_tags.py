
import logging
logger = logging.getLogger("converters/aws_tags")
import json
from collections import OrderedDict

def converter(field, record, value, params):
    """
    Capitalize the first letter of field value.
    :param value: field value
    :return: string with capitalized first letter
    """

    if not value:
        return value
    try:
        output = ""
        if isinstance(value,dict):
            ordered_values = OrderedDict(value)
            for key,val in sorted(ordered_values.items()):
                # key,val = kv_pair
                output = output + "{key} = {val}\r\n".format(key=key,val=val)
        logger.debug("Converted tags to: \r\n{}".format(output))
        return output
    except:
        logger.error("Error running aws_tags() converter on %r.", value)
        return value
