import base64
import logging

import arrow
from lib.connector import AssetsConnector, response_to_object
from typing import Dict, List, Any

logger = logging.getLogger("connectors/insight")


class Connector(AssetsConnector):
    """
    Insight connector
    """
    MappingName = 'insight'
    Settings = {
        'client_id': {'order': 1, 'example': '', 'default': ""},
        'client_key': {'order': 2, 'example': '', 'default': ""},
        'client_secret': {'order': 3, 'example': '******', 'default': ""},
        'order_creation_date_from': {'order': 4, 'example': 'YYYY-MM-DD', 'default': ""},
        'order_creation_date_to': {'order': 5, 'example': 'YYYY-MM-DD', 'default': ""},
        'tracking_data': {'order': 6, 'example': 'X', 'default': ""}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.get_sales_order_status_api = 'https://insight-prod.apigee.net/GetStatus'

        self.access_token = ""
        self.insight_expires_in = 0
        self.client_key = self.settings.get('client_key', '')
        self.client_secret = self.settings.get('client_secret', '')

        self.client_id = self.settings.get('client_id', '')
        self.order_date_from = self.settings.get('order_creation_date_from', '')
        self.order_date_to = self.settings.get('order_creation_date_to', '')
        self.tracking_data = self.settings.get('tracking_data', '')

    def get_headers(self):
        if round(arrow.utcnow().float_timestamp) > self.insight_expires_in:
            self.get_access_token(self.client_key, self.client_secret)
        return {'Accept': 'application/json',
                'Authorization': f'Bearer {self.access_token}'}

    def get_access_token(self, client_key, client_secret):
        # Create the base64 client_id and client_secret token and grab an Access Token
        token = f"{client_key}:{client_secret}"
        base64_token = base64.b64encode(token.encode()).decode()
        token_url = 'https://insight-prod.apigee.net/oauth/client_credential/accesstoken?grant_type=client_credentials'
        basic_auth_headers = {
            'Authorization': 'Basic {0}'.format(base64_token),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        json_response = self.post(token_url, data={},
                                  headers=basic_auth_headers, post_as_json=False)
        dict_response = response_to_object(json_response.text)

        self.access_token = dict_response.get('access_token', '')
        # expires in 1hr according to docs
        self.insight_expires_in = round(arrow.utcnow().float_timestamp) + int(dict_response.get('expires_in', 3599))


    def get_orders(self):
        # The call must have a body to return a 200 response
        body_data = {"MT_Status2Request": {
          "StatusRequest": [
            {
              "ClientID": self.client_id,
              "TrackingData": self.tracking_data,
              "OrderCreationDateFrom": self.order_date_from,
              "OrderCreationDateTo": self.order_date_to
            }
          ]
        }}

        # The GET method does not allow for data so POST is being used here
        response = response_to_object(self.post(self.get_sales_order_status_api, data=body_data).text)
        return response

    @staticmethod
    def attach_order_headers(order_header: List[Dict[str, Any]], final_dict: Dict[str, Any]):
        final_dict.update({key: value for (key, value) in order_header[0].items()})

    @staticmethod
    def attach_order_tracking(order_tracking_info: List[Dict[str, Any]],
                              serial_number: str,
                              final_dict: Dict[str, Any]):
        for tracking in order_tracking_info:
            if 'SerialNumber' in tracking and tracking['SerialNumber'] == serial_number:
                final_dict.update({key: tracking[key] for key in tracking.keys()})

    def attach_order_line_items_and_tracking(self, order_line_items: Dict[str, Any],
                                             order_tracking_info: List[Dict[str, Any]],
                                             final_dict: Dict[str, Any],
                                             ignore_keys: List[str]):

        for order_item in order_line_items['OrderLineItems']:
            final_dict.update({key: value for (key, value) in order_item.items() if key not in ignore_keys})
            if "Delivery" in order_item:
                for delivery in order_item['Delivery']:
                    final_dict.update({key: delivery[key] for key in delivery.keys() if key not in ignore_keys})

                    if "SerialNumbers" in delivery:
                        for serial_number_dict in delivery['SerialNumbers']:
                            serial_number = serial_number_dict['SerialNumber'].strip()
                            final_dict['SerialNumber'] = serial_number

                            self.attach_order_tracking(order_tracking_info, serial_number, final_dict)
                            if 'BillingInformation' in delivery:
                                if len(delivery['BillingInformation']) == 1:
                                    final_dict.update(
                                        {key: value for (key, value) in delivery['BillingInformation'][0].items()})
                                    yield final_dict
                                else:
                                    logger.warning(
                                        "Billing Information not added to dict as only one is expected per item in "
                                        "Order line item.")

    def create_insight_response_dict(self, response):
        for orders in response["StatusOrderResponse"]:

            for order in orders['Order']:
                order_header = order.get('OrderHeader', [])
                order_tracking_info = order.get('Tracking', [])
                ignore_keys = ["Delivery", "SerialNumbers", "BillingInformation"]
                output_dict = {}

                self.attach_order_headers(order_header, output_dict)
                for result in self.attach_order_line_items_and_tracking(order, order_tracking_info, output_dict, ignore_keys):
                    yield result

    def _load_records(self, *a, **kw):
        if not self.client_key or not self.client_secret:
            self.logger.warning("Missing Client Key or Client Secret. Can not run. Exiting.")
            return

        insight_payload = self.get_orders()
        for ready_order_info in self.create_insight_response_dict(insight_payload):
            yield ready_order_info
