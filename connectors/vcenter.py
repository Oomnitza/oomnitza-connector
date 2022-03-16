import logging
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from lib.connector import AssetsConnector

logger = logging.getLogger("connectors/vcenter")  # pylint:disable=invalid-name


class Connector(AssetsConnector):
    MappingName = 'vCenter'
    Settings = {
        'url':        {'order': 1, 'default': "https://api_host"},
        'username':   {'order': 2, 'example': "administrator@vsphere.local"},
        'password':   {'order': 3, 'example': "change-me"}
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        
    def _build_url(self, path):
        return self.settings['url'] + path

    def _perform_get(self, url):
        return self.get(url, headers={"vmware-api-session-id": self.session_token})

    def _get_session_token(self):
        resp = self._get_session().post(
            url=self._build_url("/rest/com/vmware/cis/session"),
            auth=(self.settings['username'], self.settings['password']),
            verify=self.get_verification()
        )
        resp.raise_for_status()
        return resp.json()['value']

    def _get_network_interfaces(self):
        resp = self._perform_get(self._build_url(f"/rest/appliance/networking/interfaces"))
        return resp.json()['value']

    def _load_data_centers(self):
        resp = self._perform_get(self._build_url("/rest/vcenter/datacenter"))
        return resp.json()['value']

    def _load_hosts(self, datacenter):
        resp = self._perform_get(self._build_url(f"/rest/vcenter/host?filter.datacenters={datacenter}"))
        return resp.json()['value']

    def _load_vm_list(self, host):
        resp = self._perform_get(self._build_url(f"/rest/vcenter/vm?filter.hosts={host}"))
        return resp.json()['value']

    def _load_vm_detail(self, vm_id):
        resp = self._perform_get(self._build_url(f"/rest/vcenter/vm/{vm_id}"))
        return resp.json()['value']

    def _load_vm_ip(self, mac_address):
        for interface in self.network_interfaces:
            if interface['mac'] == mac_address:
                return interface['ipv4']['address']

    def _load_vm_tools(self, vm_id):
        try:
            resp = self._perform_get(self._build_url(f"/rest/vcenter/vm/{vm_id}/tools"))
            return resp.json()['value']
        except Exception as e:
            return {}

    def _load_guest_identity(self, vm_id):
        # this endpoint returns a 503 if vmware tools is not installed
        try:
            retry_strategy = Retry(
                total=5,
                status_forcelist=[429, 500],
                method_whitelist=["GET"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            http = requests.Session()
            http.mount("https://", adapter)
            http.mount("http://", adapter)

            url = self._build_url(f"/rest/vcenter/vm/{vm_id}/guest/identity")
            headers = {"vmware-api-session-id": self.session_token}
            resp = http.get(url, headers=headers, verify=self.get_verification())
            return {} if resp.status_code != 200 else resp.json()['value']
        except Exception as e:
            return {}

    def _load_records(self, options):
        self.session_token = self._get_session_token()
        self.network_interfaces = self._get_network_interfaces()

        for dc in self._load_data_centers():
            for host in self._load_hosts(dc['datacenter']):
                for vm in self._load_vm_list(host['host']):
                    vm_detail = self._load_vm_detail(vm['vm'])

                    # extend detail record
                    vm_detail['vm'] = vm
                    vm_detail['datacenter'] = dc
                    vm_detail['host'] = host
                    vm_detail['tools'] = self._load_vm_tools(vm['vm'])
                    vm_detail['guest_identity'] = self._load_guest_identity(vm['vm'])

                    if len(vm_detail.get('nics', [])) > 0:
                        # populate NIC ip addresses
                        for nic in vm_detail['nics']:
                            nic_mac = nic['value']['mac_address']
                            nic_ip = self._load_vm_ip(nic_mac)
                            nic['value']['ip_address'] = nic_ip

                        # set record top level mac and ip using first nic
                        vm_detail['mac_address'] = vm_detail['nics'][0]['value']['mac_address']
                        vm_detail['ip_address'] = self._load_vm_ip(vm_detail['mac_address'])
                    else:
                        vm_detail['mac_address'] = None
                        vm_detail['ip_address'] = None

                    yield vm_detail
