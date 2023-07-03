import logging
import json
import arrow
from lib.connector import AssetsConnector, response_to_object
from requests.exceptions import RequestException
from typing import Dict, List, Any, Tuple

logger = logging.getLogger("connectors/dell_asset_order_status")


class Connector(AssetsConnector):
    """
    Dell Order Status connector
    """
    MappingName = 'dell_asset_order_status'
    Settings = {
        'client_id': {'order': 1, 'example': '', 'default': ""},
        'client_secret': {'order': 2, 'example': '', 'default': ""},
        'is_dp_id': {'order': 3, 'example': 'True', 'default': ""},
        'is_po_numbers': {'order': 4, 'example': 'False', 'default': ""},
        'is_order_no_country_code': {'order': 4, 'example': 'False', 'default': ""},
        'values': {'order': 5, 'example': ['PO123', 'PO432'], 'default': []},
        'country_code': {'order': 6, 'example': ['US', 'EU', 'IN'], 'default': []}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.get_sales_order_status_api = 'https://apigtwb2c.us.dell.com/PROD/order-status/api/search'
        self.access_token = ""
        self.dell_expires_in = 0
        self.client_secret = self.settings.get('client_secret', '')
        self.client_id = self.settings.get('client_id', '')
        self.is_dp_id = self.settings.get('is_dp_id', '') in ['True', True]
        self.is_po_numbers = self.settings.get('is_po_numbers', True) in ['True', True]
        self.is_order_no_country_code = self.settings.get('is_order_no_country_code', '') in ['True', True]
        self.country_code = self.settings.get('country_code', [])
        self.values = self.settings.get('values', [])

    def get_headers(self):
        if self.settings.get('access_token'):
            self.access_token = self.settings.get('access_token')
        elif round(arrow.utcnow().float_timestamp) > self.dell_expires_in:
            self.get_access_token(self.client_id, self.client_secret)

        return {'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'}

    def get_access_token(self, client_key: str, client_secret: str):
        base_url = "https://apigtwb2c.us.dell.com/auth/oauth/v2/token"
        grant_type = "client_credentials"
        url = f"{base_url}?grant_type={grant_type}&client_id={client_key}&client_secret={client_secret}"
        basic_auth_headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        json_response = self.post(url, data={},
                                  headers=basic_auth_headers, post_as_json=False)

        dict_response = response_to_object(json_response.text)
        self.access_token = dict_response.get('access_token', '')
        self.dell_expires_in = round(arrow.utcnow().float_timestamp) + int(dict_response.get('expires_in', 3600))
        self.logger.info("Access token acquired")

    def get_body_data(self) -> Dict[str, List[Dict[str, List[str]]]]:
        search_parameter = []
        values = self.values if isinstance(self.values, list) else json.loads(self.values)
        country_code = self.country_code if isinstance(self.country_code, list) else json.loads(self.country_code)
        if self.is_po_numbers:
            search_parameter.append({
                "key": "po_numbers",
                "values": values
            })
        elif self.is_dp_id:
            search_parameter.append({
                "key": "dp_ids",
                "values": values
            })
        elif self.is_order_no_country_code:
            search_parameter.extend([
                {
                    "key": "order_numbers",
                    "values": values
                },
                {
                    "key": "country_code",
                    "values": country_code
                }
            ])
        body = {
            "searchParameter": search_parameter
        }

        return body

    def get_orders(self) -> Dict[str, Any]:
        body = self.get_body_data()
        response = response_to_object(self.post(self.get_sales_order_status_api, data=body).text)
        self.logger.info("Order details fetched.")
        return response

    @staticmethod
    def attach_list_header_details(order: Dict, final_dict: Dict, ignore_keys: Any):
        final_dict.update({key: value for key, value in order.items() if key not in ignore_keys})

    def process_product_info(self, order: Dict, product_info: Dict, final_dict: Dict) -> List[Dict]:
        results = []
        if 'serviceTags' in product_info:
            self.attach_list_header_details(product_info, final_dict, ignore_keys=['serviceTags'])
            for serial_number in product_info['serviceTags']:
                final_dict['serialnumber'] = serial_number
                # Attach shipping information to final dict from order information.
                if 'shipToInformation' in order:
                    final_dict['shipToInformation'] = order['shipToInformation']
                    # Copy original contents as there may be more than one serial number in an order
                    results.append(final_dict.copy())
        return results

    def attach_dell_order_details(self, dell_orders: Dict, final_dict: Dict, ignore_keys: List) -> List[Dict]:
        results = []
        for order in dell_orders:
            self.attach_list_header_details(order, final_dict, ignore_keys)
            if 'productInfo' in order:
                for product_info in order['productInfo']:
                    results.extend(self.process_product_info(order, product_info, final_dict))
            else:
                logger.warning("No product information available in Dell Orders.")
        return results

    def create_dell_response_dict(self, response) -> List[Dict]:
        results = []
        for order in response["purchaseOrderDetails"]:
            output_dict = {}
            self.attach_list_header_details(order, output_dict, ignore_keys=["dellOrders"])
            order_info = order.get('dellOrders', [])
            ignore_keys = ["productInfo", "trackingInformation", "shipToInformation", "purchaseOrderLines"]
            results.extend(self.attach_dell_order_details(order_info, output_dict, ignore_keys))
        return results

    def _load_records(self, *a, **kw):
        if not self.client_id or not self.client_secret:
            self.logger.warning("Missing Client ID or Client Secret. Can not run. Exiting.")
            return
        try:
            dell_payload = self.get_orders()
        except RequestException as req_err:
            self.logger.warning(f"Failed to fetch order information: {req_err.response.status_code} "
                                f"{req_err.response.text}")
            return
        for ready_order_info in self.create_dell_response_dict(dell_payload):
            yield ready_order_info

    def load_shim_records(self, _settings) -> Tuple[List[Dict], bool]:
        break_early = True
        devices = []
        self.settings['access_token'] = _settings.get('Authorization').split()[-1]
        try:
            dell_payload = self.get_orders()
        except RequestException as req_err:
            self.logger.warning(f"Failed to fetch order information: {req_err.response.status_code}"
                                f"{req_err.response.text}")
            return devices, break_early
        devices = self.create_dell_response_dict(dell_payload)
        return devices, break_early
