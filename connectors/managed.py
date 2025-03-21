import copy
import importlib
import json
import traceback
from typing import Optional, Dict

from constants import TRUE_VALUES
from lib.api_caller import ConfigurableExternalAPICaller
from lib.aws_iam import AWSIAM
from lib.connector import BaseConnector
from utils.helper_utils import response_to_object
from lib.error import ConfigError
from lib.httpadapters import init_mtls_ssl_adapter, SSLAdapter

from requests.exceptions import HTTPError


class Connector(ConfigurableExternalAPICaller, BaseConnector):
    """
    The connector class for the cloud-managed connector.

    The specific of this connector is that its behavior is prescribed by the some external configuration fetched from the Oomnitza
    cloud and initially this connector class does not rely to any of the SaaS API implementation specific
    """
    Settings = {
        # NOTE: it is expected for on-premise installation to set this 2 params to be set in the .ini file
        'saas_authorization': {
            'order': 1,
            'example': {'params': {'api-token': 'saas-api-token'}, 'headers': {'Authorization': 'Bearer Example'}},
            'default': {}
        },
        'oomnitza_authorization': {
            'order': 2,
            'example': 'oomnitza-api-token',
            'default': {}
        },
        'local_inputs': {
            'order': 3,
            'example': {'username': 'username@example.com', 'password': 'ThePassword'},
            'default': {}
        },
        'test_run': {
            'order': 4,
            'example': False,
            'default': False
        },
        'is_custom': {
            'order': 5,
            'example': False,
            'default': False
        },
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

    MAX_ITERATIONS = 1000

    def __init__(self, section, settings):
        self.inputs_from_cloud = settings.pop('inputs', {}) or {}
        self.exploratory_list_behavior = settings.pop('exploratory_list_behavior', {})
        self.pre_list_behavior = settings.pop('pre_list_behavior', {})
        self.list_behavior = settings.pop('list_behavior', {})
        self.detail_behavior = settings.pop('detail_behavior', {})
        self.software_behavior = settings.pop('software_behavior', {})
        self.saas_behavior = settings.pop('saas_behavior', {})
        self.RecordType = settings.pop('type')
        self.MappingName = settings.pop('name')
        self.ConnectorID = settings.pop('id')
        self.BasicConnector = settings.pop('basic_connector', '')
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

    def generate_session_based_secret(self) -> dict:
        """
        Generate the session-based auth settings based on the given inputs, etc
        """
        api_call_specification = self.build_call_specs(self.session_auth_behavior)

        response = self.perform_api_request(
            logger=self.logger,
            **api_call_specification,
        )
        response_headers = response.headers

        response = response_to_object(response.text)

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

    def attach_saas_authorization(self, api_call_specification, iam_credentials: Optional[dict] = None) -> (dict, dict, Optional[SSLAdapter]):
        """
        There can be two options here:
            - there is credential_id string to be used in case of cloud connector setup
            - there is a JSON containing the ready-to-use headers and params in case of on-premise connector setup
        """
        ssl_adapter = None

        if self.session_auth_behavior:
            secret = self.generate_session_based_secret()
        else:
            secret = self.settings['saas_authorization']

        return secret['headers'], secret['params'], ssl_adapter,\
            secret.get('url_attributes', {}), secret.get('body_attributes', {})

    def save_test_response_to_file(self):
        self.logger.info("Getting test response from custom integration")
        api_call_specification = self.build_call_specs(self.list_behavior)

        auth_headers, auth_params, ssl_adapter, url_attributes, body_attributes = self.attach_saas_authorization(api_call_specification)

        if url_attributes or body_attributes:
            self.update_rendering_context(**url_attributes)
            self.update_rendering_context(**body_attributes)
            api_call_specification = self.build_call_specs(self.list_behavior)

        api_call_specification['headers'].update(**auth_headers)
        api_call_specification['params'].update(**auth_params)
        api_call_specification['ssl_adapter'] = ssl_adapter

        response = self.perform_api_request(logger=self.logger, **api_call_specification)
        self.logger.debug(f"..response: {response.text}")

        try:
            self.save_data_locally(response.json(), self.settings['__name__'])
        except json.decoder.JSONDecodeError:
            self.logger.exception(f"Unable to convert response to JSON: {response.text}")
        return response.text

    def render_add_if_controls(self, api_specification, pagination_controls):
        extra_headers = {_['key']: self.render_to_string(_['value']) for _ in pagination_controls.get('headers', [])}
        extra_params = {_['key']: self.render_to_string(_['value']) for _ in pagination_controls.get('params', [])}
        api_specification['headers'].update(**extra_headers)
        api_specification['params'].update(**extra_params)
        return api_specification

    def make_api_request(self, behavior, pagination, break_early, add_if, iam_credentials=None):
        api_call_specification = self.build_call_specs(behavior)

        # NOTE: Check if we have to add the pagination extra things
        if pagination:
            # check the break early condition in case we could fetch the first page and this is the only page we have
            if bool(self.render_to_native(break_early)):
                return [], {}, {}

            if bool(self.render_to_native(add_if)):
                self.render_add_if_controls(api_call_specification, pagination)

        auth_headers, auth_params, ssl_adapter, url_attributes, body_attributes = self.attach_saas_authorization(
            api_call_specification,
            iam_credentials=iam_credentials
        )

        if url_attributes or body_attributes:
            self.update_rendering_context(**url_attributes)
            self.update_rendering_context(**body_attributes)
            api_call_specification = self.build_call_specs(behavior)
            api_call_specification = self.render_add_if_controls(api_call_specification, pagination)

        api_call_specification['headers'].update(**auth_headers)
        api_call_specification['params'].update(**auth_params)
        api_call_specification['ssl_adapter'] = ssl_adapter

        response = self.perform_api_request(logger=self.logger, **api_call_specification)
        return response_to_object(response.text), response.headers, response.links

    def get_exploratory_list_of_items(self, batch_size=100):
        exploratory_list_iteration = 0

        try:
            self.update_rendering_context(
                exploratory_list_iteration=exploratory_list_iteration,
                exploratory_list_response={},
                exploratory_list_response_headers={},
                exploratory_list_response_links={}
            )

            # Pull the controls out, same controls for Exploratory-List, exploratory-List and List calls
            pagination_dict = self.exploratory_list_behavior.get('pagination', {})
            break_early_control = pagination_dict.get('break_early')
            add_if_control = pagination_dict.get('add_if')
            result_control = self.exploratory_list_behavior.get('result')

            while exploratory_list_iteration < self.MAX_ITERATIONS:

                if self.is_run_canceled():
                    break

                exploratory_list_response, headers, links = self.make_api_request(self.exploratory_list_behavior,
                                                                                  pagination_dict,
                                                                                  break_early_control,
                                                                                  add_if_control)

                results = None
                if exploratory_list_response:
                    self.update_rendering_context(
                        exploratory_list_response=exploratory_list_response,
                        exploratory_list_response_headers=headers,
                        exploratory_list_response_links=links
                    )
                    results = self.render_to_native(result_control)

                if not results:
                    # Note: We don't ever want to skip this check as this it the top level list call and if it's empty
                    # there is nothing to do.
                    if exploratory_list_iteration == 0:
                        raise self.ManagedConnectorListGetEmptyInBeginningException()
                    else:
                        break

                for exploratory_list_response_item in results:
                    self.update_rendering_context(
                        exploratory_list_response_item=exploratory_list_response_item,
                    )
                    for batch_results in self.get_pre_list_of_items(batch_size, skip_empty_response=True):
                        yield batch_results

                exploratory_list_iteration += 1
                self.update_rendering_context(
                    exploratory_list_iteration=exploratory_list_iteration
                )
        except self.ManagedConnectorListGetEmptyInBeginningException as exc:
            raise exc
        except Exception as exc:
            self.logger.exception('Failed to fetch the exploratory_list of items')
            if exploratory_list_iteration == 0:
                raise self.ManagedConnectorListGetInBeginningException(error=str(exc))
            else:
                raise self.ManagedConnectorListGetInMiddleException(error=str(exc))

    def get_pre_list_of_items(self, batch_size=100, skip_empty_response: bool = False):
        pre_list_iteration = 0

        try:
            self.update_rendering_context(
                pre_list_iteration=pre_list_iteration,
                pre_list_response={},
                pre_list_response_headers={},
                pre_list_response_links={}
            )

            # Pull the controls out, same controls for Exploratory-List, Pre-List and List calls
            pagination_dict = self.pre_list_behavior.get('pagination', {})
            break_early_control = pagination_dict.get('break_early')
            add_if_control = pagination_dict.get('add_if')
            result_control = self.pre_list_behavior.get('result')

            while pre_list_iteration < self.MAX_ITERATIONS:

                if self.is_run_canceled():
                    break

                pre_list_response, headers, links = self.make_api_request(self.pre_list_behavior, pagination_dict,
                                                                          break_early_control, add_if_control)

                self.update_rendering_context(
                    pre_list_response=pre_list_response,
                    pre_list_response_headers=headers,
                    pre_list_response_links=links
                )
                results = self.render_to_native(result_control)

                if not results:
                    # NOTE: In this case we can have multiple empty results if exploratory_list is used so we should
                    # continue on as other list mat not be empty.
                    if pre_list_iteration == 0 and not skip_empty_response:
                        raise self.ManagedConnectorListGetEmptyInBeginningException()
                    else:
                        break

                for pre_list_response_item in results:
                    self.update_rendering_context(
                        pre_list_response_item=pre_list_response_item,
                    )
                    for batch_results in self.get_list_of_items(batch_size, skip_empty_response=True):
                        yield batch_results

                pre_list_iteration += 1
                self.update_rendering_context(
                    pre_list_iteration=pre_list_iteration
                )

        except self.ManagedConnectorListGetEmptyInBeginningException as exc:
            raise exc
        except Exception as exc:
            self.logger.exception('Failed to fetch the pre_list of items')
            if pre_list_iteration == 0:
                raise self.ManagedConnectorListGetInBeginningException(error=str(exc))
            else:
                raise self.ManagedConnectorListGetInMiddleException(error=str(exc))

    def get_list_of_items(self, batch_size, iam_credentials: dict = None, skip_empty_response: bool = False):
        iteration = 0
        try:
            self.update_rendering_context(
                iteration=iteration,
                list_response={},
                list_response_headers={},
                list_response_links={}
            )

            # Pull the controls out
            pagination_dict     = self.list_behavior.get('pagination', {})
            break_early_control = pagination_dict.get('break_early')
            add_if_control      = pagination_dict.get('add_if')
            result_control      = self.list_behavior.get('result')

            while iteration < self.MAX_ITERATIONS:

                if self.is_run_canceled():
                    break

                list_response, headers, links = self.make_api_request(self.list_behavior, pagination_dict,
                                                                      break_early_control, add_if_control,
                                                                      iam_credentials=iam_credentials)

                results = None
                if list_response:
                    self.update_rendering_context(
                        list_response=list_response,
                        list_response_headers=headers,
                        list_response_links=links
                    )
                    results = self.render_to_native(result_control)

                if not results:
                    # NOTE: In the case of AWS IAM or pre and exploratory lists, we should proceed with all the chunks ignoring empty ones
                    if iteration == 0 and not skip_empty_response:
                        raise self.ManagedConnectorListGetEmptyInBeginningException()
                    else:
                        break

                for batch_results in self.process_records_in_batches(results, batch_size, iam_credentials=iam_credentials):
                    yield batch_results

                iteration += 1
                self.update_rendering_context(
                    iteration=iteration
                )

        except self.ManagedConnectorListGetEmptyInBeginningException as exc:
            raise exc
        except Exception as exc:
            self.logger.exception('Failed to fetch the list of items')
            if iteration == 0:
                raise self.ManagedConnectorListGetInBeginningException(error=str(exc))
            else:
                raise self.ManagedConnectorListGetInMiddleException(error=str(exc))

        if iteration >= self.MAX_ITERATIONS:
            self.logger.exception(f'Failed to fetch the list of items '
                                  f'Connector exceeded processing limit of {self.MAX_ITERATIONS} iterations')
            raise self.ManagedConnectorListMaxIterationException(error='Reached max iterations')

    def process_records_in_batches(self, result, batch_size, iam_credentials=None):
        batch = []
        for i, item in enumerate(result):
            updated_result = self._do_details_and_software_calls(item, iam_credentials=iam_credentials)
            batch.append(updated_result)
            if (i + 1) % batch_size == 0:
                yield batch
                batch = []
        if batch:  # Yield the last batch if it's not empty
            yield batch

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

    def get_detail_of_item(self, list_response_item, iam_credentials: Optional[dict] = None):
        if self.detail_behavior:
            result_control = self.detail_behavior.get('result', '')
            try:
                self.update_rendering_context(
                    list_response_item=list_response_item,
                )

                detail_response_object = self._call_endpoint_for_sub_behavior(self.detail_behavior)
                if result_control:
                    self.update_rendering_context(
                        detail_response=detail_response_object
                    )
                    detail_response_object = self.render_to_native(result_control)

                # We should keep the exploratory_list_response_item, pre_list_response_item and
                # list_response_item as they can contain some useful information.
                if type(detail_response_object) is dict:
                    detail_response_object['list_response_item'] = list_response_item
                    detail_response_object['pre_list_response_item'] = self.get_arg_from_rendering_context("pre_list_response_item")
                    detail_response_object['exploratory_list_response_item'] = self.get_arg_from_rendering_context("exploratory_list_response_item")

                return detail_response_object
            except Exception as exc:
                self.logger.exception('Failed to fetch the details of item')
                raise self.ManagedConnectorDetailsGetException(error=str(exc))
        else:
            # There is no details call so save the pre_list_response_item and exploratory_list_response_item to the response_item.
            if type(list_response_item) is dict:
                list_response_item['pre_list_response_item'] = self.get_arg_from_rendering_context("pre_list_response_item")
                list_response_item['exploratory_list_response_item'] = self.get_arg_from_rendering_context("exploratory_list_response_item")
            return list_response_item

    def get_cloud_inputs(self) -> Dict:
        secure_inputs = {}

        inputs_from_cloud = {}
        for key, cloud_input in self.inputs_from_cloud.items():
            secret_id = cloud_input.get("secret_id")
            value = secure_inputs.get(secret_id, cloud_input.get("value"))
            inputs_from_cloud[key] = self.render_to_string(value)

        return inputs_from_cloud

    def get_local_inputs(self) -> Dict:
        if isinstance(self.settings.get("local_inputs"), str):
            inputs_from_local = json.loads(self.settings["local_inputs"])
        elif isinstance(self.settings.get("local_inputs"), dict):
            inputs_from_local = self.settings["local_inputs"]
        else:
            raise ConfigError(f'Managed connector #{self.ConnectorID}: local inputs have invalid format. Exiting')
        return inputs_from_local

    def _do_details_and_software_calls(self, list_response_item, iam_credentials: Optional[dict] = None):
        try:
            item_details = self.get_detail_of_item(list_response_item, iam_credentials=iam_credentials)
            self._add_desktop_software(item_details, iam_credentials=iam_credentials)
            self._add_saas_information(item_details)
        except (
                self.ManagedConnectorSoftwareGetException,
                self.ManagedConnectorDetailsGetException,
                self.ManagedConnectorSaaSGetException
        ) as e:
            return list_response_item, str(e)
        else:
            return item_details

    def _load_list(self, batch_size, iam_credentials: dict = None, skip_empty_response: bool = False):
        # NOTE: There are no Exploratory list, Pre List, Details and Software Behaviours for AWS Connectors
        # So special IAM adjustments are not required
        self.logger.debug(f"Loading Managed Records with: exploratory list:{bool(self.exploratory_list_behavior)},"
                          f"pre-list: {bool(self.pre_list_behavior)}, list: {bool(self.list_behavior)}")
        if self.exploratory_list_behavior:
            yield from self.get_exploratory_list_of_items(batch_size)
        elif self.pre_list_behavior:
            yield from self.get_pre_list_of_items(batch_size)
        else:
            yield from self.get_list_of_items(batch_size, iam_credentials=iam_credentials, skip_empty_response=skip_empty_response)

    def _load_basic_connector_list(self, connector_settings: dict):
        api_call_specification = self.build_call_specs(self.list_behavior)
        auth_headers, _, _, _, _ = self.attach_saas_authorization(api_call_specification)
        connector_settings['authorization_settings'] = auth_headers
        credential_details = self.get_credential_details(self.BasicConnector)

        try:
            BasicConnector = self.get_basic_connector_object(self.BasicConnector)
            connector_object = BasicConnector(section=self.BasicConnector, settings=connector_settings)
            for data in connector_object.load_cloud_records(credential_details=credential_details):
                yield data
        except Exception as exc:
            self.logger.exception(f"Failed to fetch the list of items from Basic Connector {self.BasicConnector}")
            raise self.ManagedConnectorListGetInBeginningException(error=str(exc))

    def get_basic_connector_object(self, connector_name: str):
        try:
            mod = importlib.import_module(f'connectors.{connector_name}')
            return mod.Connector
        except ImportError:
            self.logger.exception(f"Could not import connector for {connector_name}.")
            raise ConfigError(f"Could not import connector for {connector_name}.")

    def get_credential_details(self, connector_name: str) -> Dict:
        return {}

    def _load_iam_list(self, batch_size):
        iteration = 0
        iam_records = 0

        try:
            credential_id = self.settings['saas_authorization']['credential_id']
            iam = AWSIAM(managed_connector=self, credential_id=credential_id)

            # NOTE: AWS Credentials have a short life-time, so we can't pre-generate them
            for iam_credentials in iam.get_iam_credentials():
                for page in self._load_list(batch_size, iam_credentials=iam_credentials, skip_empty_response=True):
                    yield page

                    iteration += 1
                    iam_records += len(page)

        except Exception as exc:
            if isinstance(exc, HTTPError) and exc.response.status_code == 403:
                self.logger.exception(f'Encountered a 403 Forbidden error while fetching AWS IAM data, '
                                      f'the Integration User must have appropriate permissions: {exc}')
            else:
                self.logger.exception(f'Failed to fetch AWS IAM data: {exc}')
            if iteration == 0:
                raise self.ManagedConnectorListGetInBeginningException(error=str(exc))
            else:
                raise self.ManagedConnectorListGetInMiddleException(error=str(exc))

        # NOTE: We have such functionality as ManagedConnectorListGetEmptyInBeginningException exception
        # So to properly handle it we should analyze AWS IAM Responses. If we have any records there then we shouldn't
        # raise an exception with an empty Response during default AWS Account processing
        skip_empty_response = True if iam_records > 0 else False
        yield from self._load_list(batch_size, skip_empty_response=skip_empty_response)

    def _use_single_mode(self):
        return self._check_iam() or self.BasicConnector

    def _check_iam(self):

        inputs_from_cloud = {
            k: self.render_to_string(v.get('value'))
            for k, v in self.inputs_from_cloud.items()
        }
        inputs_from_local = self.get_local_inputs()
        self.update_rendering_context(
            inputs={
                **inputs_from_cloud,
                **inputs_from_local
            }
        )

        iam_roles = self.inputs_from_cloud.get('iam_roles', {}).get('value')

        if iam_roles:
            return True
        else:
            return False

    def _load_records(self, options):
        """
        Process the given configuration. First try to download the list of records (with the pagination support)

        Then, optionally, if needed, make an extra call to fetch the details of each object using the separate call
        """

        batch_size = options.get("batch_size", 100)
        inputs_from_cloud = self.get_cloud_inputs()
        inputs_from_local = self.get_local_inputs()
        self.update_rendering_context(
            inputs={
                **inputs_from_cloud,
                **inputs_from_local
            }
        )

        # NOTE: The managed sync happen on behalf of a specific user that is defined separately
        oomnitza_access_token = self.get_oomnitza_auth_for_sync()
        self.OomnitzaConnector.settings['api_token'] = oomnitza_access_token
        self.OomnitzaConnector.authenticate()

        try:
            iam_roles = self.inputs_from_cloud.get('iam_roles', {}).get('value')
            if iam_roles:
                yield from self._load_iam_list(batch_size)
            elif self.BasicConnector:
                yield from self._load_basic_connector_list(inputs_from_cloud)
            else:
                yield from self._load_list(batch_size)

        except self.ManagedConnectorListGetInBeginningException as e:
            # this is a very beginning of the iteration, we do not have a started portion yet,
            # So create a new synthetic one with the traceback of the error and exit
            self.OomnitzaConnector.create_synthetic_finalized_failed_portion(
                self.ConnectorID,
                self.gen_portion_id(),
                error=traceback.format_exc(),
                multi_str_input_value=self.get_multi_str_input_value(),
                is_fatal=True,
                test_run=self.settings.get('test_run', False) in TRUE_VALUES
            )
            raise
        except self.ManagedConnectorListGetInMiddleException as e:
            # this is somewhere in the middle of the processing, We have failed to fetch the new items page. So cannot process further. Send an error and stop
            # we are somewhere in the middle of the processing, send the traceback of the error attached to the portion and stop
            self.send_to_oomnitza({}, error=traceback.format_exc(), is_fatal=True)
            self.finalize_processed_portion()
            raise
        except self.ManagedConnectorListGetEmptyInBeginningException:
            self.OomnitzaConnector.create_synthetic_finalized_empty_portion(
                self.ConnectorID,
                self.gen_portion_id(),
                self.get_multi_str_input_value()
            )
            raise
        except self.ManagedConnectorListMaxIterationException as e:
            # This is due to the connector running in excess and either had a faulty break_early or
            # the pagination/list request is getting the same page endlessly.
            self.send_to_oomnitza({}, error=traceback.format_exc(), is_fatal=True)
            self.finalize_processed_portion()
            raise

    def _add_desktop_software(self, item_details, iam_credentials: Optional[dict] = None):
        try:
            if self.software_behavior is not None and self.software_behavior.get('enabled'):
                self.update_rendering_context(detail_response=item_details)
                software_response = self._get_software_response(item_details, iam_credentials=iam_credentials)
                list_of_software = self._build_list_of_software(software_response)
                self._add_list_of_software(item_details, list_of_software)
        except Exception as exc:
            self.logger.exception('Failed to fetch the software info')
            raise self.ManagedConnectorSoftwareGetException(error=str(exc))

    def _get_software_response(self, default_response, iam_credentials: Optional[dict] = None):
        valid_api_spec = self.software_behavior.get('url') and self.software_behavior.get('http_method')
        response = self._call_endpoint_for_sub_behavior(self.software_behavior, iam_credentials=iam_credentials) if valid_api_spec else default_response
        return response

    def _call_endpoint_for_sub_behavior(self, behavior, iam_credentials: Optional[dict] = None):
        api_call_specification = self.build_call_specs(behavior)
        auth_headers, auth_params, ssl_adapter, url_attributes, body_attributes = self.attach_saas_authorization(
            api_call_specification,
            iam_credentials=iam_credentials
        )

        if url_attributes or body_attributes:
            self.update_rendering_context(**url_attributes)
            self.update_rendering_context(**body_attributes)
            api_call_specification = self.build_call_specs(behavior)

        api_call_specification['headers'].update(**auth_headers)
        api_call_specification['params'].update(**auth_params)
        api_call_specification['ssl_adapter'] = ssl_adapter

        response = self.perform_api_request(logger=self.logger, **api_call_specification)
        return response_to_object(response.text)

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
            if isinstance(self.saas_behavior, dict) and self.saas_behavior.get('enabled') and self.saas_behavior.get('sync_key'):
                item_details['saas'] = {
                    'sync_key': self.saas_behavior['sync_key']
                }

                selected_saas_id = self.saas_behavior.get('selected_saas_id')
                if selected_saas_id:
                    item_details['saas']['selected_saas_id'] = selected_saas_id

                saas_name = self.saas_behavior.get('name')
                if saas_name:
                    item_details['saas']['name'] = saas_name

        except Exception as exc:
            self.logger.exception('Failed to fetch the saas info')
            raise self.ManagedConnectorSaaSGetException(error=str(exc))
