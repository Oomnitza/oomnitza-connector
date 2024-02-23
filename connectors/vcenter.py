import requests
from lib import TrueValues
from lib.connector import AssetsConnector
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from copy import deepcopy


class Connector(AssetsConnector):
    """
    The vCenter endpoints moved from '/rest' to '/api' from version 7.0U2 (March 2021)
    Example: network interfaces api doc
    https://developer.vmware.com/apis/vsphere-automation/latest/appliance/api/appliance/networking/interfaces/get/
    """

    MappingName = 'vCenter'
    Settings = {
        'url': {'order': 1, 'default': "https://api_host"},
        'username': {'order': 2, 'example': "administrator@vsphere.local"},
        'password': {'order': 3, 'example': "change-me"},
        'use_legacy_apis': {'order': 4, 'example': 'True', "default": 'True'}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        # Support for deprecated version of vCenter, we construct the appropriate urls are start up
        self.logger.info(f"Using Legacy Apis: {self._is_legacy_api()}")
        if self._is_legacy_api():
            self.api_route = "/rest"
            self.get_session_url = f"{self.api_route}/com/vmware/cis/session"
            self.get_host_datacenters_url = f"{self.api_route}/vcenter/host?filter.datacenters="
            self.get_vm_hosts_url = f"{self.api_route}/vcenter/vm?filter.hosts="
        else:
            self.api_route = "/api"
            self.get_session_url = f"{self.api_route}/session"
            self.get_host_datacenters_url = f"{self.api_route}/vcenter/host?datacenters="
            self.get_vm_hosts_url = f"{self.api_route}/vcenter/vm?hosts="

        self.vm_url = f"{self.api_route}/vcenter/vm"
        self.network_interfaces_url = f"{self.api_route}/appliance/networking/interfaces"
        self.data_center_url = f"{self.api_route}/vcenter/datacenter"

    def _check_response_for_legacy_field(self, resp):
        return resp.json()['value'] if self._is_legacy_api() else resp.json()

    def _is_legacy_api(self):
        return self.settings.get('use_legacy_apis', 'True') in TrueValues

    def _build_url(self, path):
        return f"{self.settings['url']}{path}"

    def _perform_get(self, url):
        return self.get(url, headers={"vmware-api-session-id": self.session_token})

    def _get_session_token(self):
        resp = self._get_session().post(
            url=self._build_url(self.get_session_url),
            auth=(self.settings['username'], self.settings['password']),
            verify=self.get_verification()
        )
        resp.raise_for_status()
        return self._check_response_for_legacy_field(resp)

    def _get_network_interfaces(self):
        resp = self._perform_get(self._build_url(self.network_interfaces_url))
        return self._check_response_for_legacy_field(resp)

    def _load_data_centers(self):
        resp = self._perform_get(self._build_url(self.data_center_url))
        return self._check_response_for_legacy_field(resp)

    def _load_hosts(self, datacenter):
        resp = self._perform_get(self._build_url(f"{self.get_host_datacenters_url}{datacenter}"))
        return self._check_response_for_legacy_field(resp)

    def _load_vm_list(self, host):
        resp = self._perform_get(self._build_url(f"{self.get_vm_hosts_url}{host}"))
        return self._check_response_for_legacy_field(resp)

    def _load_vm_detail(self, vm_id):
        resp = self._perform_get(self._build_url(f"{self.vm_url}/{vm_id}"))
        return self._check_response_for_legacy_field(resp)

    def _load_vm_ip(self, mac_address):
        for interface in self.network_interfaces:
            if interface['mac'] == mac_address:
                return interface['ipv4']['address']

    def _load_vm_tools(self, vm_id):
        try:
            resp = self._perform_get(self._build_url(f"{self.vm_url}/{vm_id}/tools"))
            return self._check_response_for_legacy_field(resp)
        except Exception as e:
            return {}

    def _load_guest_identity(self, vm_id):
        # this endpoint returns a 503 if vmware tools is not installed
        try:
            retry_strategy = Retry(
                total=5,
                status_forcelist=[429, 500],
                allowed_methods=["GET"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            http = requests.Session()
            http.mount("https://", adapter)
            http.mount("http://", adapter)

            url = self._build_url(f"{self.vm_url}/{vm_id}/guest/identity")
            headers = {"vmware-api-session-id": self.session_token}
            self.logger.info("Issuing GET %s", url)

            resp = http.get(url, headers=headers, verify=self.get_verification())
            return {} if resp.status_code != 200 else self._check_response_for_legacy_field(resp)

        except Exception as e:
            return {}

    def _get_nics_from_list(self, vm_detail):
        # populate NIC ip addresses
        for nic in vm_detail['nics']:
            nic_mac = nic['value']['mac_address']
            nic_ip = self._load_vm_ip(nic_mac)
            nic['value']['ip_address'] = nic_ip

        # set record top level mac and ip using first nic
        vm_detail['mac_address'] = vm_detail['nics'][0]['value']['mac_address']
        vm_detail['ip_address'] = self._load_vm_ip(vm_detail['mac_address'])
        return vm_detail

    def _get_nics_from_dict(self, vm_detail):
        # With the latest version on vCenter the nics (and other information) are no longer returned as a list
        # of dicts, with each dict having a key. To make sure we don't break mapping we format the response
        # from the new api to look like the old version.
        nics = deepcopy(vm_detail['nics'])
        vm_detail['nics'] = []
        for key, nic_value in nics.items():
            nic_mac = nic_value['mac_address']
            nic_ip = self._load_vm_ip(nic_mac)
            nic_value['ip_address'] = nic_ip
            nic_value['key'] = key
            vm_detail['nics'].append(nic_value)

        # Assumed set record top level mac and ip using first nic key
        top_level_nic_key = list(nics.keys())[0]
        nic_mac = nics[top_level_nic_key]['mac_address']
        vm_detail['mac_address'] = nic_mac
        vm_detail['ip_address'] = self._load_vm_ip(nic_mac)

        return vm_detail

    def _format_response_for_mapping(self, vm_detail, to_convert):
        # Convert new api format to old so as not to break mappings
        convert_items = deepcopy(vm_detail[to_convert])
        vm_detail[to_convert] = []
        for key, value in convert_items.items():
            vm_detail[to_convert].append({"value": value, "key": key})
        return vm_detail

    def _load_records(self, options):
        self.session_token = self._get_session_token()
        self.network_interfaces = self._get_network_interfaces()

        self.logger.info("Performing vCenter sync")
        for dc in self._load_data_centers():
            for host in self._load_hosts(dc['datacenter']):
                for vm in self._load_vm_list(host['host']):
                    vm_detail = self._load_vm_detail(vm['vm'])

                    # extend detail record
                    vm_detail['vm'] = vm
                    vm_detail['datacenter'] = dc
                    vm_detail['host'] = host
                    vm_detail['tools'] = self._load_vm_tools(vm['vm'])
                    guest_identity = self._load_guest_identity(vm['vm'])

                    # The new api responses for all apis change from list of dicts to dicts of dicts.
                    # In order to be backwards compatible and not break mapping, we convert the new responses
                    # to the old format for mapping.
                    if guest_identity.get("full_name", {}).get("params") and \
                            type(guest_identity["full_name"]["params"]) == dict:
                        guest_identity['full_name'] = self._format_response_for_mapping(
                            guest_identity['full_name'], 'params')
                    vm_detail['guest_identity'] = guest_identity

                    if type(vm_detail.get('nics')) == dict and not self._is_legacy_api():
                        vm_detail = self._format_response_for_mapping(vm_detail, 'serial_ports')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'scsi_adapters')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'sata_adapters')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'parallel_ports')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'nics')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'floppies')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'disks')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'cdroms')
                        vm_detail = self._format_response_for_mapping(vm_detail, 'nvme_adapters')

                    if len(vm_detail.get('nics', [])) > 0:
                        vm_detail = self._get_nics_from_list(vm_detail)
                    else:
                        vm_detail['mac_address'] = None
                        vm_detail['ip_address'] = None

                    yield vm_detail
