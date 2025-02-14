from lib.connector import AssetsConnector
import base64
import arrow


class Connector(AssetsConnector):
    MappingName = "dnac_network_devices"
    Settings = {
        "username": {"order": 1, "example": "", "default": ""},
        "password": {"order": 2, "example": "******", "default": ""},
        "base_url": {"order": 4, "example": "", "default": ""},
        "authorization_settings": {"order": 3, "default": {}},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.api_key = "x-auth-token"
        self.base_url = self.settings.get("base_url", "")
        self.username = self.settings.get("username", "")
        self.password = self.settings.get("password", "")
        self.expires_in = 0
        self.token = ""
        self.authorization_settings = self.settings.get("authorization_settings", {})

    def get_headers(self):
        if round(arrow.utcnow().float_timestamp) > self.expires_in:
            self._refresh_token()
        return {
            self.api_key: self.token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _refresh_token(self):
        url = f"{self.base_url}/dna/system/api/v1/auth/token"

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        if self.username and self.password:
            basic_auth_value = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode("utf-8")
            headers["Authorization"] = f"Basic {basic_auth_value}"
        else:
            headers["Authorization"] = self.authorization_settings.get(
                "Authorization", ""
            )

        response = self.post(url, headers=headers, data={})
        response.raise_for_status()
        self.token = response.json().get("Token", "")
        self.expires_in = round(arrow.utcnow().float_timestamp) + 1800

    def get_network_devices(self, limit: int, offset: int):
        url = f"{self.base_url}/dna/intent/api/v1/network-device?limit={limit}&offset={offset}"
        response = self.get(url, headers=self.get_headers())
        response.raise_for_status()
        return response.json()

    def _load_records(self, options):
        yield from self.load_cloud_records(credential_details=None)

    def load_cloud_records(self, credential_details):
        offset = 1
        limit = 50
        while True:
            devices = self.get_network_devices(limit=limit, offset=offset)
            if not devices["response"]:
                break
            for device in devices["response"]:
                yield device
            offset += limit
