
import importlib


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
