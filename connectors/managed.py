import json
import logging
import traceback

import xmltodict

from lib.api_caller import ConfigurableExternalAPICaller
from lib.connector import BaseConnector
from lib.error import ConfigError


logger = logging.getLogger()


class Connector(ConfigurableExternalAPICaller, BaseConnector):
    """
    The connector class for the cloud-managed connector.

    The specific of this connector is that its behavior is prescribed by the some external configuration fetched from the Oomnitza
    cloud and initially this connector class does not rely to any of the SaaS API implementation specific
    """
    Settings = {
        # NOTE: it is expected for on-premise installation to set this 2 params to be set in the .ini file
        'saas_authorization':       {'order': 1, "default": {}},
        'oomnitza_authorization':   {'order': 2, "default": {}},
        'local_inputs':             {'order': 3, "default": {}}
    }

    session_auth_behavior = None
    inputs_from_cloud = None
    list_behavior = None
    detail_behavior = None
    software_behavior = None
    saas_behavior = None
    RecordType = None
    MappingName = None
    ConnectorID = None

    def __init__(self, section, settings):
        self.inputs_from_cloud = settings.pop('inputs', {})
        self.list_behavior = settings.pop('list_behavior', {})
        self.detail_behavior = settings.pop('detail_behavior', {})
        self.software_behavior = settings.pop('software_behavior', {})
        self.saas_behavior = settings.pop('saas_behavior', {})
        self.RecordType = settings.pop('type')
        self.MappingName = settings.pop('name')
        self.ConnectorID = settings.pop('id')
        update_only = settings.pop('update_only')
        insert_only = settings.pop('insert_only')

        super().__init__(section, settings)

        self.settings['update_only'] = update_only
        self.settings['insert_only'] = insert_only
        self.saas_authorization_loader()
        self.oomnitza_authorization_loader()

        if self.software_behavior is not None and self.software_behavior.get('enabled'):
            self.field_mappings['APPLICATIONS'] = {'source': "software"}

        if self.saas_behavior is not None and self.saas_behavior.get('enabled'):
            self.field_mappings['SAAS'] = {'source': "saas"}

    def saas_authorization_loader(self):
        """
        There can be two options here:
        - there is credential_id string to be used in case of cloud connector setup
                {"credential_id": "qwertyuio1234567890", ...}

        - there is a JSON containing the ready-to-use headers and/or params in case of on-premise connector setup
                {"headers": {"Authorization": "Bearer qwertyuio1234567890"}}

        """
        value = self.settings['saas_authorization']
        if isinstance(value, str):
            value = json.loads(value)

        if not isinstance(value, dict):
            raise ConfigError(f'Managed connector #{self.ConnectorID}: Information for the authorization in SaaS must be presented in form of dictionary JSON')

        if isinstance(value.get('credential_id'), str):
            # cloud-based setup with the credential ID
            self.settings['saas_authorization'] = {'credential_id': value['credential_id']}

        elif value.get('type') == 'session':
            # special session-based configuration where the credentials can be generated dynamically locally, so we should not expect the ready headers or params here
            self.settings['saas_authorization'] = {}
            self.session_auth_behavior = value['behavior']

        elif (isinstance(value.get('headers', {}), dict) and value.get('headers')) or (isinstance(value.get('params', {}), dict) and value.get('params')):
            # on-premise setup with ready-to-use headers and params
            self.settings['saas_authorization'] = {
                'headers': value.get('headers', {}),
                'params': value.get('params', {})
            }

        else:
            raise ConfigError(f'Managed connector #{self.ConnectorID}: SaaS authorization format is invalid. Exiting')

    def oomnitza_authorization_loader(self):
        """
        There can be three options here
        - there is API token ID to be used in case of cloud connector setup
                {"token_id": 1234567890}

        - there is API token value as is to be used in on-premise setup
                "qwertyuio1234567890"

        - nothing set, in this case use the same token as it defined for the [oomnitza] section basic setup

        """
        value = self.settings['oomnitza_authorization']
        if isinstance(value, str) and value:
            # on-premise setup, the token explicitly set, nothing to do
            return

        elif not value:
            # on-premise setup, the token not set, pick the same as from the self.OomnitzaConnector
            self.settings['oomnitza_authorization'] = self.OomnitzaConnector.settings['api_token']

        elif isinstance(value, dict) and value.get("token_id"):
            # cloud based setup
            self.settings['oomnitza_authorization'] = {"token_id": value['token_id']}

        else:
            raise ConfigError(f'Managed connector #{self.ConnectorID}: Oomnitza authorization format is invalid. Exiting')

    # noinspection PyBroadException
    @staticmethod
    def response_to_object(response_text):
        """
        Try to represent the response as the native object from the JSON- or XML-based response
        """
        try:
            return json.loads(response_text)
        except:
            try:
                return xmltodict.parse(response_text)
            except:
                return response_text

    def generate_session_based_secret(self) -> dict:
        """
        Generate the session-based auth settings based on the given inputs, etc
        """
        api_call_specification = self.build_call_specs(self.session_auth_behavior)

        response = self.perform_api_request(**api_call_specification)
        response_headers = response.headers

        response = self.response_to_object(response.text)

        self.update_rendering_context(
            response=response,
            response_headers=response_headers
        )

        auth_headers = {
            _["key"]: self.render_to_string(_["value"])
            for _ in self.session_auth_behavior["result"].get("headers", [])
        }
        auth_params = {
            _["key"]: self.render_to_string(_["value"])
            for _ in self.session_auth_behavior["result"].get("params", [])
        }

        # NOTE: remove the response from the global rendering context because
        # it was specific for the session auth flow
        self.clear_rendering_context("response", "response_headers")

        return {
            "headers": auth_headers,
            "params": auth_params
        }

    def attach_saas_authorization(self, api_call_specification) -> (dict, dict):
        """
        There can be two options here:
            - there is credential_id string to be used in case of cloud connector setup
            - there is a JSON containing the ready-to-use headers and params in case of on-premise connector setup
        """
        credential_id = self.settings['saas_authorization'].get('credential_id')
        if credential_id:
            secret = self.OomnitzaConnector.get_secret_by_credential_id(credential_id, **api_call_specification)
        else:
            if self.session_auth_behavior:
                secret = self.generate_session_based_secret()
            else:
                secret = self.settings['saas_authorization']
        return secret['headers'], secret['params']

    def get_list_of_items(self):
        iteration = 0
        try:
            self.update_rendering_context(
                iteration=iteration,
                list_response={},
                list_response_headers={},
                list_response_links={}
            )
            while True:
                api_call_specification = self.build_call_specs(self.list_behavior)

                # check if we have to add the pagination extra things
                pagination_control = self.list_behavior.get('pagination')
                if pagination_control:
                    # check the break early condition in case we could fetch the first page and this is the only page we have
                    break_early = bool(self.render_to_native(pagination_control.get('break_early')))
                    if break_early:
                        break

                    add_pagination_control = bool(self.render_to_native(pagination_control['add_if']))
                    if add_pagination_control:
                        extra_headers = {_['key']: self.render_to_string(_['value']) for _ in pagination_control.get('headers', [])}
                        extra_params = {_['key']: self.render_to_string(_['value']) for _ in pagination_control.get('params', [])}
                        api_call_specification['headers'].update(**extra_headers)
                        api_call_specification['params'].update(**extra_params)

                auth_headers, auth_params = self.attach_saas_authorization(api_call_specification)
                api_call_specification['headers'].update(**auth_headers)
                api_call_specification['params'].update(**auth_params)

                response = self.perform_api_request(**api_call_specification)

                list_response = self.response_to_object(response.text)

                self.update_rendering_context(
                    list_response=list_response,
                    list_response_headers=response.headers,
                    list_response_links=response.links
                )
                result = self.render_to_native(self.list_behavior['result'])
                if not result:
                    break

                for entity in result:
                    yield entity

                iteration += 1
                self.update_rendering_context(
                    iteration=iteration
                )
        except Exception as exc:
            logger.exception('Failed to fetch the list of items')
            if iteration == 0:
                raise self.ManagedConnectorListGetInBeginningException(error=str(exc))
            else:
                raise self.ManagedConnectorListGetInMiddleException(error=str(exc))

    def get_oomnitza_auth_for_sync(self):
        """
        There can be two options here
        - there is API token ID to be used in case of cloud connector setup
        - there is API token value as is to be used in on-premise setup
        """
        if isinstance(self.settings['oomnitza_authorization'], dict):
            access_token = self.OomnitzaConnector.get_token_by_token_id(self.settings['oomnitza_authorization']['token_id'])
        else:
            access_token = self.settings['oomnitza_authorization']

        return access_token

    def get_detail_of_item(self, list_response_item):
        try:
            self.update_rendering_context(
                list_response_item=list_response_item,
            )
            api_call_specification = self.build_call_specs(self.detail_behavior)
            auth_headers, auth_params = self.attach_saas_authorization(api_call_specification)
            api_call_specification['headers'].update(**auth_headers)
            api_call_specification['params'].update(**auth_params)
            response = self.perform_api_request(**api_call_specification)
            return self.response_to_object(response.text)
        except Exception as exc:
            logger.exception('Failed to fetch the details of item')
            raise self.ManagedConnectorDetailsGetException(error=str(exc))

    def get_local_inputs(self) -> dict:
        if isinstance(self.settings.get("local_inputs"), str):
            inputs_from_local = json.loads(self.settings["local_inputs"])
        elif isinstance(self.settings.get("local_inputs"), dict):
            inputs_from_local = self.settings["local_inputs"]
        else:
            raise ConfigError(f'Managed connector #{self.ConnectorID}: local inputs have invalid format. Exiting')
        return inputs_from_local

    def _load_records(self, options):
        """
        Process the given configuration. First try to download the list of records (with the pagination support)

        Then, optionally, if needed, make an extra call to fetch the details of each object using the separate call
        """
        inputs_from_cloud = {k: v.get('value') for k, v in self.inputs_from_cloud.items()}
        inputs_from_local = self.get_local_inputs()
        self.update_rendering_context(
            inputs={
                **inputs_from_cloud,
                **inputs_from_local
            }
        )

        # the managed sync happen on behalf of a specific user that is defined separately
        oomnitza_access_token = self.get_oomnitza_auth_for_sync()
        self.OomnitzaConnector.settings['api_token'] = oomnitza_access_token
        self.OomnitzaConnector.authenticate()

        try:
            for list_response_item in self.get_list_of_items():
                try:
                    if self.detail_behavior:
                        item_details = self.get_detail_of_item(list_response_item)
                    else:
                        item_details = list_response_item

                    self._add_desktop_software(item_details)
                    self._add_saas_information(item_details)
                except (self.ManagedConnectorSoftwareGetException,
                    self.ManagedConnectorDetailsGetException,
                    self.ManagedConnectorSaaSGetException) as e:
                    yield list_response_item, str(e)
                else:
                    yield item_details

        except self.ManagedConnectorListGetInBeginningException as e:
            # this is a very beginning of the iteration, we do not have a started portion yet,
            # So create a new synthetic one with the traceback of the error and exit
            self.OomnitzaConnector.create_synthetic_finalized_failed_portion(
                self.ConnectorID, self.gen_portion_id(), error=traceback.format_exc(), is_fatal=True
            )
            raise
        except self.ManagedConnectorListGetInMiddleException as e:
            # this is somewhere in the middle of the processing, We have failed to fetch the new items page. So cannot process further. Send an error and stop
            # we are somewhere in the middle of the processing, send the traceback of the error attached to the portion and stop
            self.send_to_oomnitza({}, error=traceback.format_exc(), is_fatal=True)
            self.finalize_processed_portion()
            raise

    def _add_desktop_software(self, item_details):
        try:
            if self.software_behavior is not None and self.software_behavior.get('enabled'):
                self.update_rendering_context(detail_response=item_details)
                software_response = self._get_software_response(item_details)
                list_of_software = self._build_list_of_software(software_response)
                self._add_list_of_software(item_details, list_of_software)
        except Exception as exc:
            logger.exception('Failed to fetch the software info')
            raise self.ManagedConnectorSoftwareGetException(error=str(exc))

    def _get_software_response(self, default_response):
        valid_api_spec = self.software_behavior.get('url') and self.software_behavior.get('http_method')
        response = self._call_endpoint_for_software() if valid_api_spec else default_response
        return response

    def _call_endpoint_for_software(self):
        api_call_specification = self.build_call_specs(self.software_behavior)
        auth_headers, auth_params = self.attach_saas_authorization(api_call_specification)
        api_call_specification['headers'].update(**auth_headers)
        api_call_specification['params'].update(**auth_params)
        response = self.perform_api_request(**api_call_specification)
        return self.response_to_object(response.text)

    def _build_list_of_software(self, software_response):
        self.update_rendering_context(
            software_response=software_response
        )

        list_of_software = []

        for item in self.render_to_native(self.software_behavior['result']):
            self.update_rendering_context(
                software_response_item=item
            )
            list_of_software.append({
                'name': self.render_to_native(self.software_behavior['name']),
                'version': self.render_to_string(self.software_behavior['version']) if self.render_to_native(self.software_behavior['version']) is not None else None,
                'path': None
            })

        return list_of_software

    def _add_list_of_software(self, item_details, software_list):
        if software_list:
            item_details['software'] = software_list

    def _add_saas_information(self, item_details):
        try:
            if self.saas_behavior is not None and self.saas_behavior.get('enabled') and self.saas_behavior.get('sync_key'):
                item_details['saas'] = {
                    'sync_key': self.saas_behavior['sync_key']
                }

                saas_name = self.saas_behavior.get('name')
                if saas_name:
                    item_details['saas']['name'] = saas_name

        except Exception as exc:
            logger.exception('Failed to fetch the saas info')
            raise self.ManagedConnectorSaaSGetException(error=str(exc))
