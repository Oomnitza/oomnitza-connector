import asyncio
from asyncio import events

import tornado.web
from tornado.web import RequestHandler

from requests.exceptions import RequestException
# import the connectors
from connectors import (
    meraki_network_devices,
    munki_report,
    mobileiron,
    dell_asset_order_status
)
from lib.connector import response_to_object
from constants import SHIM_PORT

import logging

LOG = logging.getLogger("shim_service.py")

DEFAULT_API_PATH = "/api/v1/"
USERS_PATH       = "users/"
ASSETS_PATH      = "assets/"
SECTION          = "oomnitza"
SERVICE_NAME     = "Shim-Service"


class DefaultShimHandler(RequestHandler):
    def set_default_headers(self, msg="Method not allowed. Http Error 405"):
        self.set_header("Content-Type", 'application/json')
        self.set_header("Accept", 'application/json')
        self.set_header("Service", f"Oomnitza {SERVICE_NAME}")

    def _default_response(self):
        raise tornado.web.HTTPError(405)

    def get(self):
        self._default_response()

    def post(self, *args, **kwargs):
        self._default_response()

    def delete(self, *args, **kwargs):
        self._default_response()

    def patch(self, *args, **kwargs):
        self._default_response()

    def return_http_error(self, status_code, msg, **kwargs):
        LOG.error(f"Http error from {SERVICE_NAME} with code: {status_code}, {msg}")
        self.set_status(200)
        self.finish({
                        "code": status_code,
                        "shim_error_message": msg,
                    })


################################
# All Asset list apis are here #
################################

class CiscoMerakiNetworkAssetLoad(DefaultShimHandler):

    def initialize(self):
        self.meraki_connector = meraki_network_devices.Connector(SECTION, {})

    def post(self, *args, **kwargs):
        settings = response_to_object(self.request.body)
        settings[self.meraki_connector.api_key] = str(self.request.headers.get(self.meraki_connector.api_key))
        LOG.info(f"{self.__class__.__name__}: Fetching the Meraki Devices.")

        try:
            devices, starting_after, network_ids, is_inventory_collected = self.meraki_connector.load_shim_records(settings)
            self.write({"devices": devices, "starting_after": starting_after,
                        "network_ids": network_ids, "is_inventory_collected": is_inventory_collected})
        except RequestException as req_err:
            self.return_http_error(req_err.response.status_code, str(req_err))


class MobileIronAssetLoad(DefaultShimHandler):

    settings = {}

    def initialize(self):
        """
        This method initializes the object of the class MobileIronConnector.
        """

        self.settings = response_to_object(self.request.body)
        self.settings['Authorization'] = self.request.headers.get('Authorization')
        self.mobileiron_connector = mobileiron.Connector(SECTION, self.settings)

    def post(self, *args, **kwargs):

        LOG.info(f"{self.__class__.__name__}: Fetching the MobileIron Devices.")

        try:
            """ 
            Get device info from MobileIron Connector.
            """
            api_version = self.settings['api_version']
            if api_version == '2':
                devices, has_more, limit, offset, spaces, is_spaces_collected = self.mobileiron_connector.load_shim_records(self.settings)
                self.write({"devices": devices, "hasMore": has_more, "limit": limit, "offset": offset, "spaces": spaces, "is_spaces_collected": is_spaces_collected })
            elif api_version == '1':
                devices, partition_ids, is_partition_collected, start, total_count, now = self.mobileiron_connector.load_shim_records_v1(self.settings)
                self.write({"devices": devices, "partition_ids": partition_ids, "is_partition_collected": is_partition_collected,  "start": start, "total_count": total_count, "now": now})
        except RequestException as req_err:
            self.return_http_error(req_err.response.status_code, str(req_err))

class DellAssetOrderStatus(DefaultShimHandler):

    settings = {}

    def initialize(self):
        self.settings = response_to_object(self.request.body)
        self.settings['Authorization'] = self.request.headers.get('Authorization')
        self.dell_connector = dell_asset_order_status.Connector(SECTION, self.settings)

    def post(self, *args, **kwargs):

        LOG.info(f"{self.__class__.__name__}: Fetching the Dell Devices with Order Status.")
        try:
            devices, break_early = self.dell_connector.load_shim_records(self.settings)
            self.write({"devices": devices, "break_early": break_early})
        except RequestException as req_err:
            self.return_http_error(req_err.response.status_code, str(req_err))


###############################
# All User list apis are here #
###############################
class TemplateUserLoad(DefaultShimHandler):
    def post(self, *args, **kwargs):
        LOG.info(f"{self.__class__.__name__}: Fetching the <Connector-Name> Users.")
        self.write({"error": "Not Implemented yet"})


##############################
# All Utilizes apis are here #
##############################

class TerminateMe(DefaultShimHandler):
    def get(self, *args, **kwargs):
        LOG.info(f"Received request to terminate the {SERVICE_NAME}")
        exit(0)


class HealthCheck(DefaultShimHandler):
    def get(self, *args, **kwargs):
        LOG.info(f"{SERVICE_NAME} is active")
        self.write({"active": True})


# MAIN Application for the Shim Service.
class Application(tornado.web.Application):
    def __init__(self, handlers):
        settings = {'compress_response': True}
        tornado.web.Application.__init__(self, handlers, **settings)


class ShimService(object):

    def __init__(self):
        self.count = 0

    def make_app(self):
        LOG.info(f"Starting the Shim-Service")
        return Application([

            # Asset Loads
            (r'/api/v1/assets/cisco_meraki_network_devices', CiscoMerakiNetworkAssetLoad),
            (r'/api/v1/assets/mobileiron_devices', MobileIronAssetLoad),
            (r'/api/v1/assets/dell_asset_order_status', DellAssetOrderStatus),

            # User Loads

            # Operational.
            (r"/", DefaultShimHandler),
            # Kill the server (useful if it becomes a zombie process or becomes detached for some reason.
            (r'/api/v1/kill_me', TerminateMe),

            (r'/health_check', HealthCheck),
        ])

    async def main(self):
        app = self.make_app()
        LOG.info(f"Shim-Service listening on {SHIM_PORT}")
        app.listen(SHIM_PORT)
        await asyncio.Event().wait()

    def start_service(self, *args):
        loop = events.new_event_loop()
        events.set_event_loop(loop)
        loop.run_until_complete(self.main())
