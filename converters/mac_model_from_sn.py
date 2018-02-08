import logging
import requests

logger = logging.getLogger("converters/mac_model_from_sn")  # pylint:disable=invalid-name


def converter(field, record, value, params):
    """
    Converts a Apple SN into a nice Model

    :param value: the casper model field. hardware.model. This will be used if the serial_number fails lookup.
    :return: nice model name
    """
    serial_number = str(record['general']['serial_number']).strip()
    # Don't even attempt to lookup empty serial numbers
    if not serial_number:
        return value

    try:
        url = "{}/?sn={}".format("https://nam.oomnitza.com", serial_number)
        response = requests.get(url)
        model = response.text
        return model if not model.startswith('Error') else value
    except:
        logger.error("Lookup of Model failed for sn: %r.", serial_number)
        return value
