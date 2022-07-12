import logging

logger = logging.getLogger("converters/empty_key_remover")


def converter(record, **kwargs):
    """
    Remove empty values from dictionary.
    :param value: field value
    :return: dict without empty key values.
    """

    return {k: v for k, v in record.items() if v}
