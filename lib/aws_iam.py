import json
import uuid
from typing import List, Iterator
from urllib.parse import unquote
from utils.helper_utils import response_to_object


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

        response = self._managed_connector.perform_api_request(
            logger=self._managed_connector.logger, 
            **api_call_specification
        )
        response_object = response_to_object(response.text)

        return response_object

    def _get_user(self) -> str:
        """
        :response_object:
        <GetUserResponse xmlns="https://iam.amazonaws.com/doc/2010-05-08/">
            <GetUserResult>
                <User>
                    <Path>/</Path>
                    <UserName>ow-34223.cross-account-read-only</UserName>
                    <Arn>arn:aws:iam::376535914443:user/ow-34223.cross-account-read-only</Arn>
                    <UserId>AIDAVPK2KC7FZFEX4SWKW</UserId>
                    <CreateDate>2022-10-24T09:46:59Z</CreateDate>
                </User>
            </GetUserResult>
            <ResponseMetadata>
                <RequestId>c8068156-a61d-4931-959f-ced875abf797</RequestId>
            </ResponseMetadata>
        </GetUserResponse>
        """
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
        """
        :response_object:
        <ListUserPoliciesResponse xmlns="https://iam.amazonaws.com/doc/2010-05-08/">
            <ListUserPoliciesResult>
                <IsTruncated>false</IsTruncated>
                <PolicyNames>
                    <member>AmazonEC2ReadOnlyAccess</member>
                    <member>CrossAccountEC2ReadOnly</member>
                    <member>OomnitzaaOw-34223IAM</member>
                </PolicyNames>
            </ListUserPoliciesResult>
            <ResponseMetadata>
                <RequestId>cae089b0-98a9-4cf0-b391-d4dc2439d762</RequestId>
            </ResponseMetadata>
        </ListUserPoliciesResponse>
        """
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
        policies_list = response_object['ListUserPoliciesResponse']['ListUserPoliciesResult']['PolicyNames']['member']

        # NOTE: PolicyNames can be presented as a list or string
        if not isinstance(policies_list, list):
            policies_list = [policies_list]

        return policies_list

    def _get_user_resources(self, user: str, policy: str) -> List[str]:
        """
        :response_object:
        <GetUserPolicyResponse xmlns="https://iam.amazonaws.com/doc/2010-05-08/">
            <GetUserPolicyResult>
                <PolicyDocument>%7B%0A%20%20%20%20%22Version%22%3A%20%222012-10-17%22%2C%0A%20%20%20%20%22Statement%22%3A%20%5B%0A%20%20%20%20%20%20%20%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Sid%22%3A%20%22MultiAccountsEC2%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Effect%22%3A%20%22Allow%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Action%22%3A%20%22sts%3AAssumeRole%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Resource%22%3A%20%5B%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%22arn%3Aaws%3Aiam%3A%3A884019882798%3Arole%2FCrossAccountEC2ReadOnly%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%22arn%3Aaws%3Aiam%3A%3A819956701132%3Arole%2FCrossAccountEC2ReadOnly%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%22arn%3Aaws%3Aiam%3A%3A159485965151%3Arole%2FCrossAccountEC2ReadOnly%22%0A%20%20%20%20%20%20%20%20%20%20%20%20%5D%0A%20%20%20%20%20%20%20%20%7D%2C%0A%20%20%20%20%20%20%20%20%7B%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Sid%22%3A%20%22TestEC2%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Effect%22%3A%20%22Allow%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Action%22%3A%20%22sts%3AAssumeRole%22%2C%0A%20%20%20%20%20%20%20%20%20%20%20%20%22Resource%22%3A%20%22arn%3Aaws%3Aiam%3A%3A724523256435%3Arole%2FCrossAccountEC2ReadOnly%22%0A%20%20%20%20%20%20%20%20%7D%0A%20%20%20%20%5D%0A%7D</PolicyDocument>
                <PolicyName>CrossAccountEC2ReadOnly</PolicyName>
                <UserName>ow-34223.cross-account-read-only</UserName>
            </GetUserPolicyResult>
            <ResponseMetadata>
                <RequestId>fc295fbc-528d-42c6-bb5f-2a9b370b5722</RequestId>
            </ResponseMetadata>
        </GetUserPolicyResponse>

        :PolicyDocument:
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "MultiAccountsEC2",
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Resource": [
                        "arn:aws:iam::884019882798:role/CrossAccountEC2ReadOnly",
                        "arn:aws:iam::819956701132:role/CrossAccountEC2ReadOnly",
                        "arn:aws:iam::159485965151:role/CrossAccountEC2ReadOnly"
                    ]
                },
                {
                    "Sid": "TestEC2",
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Resource": "arn:aws:iam::724523256435:role/CrossAccountEC2ReadOnly"
                }
            ]
        }
        """
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

        # NOTE: Statement can be presented as a list or dict
        policy_statement = json.loads(unquote(policy_document))['Statement']
        if not isinstance(policy_statement, list):
            policy_statement = [policy_statement]

        # NOTE: Statement can contain entities not related to IAM and Roles Assuming
        policy_statement = [
            statement
            for statement in policy_statement
            if statement['Action'] == 'sts:AssumeRole'
        ]

        statement_resources = []
        for statement in policy_statement:
            if statement['Action'] == 'sts:AssumeRole':
                # NOTE: Resource can be presented as a list or string
                statement_resource = statement['Resource']
                if not isinstance(statement_resource, list):
                    statement_resource = [statement_resource]

                statement_resources.extend(statement_resource)

        return statement_resources

    def _assume_role(self, user_policy: str) -> dict:
        """
        :response_object:
        <AssumeRoleResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
            <AssumeRoleResult>
                <AssumedRoleUser>
                    <AssumedRoleId>AROASKIQ2WNP5N3WZI62Y:AssumeRoleSession1</AssumedRoleId>
                    <Arn>arn:aws:sts::159485965151:assumed-role/CrossAccountEC2ReadOnly/AssumeRoleSession1</Arn>
                </AssumedRoleUser>
                <Credentials>
                    <AccessKeyId>ASIAS************SZ5E</AccessKeyId>
                    <SecretAccessKey>Kaul5Z2SeXl************liZysXiNlLejrYqRo</SecretAccessKey>
                    <SessionToken>FwoGZXIvYXdzEA8aDLrz6J************************************************jTAlKEQaoMbQC7KLfWcaRAEH3B1E=</SessionToken>
                    <Expiration>2022-10-25T14:29:27Z</Expiration>
                </Credentials>
            </AssumeRoleResult>
            <ResponseMetadata>
                <RequestId>afeb812c-************-77f0879da838</RequestId>
            </ResponseMetadata>
        </AssumeRoleResponse>
        """
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

    def get_iam_credentials(self) -> Iterator[dict]:
        policies_list = self._list_user_policies(user=self._user)
        for policy in policies_list:
            resources = self._get_user_resources(user=self._user, policy=policy)
            for resource in resources:
                credentials = self._assume_role(user_policy=resource)
                yield credentials
