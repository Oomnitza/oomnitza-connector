
import importlib
import logging

LOG = logging.getLogger("lib/converters")


class Converter(object):
    def __init__(self):
        self.__loaded_converters = {}

    def run_converter(self, name, field, record, value, params):
        converter = self.__loaded_converters.get(name, None)
        if not converter:
            # the converter has not been loaded yet, so load it and save it into cls.Converters
            mod = importlib.import_module("converters.{0}".format(name))
            converter = mod.converter
            self.__loaded_converters[name] = converter

        return converter(field, record, value, params)

    def register_converter(self, name, converter):
        self.__loaded_converters[name] = converter

Converter = Converter()


def builtin_converter(record, name, **kwargs):
    """
    converter( Converter Name, **key=value )
    Calls the named converter, passing it the key=value params.

    :param name: the name of the converter to call.
    :param kwargs: key=value pairs to be passed to the converter.
    :return: the response from the converter.
    """
    return Converter.run_converter(
        name,
        field=None,
        record=record,
        value=None,
        params=kwargs
    )


def builtin_cea(record, attr, default=None):
    """
    cea( Custom Attr Name, Optional Default Value )
    Calls the casper_extension_attribute converter.

    :param attr: name of the Extension Attribute (field labelin Casper).
    :param default: the default value to return is none is provided.
    :return:
    """
    return Converter.run_converter(
        'casper_extension_attribute',
        field=None,
        record=record,
        value=None,
        params={
            'attr': attr,
            'default': default,
        }
    )



