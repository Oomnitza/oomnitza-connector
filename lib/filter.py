__author__ = 'daniel'

import logging
logging.basicConfig()
LOG = logging.getLogger("lib/filter")

from . import converters
from utils.data import get_field_value


class DynamicException(Exception):
    pass

GLOBALS = {
    'LOG': LOG,
    'DynamicException': DynamicException,
    'converter': converters.builtin_converter,
    'cae': converters.builtin_cea,
    'get_field_value': get_field_value
}

CONVERTER_WRAPPER = """
def {name}(field, record, value, params):
{code}
result = {name}(field, record, value, params)
"""

FILTER_WRAPPER = """
def the_filter(record):
{code}
result = the_filter(record)
"""


class DynamicConverter(object):
    def __init__(self, name, filter_str):
        self._name = name
        self._filter_str = filter_str

        self._filter = parse_converter(name, self._filter_str)

        converters.Converter.register_converter(self._name, self)

    def __call__(self, field, record, value, params):
        LOG.debug("running FilterConverter: %s", self._name)
        return self._filter(field, record, value, params)


def parse_filter(filter_str):
    try:
        code = FILTER_WRAPPER.format(code=filter_str)
        LOG.debug("Compiling filter: %r", code)
        code = compile(code, "the_filter", 'exec')

        def run_filter(record):
            locals = {
                '__name__': u"__main__",
                'record': record,
            }
            try:
                exec code in GLOBALS.copy(), locals
                return locals.get('result', None)
            except DynamicException:
                raise
            except Exception as exp:
                raise DynamicException(repr(exp))

        return run_filter
    except IndentationError as exp:
        # LOG.exception("IndentationError calling compile()")
        raise IndentationError("Please ensure all filters have at least 2 spaces in front of each line.")
    except SyntaxError as exp:
        LOG.exception("SyntaxError calling compile()")
        raise
    except TypeError as exp:
        LOG.exception("TypeError calling compile()")
        raise

def parse_converter(name, filter_str):
    try:
        code = CONVERTER_WRAPPER.format(name=name, code=filter_str)
        LOG.debug("Compiling converter: %r", code)
        code = compile(code, name, 'exec')

        def run_converter(field, record, value, params):
            locals = {
                '__name__': u"__main__",
                'field': field,
                'record': record,
                'value': value,
                'params': params,
            }
            exec code in GLOBALS.copy(), locals
            return locals.get('result', None)
        return run_converter
    except IndentationError as exp:
        # LOG.exception("IndentationError calling compile()")
        raise IndentationError("Please ensure the converter %r has at least 2 spaces in front of each line." % name)
    except SyntaxError as exp:
        LOG.exception("SyntaxError calling compile()")
        raise
    except TypeError as exp:
        LOG.exception("TypeError calling compile()")
        raise
    except:
        LOG.exception("Unhandled exception running filter.")
