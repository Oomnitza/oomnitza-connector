import logging
import logging.config
import uuid
from typing import Any, Dict, MutableMapping, Tuple


class ContextLoggingAdapter(logging.LoggerAdapter):
    """
    Include a contextual identifier for grouping related log entries 
    
    In an environment where logs from multiple sources are intertwined/aggregated with log
    output from other services, we can filter by `context_id` to follow the sequence
    of call(s)/response(s) from a single API request, or group of requests

    """
    HEADER_CONTEXT_ID = 'X-Context-Id'

    @staticmethod
    def generate_unique_context_id():
        """
        Return Unique UUID

        Returns:
            str: Context id uuid
        """
        return str(uuid.uuid4())        
    
    @staticmethod
    def generate_context_id_from_headers(headers: Dict[str, Any] = None):
        """
        Return 'HEADER_CONTEXT_ID' from headers if present, otherwise generate UUID

        Args:
            headers (Dict[str, Any], optional): Request headers if any.

        Returns:
            str: Context id
        """
        if headers:
            context_id = headers.get(ContextLoggingAdapter.HEADER_CONTEXT_ID)
            if context_id: 
                return context_id
            
        return ContextLoggingAdapter.generate_unique_context_id()
        
    
    def __init__(self, logger: logging.Logger, context_id: str, **kwargs) -> None:
        """
        Args:
            logger (Logger): Standard logger from logging package
            context_id (str): Contextual identifier, can be any value but usually a UUID
            kwargs (MutableMapping[str, Any]): kwargs passed to base class

        """
        self._context_id = context_id
        super().__init__(logger, kwargs)
        
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> Tuple[Any, MutableMapping[str, Any]]:
        """
        Inserts the `context_id` into the logging output
        Note: No need to call directly, it's automatically called by logger
        """
        
        return super().process(f'{msg} [{self.get_context_id()}]', kwargs)
    
    def get_context_id(self) -> str:
        """
        Return the current logging context identifier

        Returns:
            str: context id
        """
        return self._context_id


