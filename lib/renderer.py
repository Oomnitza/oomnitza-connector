import importlib
from logging import Logger
from typing import Any, Optional, Dict

from jinja2 import UndefinedError, Undefined, TemplateSyntaxError, Environment
from jinja2.exceptions import SecurityError
from jinja2.nativetypes import NativeEnvironment
from jinja2.sandbox import SandboxedEnvironment

from lib.error import ConfigError

logger = Logger(__name__)


class _RawValue:

    def __init__(self, value):
        self._value = value

    def render(self):
        return self._value


class ImportSupportJinjaEnvMixin:

    def make_globals(self, d: Optional[Dict]):
        custom_d = {
            # we are going to define some initial context to be always set here.
            # for example with `import` we can handle such templates to use the python packages within the python env;
            #       "{%set base64 = import('base64')%}{{base64.b64encode(inputs['something'].encode())}}"
            'import': importlib.import_module
        }
        if d:
            custom_d.update(**d)
        # noinspection PyUnresolvedReferences
        return super(ImportSupportJinjaEnvMixin, self).make_globals(custom_d)


class SafeEnvironmentWithImportSupport(ImportSupportJinjaEnvMixin, SandboxedEnvironment):

    safe_stdlib_modules = (
        # this list is supported for python 3.6 - 3.9
        # https://docs.python.org/3.6/library/
        # https://docs.python.org/3.7/library/
        # https://docs.python.org/3.8/library/
        # https://docs.python.org/3.9/library/
        'string',
        're',
        'struct',
        'datetime',
        'calendar',
        'time',
        'collections',
        'bisect',
        'math',
        'random',
        'statistics',
        'hashlib',
        'hmac',
        'secrets',
        'json',
        'base64',
        'binhex',
        'binascii',
        'html',
        'xml',
        'urllib.parse',
        'uuid',
    )

    def call(__self, __context, __obj, *args, **kwargs):
        if __obj == importlib.import_module and len(args) == 1:
            if args[0] not in __self.safe_stdlib_modules:
                raise SecurityError(f"{args[0]} is not safely importable")
        return super().call(__context, __obj, *args, **kwargs)


class SafeNativeEnvironmentWithImportSupport(SafeEnvironmentWithImportSupport, NativeEnvironment):
    """
    This environment will be used for the rendering to the native value,
    but because the value for the rendering can be a user input, it also must be safe
    """
    pass


class StringEnvironmentWithImportSupport(ImportSupportJinjaEnvMixin, Environment):
    """
    This environment will be used for the rendering to the string value, its purpose mostly is to process the data and values
    given in the managed connector execution flow.

    NOTE: it is not safe and MUST NOT be used for the arbitrary user input processing
    """
    pass


class _GlobalVariableContext:
    """
    Implementation of the global settings for the Jinja context
    """

    __internal_dict = None
    __oomnitza_connector = None

    def __init__(self, oomnitza_connector):
        self.__oomnitza_connector = oomnitza_connector

    def _call_for_global_settings(self) -> dict:
        return {
            _['name']: _['value']
            for _ in self.__oomnitza_connector.get_global_variables_list()
        }

    def __getitem__(self, item):
        if self.__internal_dict is None:
            self.__internal_dict = self._call_for_global_settings()

        if item in self.__internal_dict:
            return self.__internal_dict[item]

        raise AttributeError


class Renderer:
    """
    Common Jinja2 renderer, usable in the different places

    """
    jinja_string_env = None
    jinja_native_env = None
    rendering_context = None

    def __init__(self, *args, **kwargs):
        # NOTE 1: Init 3d-party context at the class initialization to avoid extra
        # API calls in case of big amount of variables to render

        # NOTE 2: All classes inherited by Renderer have access to OomnitzaConnector
        # Renderer -> ConfigurableExternalAPICaller -> ManagedConnector (Connector) -> Connector
        # So to not create one more standalone inconsistent function we will reuse it

        # NOTE 3: .pop() instead .get() because in case of native usage of Renderer it will call
        # python native Object __init__(self) that doesnt has *args, **kwarg in the function signature
        oomnitza_connector = kwargs.pop('oomnitza_connector', None) or self.OomnitzaConnector
        self.rendering_context = {
            'GlobalSetting': _GlobalVariableContext(oomnitza_connector=oomnitza_connector)
        }

        self.jinja_string_env = StringEnvironmentWithImportSupport()
        self.jinja_native_env = SafeNativeEnvironmentWithImportSupport()
        super().__init__(*args, **kwargs)

    def update_rendering_context(self, **kwargs):
        self.rendering_context.update(**kwargs)

    def clear_rendering_context(self, *args):
        for arg in args:
            self.rendering_context.pop(arg, None)

    def render_to_string(self, template: Any) -> str:
        """
        Render the value to the string
        """
        try:
            return self.jinja_string_env.from_string(str(template)).render(**self.rendering_context)
        except UndefinedError:
            logger.debug(f'Failed to render to string. Template: {str(template)}. Context: {self.rendering_context}')
            return ''
        except TemplateSyntaxError as e:
            raise ConfigError(f'Invalid configuration for the managed connector: {e.message}')

    def render_to_native(self, template: Any) -> Any:
        """
        Render the value to its native type based on the inputs
        """
        try:
            val = self.jinja_native_env.from_string(str(template)).render(**self.rendering_context)
            if val == Undefined():
                raise UndefinedError

            if isinstance(val, _RawValue):
                return val.render()

            return val
        except UndefinedError:
            logger.debug(f'Failed to render to native. Template: {str(template)}. Context: {self.rendering_context}')
            return None
        except TemplateSyntaxError as e:
            raise ConfigError(f'Invalid configuration for the managed connector: {e.message}')
