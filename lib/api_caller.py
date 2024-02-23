import logging
from typing import Optional

from lib.httpadapters import SSLAdapter
from lib.renderer import Renderer
from requests import Response, HTTPError


class ExternalAPICaller:

    def perform_api_request(
        self,
        logger: logging.Logger,
        http_method: str,
        url: str,
        headers: dict,
        params: dict,
        body: Optional[str],
        raise_error: bool,
        ssl_adapter: SSLAdapter = None,
    ) -> Response:

        # preset the specific user agent
        headers['User-Agent'] = 'Oomnitza Connector'

        if body and isinstance(body, str):
            body = body.encode()

        # noinspection PyUnresolvedReferences
        session = self._get_session()
        if ssl_adapter:
            session.mount(url, ssl_adapter)

        logger.info('Issuing %s %s', http_method, url)
        logger.debug('..params=[%s]', params)

        response = session.request(
            method=http_method,
            url=url,
            headers=headers,
            params=params,
            data=body
        )

        if raise_error:
            try:
                response.raise_for_status()
            except Exception as ex:
                if isinstance(ex, HTTPError) and ex.response.status_code == 403:
                    permission_error = f'The Integration User must have appropriate permissions. Reason: {str(ex)}'
                    ex.args = (permission_error,) + ex.args[1:]
                    logger.error('Encountered an exception. %s', permission_error)
                else:
                    logger.error('Encountered an exception. Reason [%s]', str(ex))
                raise ex

        logger.debug('Response code [%s]', response.status_code)

        return response


class ConfigurableExternalAPICaller(ExternalAPICaller, Renderer):

    def build_call_specs(
        self, 
        http_specs: dict, 
        raise_error: bool = True
    ) -> dict:

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

