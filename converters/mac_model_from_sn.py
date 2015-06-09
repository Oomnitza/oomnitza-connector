
import logging
import urllib2
import xmltodict

logger = logging.getLogger("converters/mac_model_from_sn")  # pylint:disable=invalid-name


def converter(field, record, value, params):
    """
    Converts a Apple SN into a nice Model

    :param value: serial number
    :return: nice model name
    """
    try:
        url = "http://support-sp.apple.com/sp/product?cc={}&lang=en_US".format(
            record['general']['serial_number'][-4:]
        )
        response = urllib2.urlopen(url)
        response = xmltodict.parse(response.read())['root']
        return response['configCode']
    except:
        logger.warning("First attempt to lookup model (with last 4 of serial number) failed.")
        try:
            url = "http://support-sp.apple.com/sp/product?cc={}&lang=en_US".format(
                record['general']['serial_number'][-3:]
            )
            response = urllib2.urlopen(url)
            response = xmltodict.parse(response.read())['root']
            return response['configCode']
        except:
            logger.error("Second attempt to lookup model (with last 3 of serial number) failed.")
            return value
