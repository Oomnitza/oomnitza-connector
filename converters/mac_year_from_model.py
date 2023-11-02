import logging
import requests

logger = logging.getLogger("converters/mac_model_from_sn")  # pylint:disable=invalid-name
MAC_MODEL_TABLE = {
    "MacBookPro11,4" : 2015,
    "MacBookPro12,1" : 2015,
    "MacBookPro15,1" : 2018,
    "MacBookPro14,3" : 2017,
    "MacBookPro11,2" : 2014,
    "MacBookPro9,1" : 2012,
    "MacBookPro11,1": 2013,
    "MacBookPro8,2" : 2011,
    "MacBookPro11,5" : 2015,
    "MacBookPro11,3": 2013,
    "MacBookPro10,1" : 2012,
    "MacBookPro9,2" : 2012,
    "MacBookPro6,2" : 2010,
    "MacBookPro7,1": 2010,
    "MacBookPro8,1" : 2011,
    "MacBookPro10,2" : 2012,
    "MacBookPro5,1" : 2009,
    "MacBookPro5,4" : 2010,
    "MacBookPro5,5" : 2010,
    "MacBookPro13,2" : 2016,
    "MacBookPro14,1" : 2017,
    "MacBookPro13,1" : 2016,
    "MacBookPro13,3" : 2016,
    "MacBookPro14,2" : 2017,
    "MacBookAir7,2" : 2015,
    "MacBookAir4,2" : 2011,
    "MacBookAir6,2" : 2013,
    "MacBookAir5,2" : 2012,
    "MacBookAir6,1" : 2013,
    "MacBookAir4,1" : 2011
}

def converter(record, model, **kwargs):
    """
    Converts a Apple model to model year

    :param value: the casper model field. hardware.model. This will be used if the serial_number fails lookup.
    :return: nice model name
    """

    return MAC_MODEL_TABLE.get(model,None)
