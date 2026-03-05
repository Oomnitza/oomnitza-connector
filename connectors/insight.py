import base64
import logging
import os.path

import arrow
from lib.connector import AssetsConnector
from utils.helper_utils import response_to_object
from typing import Union

logger = logging.getLogger("connectors/insight")


class Connector(AssetsConnector):
    """
    Insight connector
    """
    DEFAULT_LOOKBACK_PERIOD = 20
    MappingName = "insight"
    Settings = {
        "url": {"order": 1, "example": "https://insight-prod.apigee.net example only, please use latest urls.", "default": ""},
        "region": {"order": 2, "example": "NA", "default": "NA"},
        "client_id": {"order": 3, "example": "", "default": ""},
        "client_key": {"order": 4, "example": "", "default": ""},
        "client_secret": {"order": 5, "example": "******", "default": ""},
        "order_creation_date_from": {"order": 6, "example": "YYYY-MM-DD", "default": ""},
        "order_creation_date_to": {"order": 7, "example": "YYYY-MM-DD", "default": arrow.now().format("YYYY-MM-DD")},
        "look_back_period": {"order": 8, "example": "20", "default": "20"},
        "tracking_data": {"order": 9, "example": "X", "default": ""}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.url = self.settings.get("url", "").strip("/")
        self.region = self.settings.get("region", "NA")
        self.look_back_period = self._convert_str_to_int(
            self.settings.get("look_back_period", self.DEFAULT_LOOKBACK_PERIOD), default=self.DEFAULT_LOOKBACK_PERIOD
        )

        self.creds_url = self.url
        self.get_sales_order_status_api = "GetStatus"

        self.access_token = ""
        self.insight_expires_in = 0
        self.client_key = self.settings.get("client_key", "")
        self.client_secret = self.settings.get("client_secret", "")

        self.client_id = self.settings.get("client_id", "")
        self.order_date_from = self.settings.get("order_creation_date_from", "")
        self.order_date_to = self.settings.get("order_creation_date_to", arrow.now().format("YYYY-MM-DD"))
        self.tracking_data = self.settings.get("tracking_data") or "X"

    def _convert_str_to_int(self, value:str , default: int = 0) -> int:
        try:
            return int(value)
        except ValueError:
            self.logger.warning(f"Value is not an number, returning default: {default}")
            return default

    def get_headers(self) -> dict:
        if round(arrow.utcnow().float_timestamp) > self.insight_expires_in:
            self.get_access_token(self.client_key, self.client_secret)
        return {"Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}"}

    def get_access_token(self, client_key: str, client_secret: str) -> None:
        # Create the base64 client_id and client_secret token and grab an Access Token
        token = f"{client_key}:{client_secret}"
        base64_token = base64.b64encode(token.encode()).decode()
        token_url = f"{self.creds_url}/oauth/token?grant_type=client_credentials"
        basic_auth_headers = {
            "Authorization": f"Basic {base64_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        json_response = self.post(token_url, data={}, headers=basic_auth_headers, post_as_json=False)
        dict_response = response_to_object(json_response.text)

        self.access_token = dict_response.get("access_token", "")
        # expires in 1hr according to docs
        self.insight_expires_in = round(arrow.utcnow().float_timestamp) + int(dict_response.get("expires_in", 3599))

    @staticmethod
    def generate_dates_range(start: str, end: str, interval: int) -> list[str]:
        start = arrow.get(start)
        end = arrow.get(end)

        dates_range = []
        date_from, date_to = start, start
        while date_to < end:
            date_to = date_from.shift(days=interval)
            if date_to > end:
                date_to = end
            dates_range.append((date_from.format("YYYY-MM-DD"), date_to.format("YYYY-MM-DD")))
            date_from = date_to

        return dates_range

    def get_orders(self):
        # The Insight API allows a maximum range of 180 days, so we need to paginate on the main date range.
        # The Insight API is also very slow, so we chose an interval of 60 days therefore we're sure to get a response.
        if self.order_date_from:
            dates_range = self.generate_dates_range(self.order_date_from, self.order_date_to, 60)
        else:
            start_timestamp = arrow.utcnow().shift(days=-self.look_back_period).timestamp
            dates_range = self.generate_dates_range(start_timestamp, self.order_date_to, 60)
            self.logger.info(f"... LookBack Period set to: {self.look_back_period}")

        self.logger.info(f"... following date ranges will be tried (from_date, to_date): [{dates_range}]")

        for date_from, date_to in dates_range:
            # The call must have a body to return a 200 response
            body_data = {"MT_Status2Request": {
                "StatusRequest": [
                    {
                        "ClientID": self.client_id,
                        "TrackingData": self.tracking_data,
                        "OrderCreationDateFrom": date_from,
                        "OrderCreationDateTo": date_to
                    }
                ]
            }}

            # The GET method does not bring back data so POST is being used here
            response = response_to_object(
                self.post(os.path.join(self.url, self.region, self.get_sales_order_status_api), data=body_data).text
            )
            yield response

    # @staticmethod
    def attach_order_tracking(self, order_tracking_info: list[dict], serial_number: str, final_dict: dict) -> None:
        for tracking in order_tracking_info:
            if "SerialNumber" in tracking.keys() and str(tracking["SerialNumber"]).strip() == str(serial_number).strip():
                final_dict["Tracking"] = {key: value for key, value in tracking.items()}

    def get_dict_items_excluding_ignore_keys(self, item_list: dict, ignore_keys: list[str]) -> dict:
        return {key: value for (key, value) in item_list.items() if key not in ignore_keys}

    def extract_field_value(self, dict_item: dict, field_name: str) -> Union[str, int]:
        """ Returns the field name's value in the dict, if the field name exists in the dict.
            Returns an empty string if the value is not a str or int, or does not exist.
        """
        if not field_name in dict_item.keys():
            self.logger.info(f"Field name '{field_name}' does not exist in dict keys {dict_item.keys()}")
            return ""

        if isinstance(dict_item[field_name], int):
            return dict_item[field_name]
        elif isinstance(dict_item[field_name], str):
            return dict_item[field_name].strip()
        return ""

    def attach_billing_information(self, delivery_item: dict, final_dict: dict) -> None:
        if billing_info := delivery_item.get("BillingInformation", {}):
            if len(billing_info) == 1:
                final_dict["BillingInformation"] = {key: value for (key, value) in billing_info[0].items()}
            else:
                logger.warning( "Billing Information not added, multiple found in Order line item. One expected.")

    def confirm_and_attach_object_specific_data(self, delivery_item: dict, tracking_info: dict, final_dict: dict) -> bool:
        if serial_numbers := delivery_item.get("SerialNumbers", []):
            for serial_number_dict in serial_numbers:
                serial_number = self.extract_field_value(serial_number_dict, "SerialNumber")
                final_dict["SerialNumber"] = serial_number

                self.attach_order_tracking(tracking_info, serial_number, final_dict)
                self.attach_billing_information(delivery_item, final_dict)
                return True
        return False

    def attach_order_line_items_and_tracking(self, order_line_items: dict, order_tracking_info: list[dict],
                                             final_dict: dict, ignore_keys: list) -> None:
        if not order_line_items.get("OrderLineItems", {}):
            self.logger.warning(f"There are no OrderLineItems, terminating inner loop.")
            yield []

        for order_item in order_line_items["OrderLineItems"]:
            final_dict["OrderLineItems"] = self.get_dict_items_excluding_ignore_keys(order_item, ignore_keys)

            if delivery_items := order_item.get("Delivery", []):
                for delivery_item in delivery_items:
                    final_dict["Delivery"] = self.get_dict_items_excluding_ignore_keys(delivery_item, ignore_keys)
                    if self.confirm_and_attach_object_specific_data(delivery_item, order_tracking_info, final_dict):
                        # Yield this record if there was a serial number and then continue processing.
                        yield final_dict

                    # clear fields that might be reused so we don't keep wrong data between records.
                    self.clean_up_object_specific_fields(final_dict)

            # Clear field to avoid dup information
            final_dict["OrderLineItems"] = {}

    def clean_up_object_specific_fields(self, final_dict: dict) -> None:
        final_dict["Tracking"] = {}
        final_dict["SerialNumber"] = ""
        final_dict["Delivery"] = {}
        final_dict["BillingInformation"] = {}

    def create_insight_response_dict(self, dict_response: dict) -> dict:
        self.logger.info("... processing the insight response payload")
        for orders in dict_response["StatusOrderResponse"]:
            for order in orders["Order"]:
                order_header = order.get("OrderHeader", [])
                order_tracking_info = order.get("Tracking", [])
                ignore_keys = ["Delivery", "SerialNumbers", "BillingInformation"]

                # Set up the dict and add the OrderHeaders
                output_dict = {"OrderHeader": order_header[0]}

                if records := self.attach_order_line_items_and_tracking(order, order_tracking_info, output_dict, ignore_keys):
                    for record in records:
                        yield record

    def _load_records(self, *a, **kw) -> dict:
        if not self.client_key or not self.client_secret:
            self.logger.warning("Missing Client Key or Client Secret. Can not run. Exiting.")
            return

        self.logger.info("... fetching records.")
        for payload in self.get_orders():
            for ready_order_info in self.create_insight_response_dict(payload):
                yield ready_order_info
