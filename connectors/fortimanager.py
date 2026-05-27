import json
from typing import Optional
from lib.connector import AssetsConnector


class Connector(AssetsConnector):
    MappingName = "Fortimanager"
    Settings = {
        "url": {"order": 1, "example": "https://fmg_ip/jsonrpc", "default": ""},
        "user": {"order": 2, "example": "***", "default": ""},
        "password": {"order": 3, "example": "***", "default": ""},
        "filter_fields": {"order": 4, "example": ["name", "sn", "oid"], "default": []},
    }

    FieldMappings = {}

    @staticmethod
    def parse_filter_fields(filter_input) -> list:
        """Standardize filter_fields into a list of strings."""
        if not filter_input:
            return []

        if isinstance(filter_input, list):
            return filter_input

        if isinstance(filter_input, str):
            filter_input = filter_input.strip()
            if filter_input.startswith("["):
                try:
                    parsed = json.loads(filter_input)
                    if isinstance(parsed, list):
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass
            raise ValueError(f"Invalid filter_fields format: {filter_input}")
        raise ValueError(
            f"Invalid filter_fields format: Unsupported type {type(filter_input).__name__}"
        )

    def __init__(self, section, settings) -> None:
        super().__init__(section, settings)
        self.url = self.settings.get("url", "").strip("/")
        if "/jsonrpc" not in self.url:
            self.url += "/jsonrpc"
        self.user = self.settings.get("user", "")
        self.password = self.settings.get("password", "")

        raw_filter = self.settings.get("filter_fields", [])
        self.filter_fields = self.parse_filter_fields(raw_filter)

        self.session_token = ""
        if _input_from_cloud := settings.get("inputs_from_cloud", {}):
            self.url = _input_from_cloud.get("url", {}).get("value", "")

    def get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
        }

    def authenticate(self) -> None:
        payload = {
            "id": 1,
            "method": "exec",
            "params": [
                {
                    "data": [
                        {
                            "passwd": self.password,
                            "user": self.user,
                        }
                    ],
                    "url": "/sys/login/user",
                }
            ],
            "session": None,
            "verbose": 1,
        }

        response = self.post(url=self.url, data=payload, headers=self.get_headers())
        data = response.json()
        self.session_token = data.get("session", "")

    def _logout(self) -> None:
        if not self.session_token:
            return

        payload = {
            "id": 1,
            "method": "exec",
            "params": [{"url": "/sys/logout"}],
            "session": self.session_token,
        }

        self.post(url=self.url, data=payload, headers=self.get_headers())
        self.session_token = ""

    def get_devices(self) -> list:
        payload = {
            "method": "get",
            "params": [{"fields": self.filter_fields, "url": "/dvmdb/device"}],
            "session": self.session_token,
            "verbose": 1,
            "id": 1,
        }

        response = self.post(url=self.url, data=payload, headers=self.get_headers())
        results = response.json().get("result", [])

        if not results or not isinstance(results, list):
            self.logger.warning("API returned an empty result list.")
            return []

        first_result = results[0]
        status = first_result.get("status", {})
        status_code = status.get("code")

        if status_code != 0:
            self.logger.error(
                f"Failed to fetch devices. Code: {status_code}, Msg: {status.get('message')}"
            )
            return []

        devices = first_result.get("data", [])
        self.logger.info(f"Successfully fetched {len(devices)} device(s).")
        return devices

    def _load_records(self, options: dict[str, Optional[str]]):
        if not self.user or not self.password:
            self.logger.warning("Missing User and/or Password. Can not run. Exiting")
            return

        self.authenticate()

        try:
            for asset in self.get_devices():
                yield asset
        finally:
            self._logout()

    def load_cloud_records(self, credential_details: dict):
        if not self.url:
            self.logger.warning(
                "Missing FortiManager URL can not proceed. Exiting."
            )
            yield (
                [],
                "Missing or Incorrect Inputs URL, can not proceed. Please change url input.",
            )
        else:
            yield from self._load_records({})
