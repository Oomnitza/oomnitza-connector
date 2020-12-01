import importlib
from logging import Logger
from typing import Any

from jinja2 import Environment, UndefinedError, Undefined, TemplateSyntaxError
from jinja2.nativetypes import NativeEnvironment

from lib.error import ConfigError

logger = Logger(__name__)


class Renderer:
    """
    Common Jinja2 renderer, usable in the different places

    """
    jinja_string_env = None
    jinja_native_env = None
    rendering_context = None

    def __init__(self, *args, **kwargs):
        self.rendering_context = {
            # we are going to define some initial context to be always set here.
            # for example with `import` we can handle such templates to use the python packages within the python env;
            #       "{%set base64 = import('base64')%}{{base64.b64encode(inputs['something'].encode())}}"
            #       "{%set arrow = import('arrow')%}{{arrow.utcnow().replace(days=-3).timestamp}}"
            'import': importlib.import_module
        }
        self.jinja_string_env = Environment()
        self.jinja_native_env = NativeEnvironment()
        super().__init__(*args, **kwargs)

    def update_rendering_context(self, **kwargs):
        self.rendering_context.update(**kwargs)

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
            return val
        except UndefinedError:
            logger.debug(f'Failed to render to native. Template: {str(template)}. Context: {self.rendering_context}')
            return None
        except TemplateSyntaxError as e:
            raise ConfigError(f'Invalid configuration for the managed connector: {e.message}')
