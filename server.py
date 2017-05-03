import logging

from gevent import pywsgi

from connector import prepare_connector, parse_command_line_args

LOG = logging.getLogger("connector_server")


class Server(object):
    """
    WSGI server based on gevent
    """

    non_oomnitza_connectors = None
    oomnitza_connector = None
    options = None

    host = None
    port = None
    workers = None

    def __init__(self, command_line_args):
        self.host = command_line_args.host
        self.port = command_line_args.port

        self.non_oomnitza_connectors, self.oomnitza_connector, self.options = prepare_connector(command_line_args)

    def handle_incoming_request(self, environ, response):

        # take the last part of the url as identifier of connector to handle the request
        connector_name = environ['PATH_INFO'].split('/')[-1]
        connector_to_handle_request = self.non_oomnitza_connectors.get(connector_name)
        if not connector_to_handle_request:
            LOG.warning('Received request cannot be handled because connector "%s" is not active or does not exist' % connector_name)

        else:
            try:
                connector_to_handle_request['__connector__'].server_handler(environ, self.options)
            except NotImplementedError:
                LOG.warning('Received request cannot be handled because connector "%s" does not support server mode' % connector_name)

        response('204 NO CONTENT', [('Content-Type', 'text/html')])
        return [None]

    def http_server(self):
        http_server = pywsgi.WSGIServer((self.host, int(self.port)),
                                        self.handle_incoming_request)
        LOG.info('--CONNECTOR SERVER STARTED--')
        http_server.serve_forever()


if __name__ == '__main__':

    cmdline_args = parse_command_line_args(for_server=True)

    Server(cmdline_args).http_server()
