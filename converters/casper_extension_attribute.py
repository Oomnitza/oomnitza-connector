
import logging
logger = logging.getLogger(__file__)


def converter(field, record, value, params):
    """
    Loads a value from Casper's Extension Attributes.

    :param value: field value
    :return:
    """
#    logger.warn("converter(%r, %r, %r, %r)", field, record, value, params)

    attributes = record.get('extension_attributes', [])
    target = params.get('attr', None)
    default = params.get('default', None)

    logger.warn("converter.attributes = %r", attributes)
    logger.warn("converter.target = %r", target)
    logger.warn("converter.default = %r", default)

    for attribute in attributes:
        logger.warn("    attribute = %r", attribute)

        if attribute.get('name') == target:
            return attribute.get('value')

    return default

