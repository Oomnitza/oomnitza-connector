__author__ = 'daniel'

import logging
import re
import functools

LOG = logging.getLogger("lib/filter/tree")  # pylint:disable=invalid-name

from .. import converters


class Statement(object):
    Environment = {}

    @classmethod
    def reset_environment(cls):
        cls.Environment = {
            'True': True, 'False': False,
            'tmp': {},
            'result': {},
        }
Statement.reset_environment()


class Expression(Statement):
    pass


class Literal(Statement):
    def __init__(self, value):
        self._value = value

    def __call__(self, record):
        return self._value


class Field(Statement):
    def __init__(self, keys, default=None):
        self._keys = keys
        self._default = default

    def __call__(self, record):
        LOG.debug("Field( %r, %r, %r )", self._keys, record, self._default)
        if self._keys[0] == "record":
            if not record:
                return self._default
            data = record
        elif self._keys[0] in self.Environment:
            data = self.Environment.get(self._keys[0])
        else:
            raise SyntaxError("Can not set variable %r." % '.'.join(self._keys))

        for key in self._keys[1:]:
            if isinstance(data, list) and key.isdigit():
                data = data[int(key)]
            elif key in data:
                data = data[key]
            else:
                LOG.warning("failed to get value for %r", self._keys)
                return self._default

        return data

    def set(self, record, value):
        if self._keys[0] == 'record':
            raise SyntaxError("Can't set field in record at this time: %r" % '.'.join(self._keys))
        if len(self._keys) == 1:
            raise SyntaxError("Can't set global values at this time: %r" % '.'.join(self._keys))
        if [k for k in self._keys if k.isdigit()]:
            raise SyntaxError("Set statement can't index a list at this time: %r" % '.'.join(self._keys))

        try:
            data = self.Environment[self._keys[0]]
        except KeyError as exp:
            raise SyntaxError("Can't set variable %r." % self._keys[0])

        for key in self._keys[1:-1]:
            data = data.setdefault(key, {})
        data[self._keys[-1]] = value

    @property
    def keys(self):
        return self._keys


class Bool(Expression):
    def __init__(self, lexpr, oper, rexpr):
        self._lexpr = lexpr
        self._oper = oper
        self._rexpr = rexpr

    def __call__(self, record):
        lvalue = self._lexpr(record)
        rvalue = self._rexpr(record)
        return self._oper(lvalue, rvalue)


class Set(Expression):
    def __init__(self, field, expr):
        self._field = field
        self._expr = expr

    def __call__(self, record):
        self._field.set(record, self._expr(record))
        return True


class If(Expression):
    def __init__(self, condition, true_stmts, false_stmts):
        self._condition = condition
        self._true_stmts = true_stmts
        self._false_stmts = false_stmts

    def __call__(self, record):
        stmts = self._true_stmts
        if not self._condition(record):
            stmts = self._false_stmts

        for stmt in stmts:
            if not stmt(record):
                return False
        return True


class RegEx(Expression):
    def __init__(self, lexpr, rexpr):
        self._lexpr = lexpr
        self._rexpr = rexpr

        self._regex = re.compile(rexpr({}))

    def __call__(self, record):
        lvalue = self._lexpr(record)
        return self._regex.match(lvalue)


class And(Statement):
    def __init__(self, children):
        self._children = children

    def pprint(self, indent=0):
        print "{}AND {{".format(' '*indent)
        for child in self._children:
            child.pprint(indent+4)
        print "{}}}".format(' '*indent)

    def __repr__(self):
        return "AND( {} )".format(repr(self._children))

    def __call__(self, record):
        for child in self._children:
            if not child(record):
                return False
        return True


class Or(Statement):
    def __init__(self, children):
        self._children = children

    def pprint(self, indent=0):
        print "{}OR {{".format(' '*indent)
        for child in self._children:
            child.pprint(indent+4)
        print "{}}}".format(' '*indent)

    def __repr__(self):
        return "OR( {} )".format(repr(self._children))

    def __call__(self, record):
        for child in self._children:
            if child(record):
                return True
        return False


class Converter(Statement):
    EnabledConverters = {
        'casper_extension_attribute': True,
    }

    def __init__(self, converter_name, params={}):
        if converter_name not in self.EnabledConverters:
            raise Exception("Unknown converter: %r" % (converter_name,))
        self._converter_name = converter_name
        self._params = params

    def pprint(self, indent=0):
        print "{}{}".format(' '*indent, repr(self))

    def __call__(self, record):
        return converters.Converter.run_converter(
            self._converter_name,
            field=None,
            record=record,
            value=None,
            params=self._params
        )

    def __repr__(self):
        return "converter( {}, {} )".format(self._converter_name, self._params)


def _builtin_converter(record, name, **kwargs):
    return converters.Converter.run_converter(
        name,
        field=None,
        record=record,
        value=None,
        params=kwargs
    )


def _builtin_cea(record, attr, default=None):
    return converters.Converter.run_converter(
        'casper_extension_attribute',
        field=None,
        record=record,
        value=None,
        params={
            'attr': attr,
            'default': default,
        }
    )


def _builtin_number(record, value):
    try:
        return float(value)
    except ValueError:
        LOG.exception("_builtin_number( %r )", value)
        return "NaN"
    except:
        raise


def _builtin_split(record, value, sep, part=0):
    try:
        return str(value).split(sep, 1)[int(part)]
    except:
        LOG.exception("Error splitting value %r on %r." % (value, sep))
        return ""


def _builtin_startswith(record, value):
    try:
        return str(value).startswith(value)
    except:
        LOG.exception("Error checking value %r on %r." % (value,))
        return ""


def _builtin_endswith(record, value):
    try:
        return str(value).endswith(value)
    except:
        LOG.exception("Error splitting value %r on %r." % (value,))
        return ""



class FunctionCall(Statement):
    EnabledFunctions = {
        'converter': _builtin_converter,
        'number': _builtin_number,
        # 'float': _builtin_number,

        'cea': _builtin_cea,
        'split': _builtin_split,

        'startswith': _builtin_startswith,
        'endswith': _builtin_endswith,
    }

    def __init__(self, name, params=None):
        self._name = name[1]
        self._params = params or ([], {})

        self._fn = self.EnabledFunctions.get(self._name, None)
        if self._fn is None:
            raise Exception("Unknown method: %r" % (name,))

    def pprint(self, indent=0):
        print "{}{}".format(' '*indent, repr(self))

    def __call__(self, record):
        args = [arg(record) if callable(arg) else arg for arg in self._params[0]]
        kwargs = {name: value(record) if callable(value) else value for name, value in self._params[1].items()}

        try:
            return self._fn(record, *args, **kwargs)
        except TypeError as exp:
            raise SyntaxError(str(exp).replace('_builtin_', '', 1))

    def __repr__(self):
        return "{}{}".format(self._name, repr(self._params))


