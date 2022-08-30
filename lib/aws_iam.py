import json
import uuid
from typing import List
from urllib.parse import unquote


class AWSIAM:
    _managed_connector = None

    _credential_id = None
    _user = None

    def __init__(self, managed_connector, credential_id: str):
        self._managed_connector = managed_connector
        self._credential_id = credential_id

        self._user = self._get_user()

    def _get_signature(self, api_call_specification: dict) -> dict:
        signature = self._managed_connector.OomnitzaConnector.get_secret_by_credential_id(
            credential_id=self._credential_id,
            **api_call_specification
        )

        return signature

    def _perform_aws_api_call(self, api_call_specification: dict) -> dict:
        signature = self._get_signature(api_call_specification=api_call_specification)
        api_call_specification['headers'].update(**signature['headers'])
        api_call_specification['params'].update(**signature['params'])

        response = self._managed_connector.perform_api_request(**api_call_specification)
        response_object = self._managed_connector.response_to_object(response.text)

        return response_object

    def _get_user(self) -> str:
        api_call_specification = {
            'raise_error': True,
            'http_method': 'GET',
            'url': 'https://iam.amazonaws.com',
            'body': None,
            'headers': {},
            'params': {
                'Action': 'GetUser',
                'Version': '2010-05-08'
            }
        }

        response_object = self._perform_aws_api_call(api_call_specification=api_call_specification)
        user = response_object['GetUserResponse']['GetUserResult']['User']['UserName']

        return user

    def _list_user_policies(self, user: str) -> List[str]:
        api_call_specification = {
            'raise_error': True,
            'http_method': 'GET',
            'url': 'https://iam.amazonaws.com',
            'body': None,
            'headers': {},
            'params': {
                'Action': 'ListUserPolicies',
                'Version': '2010-05-08',
                'UserName': user
            }
        }

        response_object = self._perform_aws_api_call(api_call_specification=api_call_specification)

        # It's possible to format of PolicyNames
        # 1. two and more policies
        # OrderedDict([('member', ['AssumeRoleOW30369', 'OW30369AccessRole2'])]
        # 2. only one policy
        # OrderedDict([('member', 'AssumeRoleOW30369')]

        policies_list = list(response_object['ListUserPoliciesResponse']['ListUserPoliciesResult']['PolicyNames'].values())

        if policies_list and isinstance(policies_list[0], list):
            policies_list = policies_list[0]

        return policies_list

    def get_policies_list(self) -> List[str]:
        policies_list = self._list_user_policies(user=self._user)
        return policies_list

    def _get_user_policy(self, user: str, policy: str) -> str:
        api_call_specification = {
            'raise_error': True,
            'http_method': 'GET',
            'url': 'https://iam.amazonaws.com',
            'body': None,
            'headers': {},
            'params': {
                'Action': 'GetUserPolicy',
                'Version': '2010-05-08',
                'UserName': user,
                'PolicyName': policy
            }
        }

        response_object = self._perform_aws_api_call(api_call_specification=api_call_specification)

        policy_document = response_object['GetUserPolicyResponse']['GetUserPolicyResult']['PolicyDocument']
        user_policy = json.loads(unquote(policy_document))['Statement']['Resource']

        return user_policy

    def _assume_role(self, user_policy: str) -> dict:
        api_call_specification = {
            'raise_error': True,
            'http_method': 'GET',
            'url': 'https://sts.amazonaws.com',
            'body': None,
            'headers': {},
            'params': {
                'Action': 'AssumeRole',
                'Version': '2011-06-15',
                'RoleArn': user_policy,
                'RoleSessionName': uuid.uuid4().hex
            }
        }

        response_object = self._perform_aws_api_call(api_call_specification=api_call_specification)
        response_role = response_object['AssumeRoleResponse']['AssumeRoleResult']['Credentials']

        role = {
            'access_key': response_role['AccessKeyId'],
            'secret_key': response_role['SecretAccessKey'],
            'session_token': response_role['SessionToken']
        }

        return role

    def get_role_credentials(self, policy: str) -> dict:
        user_policy = self._get_user_policy(user=self._user, policy=policy)
        role = self._assume_role(user_policy=user_policy)
        return role
