from typing import Optional

from requests import Response

from lib.httpadapters import SSLAdapter
from lib.renderer import Renderer


class ExternalAPICaller:

    def perform_api_request(
        self,
        http_method: str,
        url: str,
        headers: dict,
        params: dict,
        body: Optional[str],
        raise_error: bool,
        ssl_adapter: SSLAdapter = None
    ) -> Response:

        # preset the specific user agent
        headers['User-Agent'] = 'Oomnitza Connector'

        if body and isinstance(body, str):
            body = body.encode()

        # noinspection PyUnresolvedReferences
        session = self._get_session()
        if ssl_adapter:
            session.mount(url, ssl_adapter)

        response = session.request(
            method=http_method,
            url=url,
            headers=headers,
            params=params,
            data=body
        )

        if raise_error:
            response.raise_for_status()

        return response


class ConfigurableExternalAPICaller(ExternalAPICaller, Renderer):

    def build_call_specs(self, http_specs: dict, raise_error: bool = True) -> dict:
        call_spec = dict(
            raise_error=raise_error,
            http_method=http_specs['http_method'],
            url=self.render_to_string(http_specs['url']),
        )
        if 'body' in http_specs:
            call_spec['body'] = self.render_to_string(http_specs['body'])
        else:
            call_spec['body'] = None

        call_spec['headers'] = {_['key']: self.render_to_string(_['value']) for _ in http_specs['headers']}
        call_spec['params'] = {_['key']: self.render_to_string(_['value']) for _ in http_specs['params']}
        return call_spec

    def api_call(self, *args, **kwargs):
        return self.perform_api_request(**self.build_call_specs(*args, **kwargs))
