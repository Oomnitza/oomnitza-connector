import datetime

import arrow
import time



def converter(field, record, value,params='', **kwargs):
    """
    Converts a date field to epoch time.

    :param value: field value
    :return: epoch time
    """
    if isinstance(value, datetime.datetime):
        return arrow.get(value).timestamp

    try:
        if isinstance(value,str) and ' ' in value:
            # return arrow.get(value, "YYYY-MM-DD HH:mm:ss").timestamp
            return arrow.get(value).format("YYYY-MM-DD")
        elif isinstance(value,int):
            unit_type = kwargs.get("unit_type",None)
            if isinstance(unit_type,str):
                if unit_type == "ms":
                    value = value // 1000
                    if kwargs.get("return_timestamp", False):
                        return value
            output = arrow.get(value)
            return output.format('YYYY-MM-DD HH:mm:ss')
        else:
            arrow_obj = arrow.get(value)
            return value
    except:
        return value
