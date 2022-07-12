from __future__ import absolute_import

import os
import logging
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from lib.connector import AssetsConnector
from lib.error import ConfigError
import os
import hvac
import time

LOGGER = logging.getLogger(__name__)  # pylint:disable=invalid-name
# Logs URL: https://<subdomain>.oomnitza.com/api/v3/connector_run_logs/connector_aws_assets/
MAX_RETRY_COUNT = 5
MIN_SLEEP_SECONDS = 5
MAX_SLEEP_SECONDS = 10


def json_validator(value):
    try:
        return json.loads(value)
    except ValueError:
        raise ConfigError('setting is incorrect json expected but %r found' % value)


class Connector(AssetsConnector):
    MappingName = 'AWS_Assets'
    Settings = {
        'access_key_id': {'order': 1, 'example': "ASIA4UEKLXP33M442AUF", 'default': ""},
        'secret_access_key': {'order': 2, 'example': 'ammDVpAi0xry3KIMpemeBGejwmAnzZUrZFc9KXhv',
                              'default': ""},
        'session_token': {'order': 3, 'example': 'FQoGZXIvYXdzEIT//////////', 'default': ""},
        'regions': {'order': 4, 'example': '["us-west-1","us-west-2"]', 'default': '["us-west-1"]',
                    'validator': json_validator},
        # 'sync_field': {'order': 5, 'example': '5A22F8E992574C4099AA16CFE4C092C9'},
        'sync_field': {'order': 5, 'example': 'instance_id'},
        'asset_type': {'order': 6, 'example': "ec2", 'default': "AWS EC2 Instance"},
        'vault_approle_id': {'order': 7, 'example': "3216-654561-654654", 'default': ""},
        'vault_secret_id': {'order': 8, 'example': "sdas51-kvd93-asodiah98-asdoaiushd32",
                            'default': ""},
        'vault_aws_role': {'order': 9, 'example': "AWS-ReadOnly", 'default': ""},
        'vault_addr': {'order': 10, 'example': "https://vault.example.com:8200",
                       'default': ""},
        'account_name': {'order': 11, 'example': "aws-lab", 'default': ""},
    }

    FieldMappings_v3 = {
        "instance_id": {'source': 'InstanceId'},
        "account_name": {'setting': 'account_name'},
        "instance_type": {'source': 'InstanceType'},
        "ami": {'source': 'ImageId'},
        "availability_zone": {'source': 'zone'},
        "vpc_id": {'source': 'VpcId'},
        "operating_system": {'source': 'Platform'},
        "public_ip": {'source': 'PublicIpAddress'},
        "ipv4_address": {'source': 'PrivateIpAddress'},
        "asset_type": {'setting': 'asset_type'},
        "instance_state": {'source': 'state'},
        "region": {'source': 'region'},
        "security_groups": {'source': 'security_groups'},
        "security_group_ids": {'source': 'security_group_ids'},
        # tags
        "instance_name": {'source': 'Name'},
        "owner": {'source': 'Owner'},
        "environment": {'source': 'Environment'},
        "department": {'source': 'Department'},
        "raw_tags": {'source': 'raw_tags', 'converter': 'aws_tags'},

    }

    FieldMappings = FieldMappings_v3
    AWS_CREDS_MAX_RETRY = 5
    AWS_RETRY_DELAY = 2
    RETRY_COUNTER = 0

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        if not self.settings.get('access_key_id') and not self.settings.get(
                'secret_access_key') and not self.authenticate_vault():
            LOGGER.error("Unable to authenticate to Vault and generate AWS creds.")
            raise hvac.v1.exceptions.Unauthorized()
        self._aws_session = self.authenticate()
        self._aws_regions = []

    def __refresh_connection(self):
        self.authenticate_vault()
        self._aws_session = self.authenticate()
        time.sleep(MAX_SLEEP_SECONDS)

    def authenticate(self):
        access_key = self.settings.get('access_key_id', os.environ.get('AWS_ACCESS_KEY_ID'))
        secret_key = self.settings.get('secret_access_key', os.environ.get('AWS_ACCESS_KEY_ID'))
        session_token = self.settings.get('session_token', os.environ.get('AWS_SESSION_TOKEN')),
        if isinstance(session_token, tuple):
            session_token = session_token[0]
        if session_token and not isinstance(session_token, tuple):
            time.sleep(MIN_SLEEP_SECONDS)
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name="us-west-1"
            )
        else:
            time.sleep(MIN_SLEEP_SECONDS)
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="us-west-1"
            )

    def authenticate_vault(self):
        self.vault_mount_point = self.settings.get('vault_aws_role')
        if self.vault_mount_point:
            mount_info = str(self.vault_mount_point).split("/")
            if mount_info and isinstance(mount_info, list):
                self.vault_mount_point = mount_info[0]
                self.vault_role_name = mount_info[2]

        vault_addr = os.environ.get("VAULT_ADDR", self.settings.get("vault_addr"))
        if not vault_addr:
            return False
        self.vault_client = hvac.Client(url=vault_addr)
        vault_token = os.environ.get("VAULT_TOKEN")

        approle_id = None
        secret_id = None
        if not vault_token:
            approle_id = self.settings.get("vault_approle_id",
                                           os.environ.get("OOMNITZA_CONNECTOR_APPROLE"))
            secret_id = self.settings.get("vault_secret_id",
                                          os.environ.get("OOMNITZA_CONENCTOR_SECRET_ID"))

        # Let approle take precedence
        if approle_id and secret_id:
            self.vault_client.auth.approle.login(role_id=approle_id, secret_id=secret_id)
        elif vault_token:
            self.vault_client.token = vault_token
        else:
            # Not able to auth
            return False

        if not self.vault_client.is_authenticated():
            return False

        try:
            aws_creds_response = self.vault_client.secrets.aws.generate_credentials(
                name=self.vault_role_name,
                mount_point=self.vault_mount_point,
                endpoint="sts",
            )
            self.settings['access_key_id'] = aws_creds_response['data']['access_key']
            self.settings['secret_access_key'] = aws_creds_response['data']['secret_key']
            self.settings['session_token'] = aws_creds_response['data']['security_token']
            return True
        except Exception:
            LOGGER.error("Unable to get creds from Vault", exc_info=True)
            return False

    def do_test_connection(self, options):
        ec2 = self._aws_session.client('ec2')
        try:
            self._aws_regions = [region['RegionName'] for region in
                                 ec2.describe_regions()['Regions']]
        except ClientError as e:
            if "would have succeeded" in str(e):
                return True
            else:
                LOGGER.error("Dry run failed unable to connect to AWS.", exc_info=True)
                return False
        except NoCredentialsError:
            LOGGER.error("No AWS creds found")
            return False

        return True

    def __process_regions(self):
        ec2_reservations = []
        for region in self._aws_regions:
            LOGGER.info("Processing region: %s", region)
            try:
                ec2 = self._aws_session.client('ec2', region_name=region)
                ec2_reservations = ec2_reservations + ec2.describe_instances().get(
                    'Reservations', {str(region): "error"}
                )
            except ClientError:
                LOGGER.error("Error getting EC2 data from %s", region)
                LOGGER.info("Attempting to refresh AWS connection...")
                self.__refresh_connection()
                LOGGER.info("Refresh complete, getting EC2 data...")
                ec2 = self._aws_session.client('ec2', region_name=region)
                ec2_reservations = ec2_reservations + ec2.describe_instances().get(
                    'Reservations', {str(region): "error"}
                )
            except Exception:
                LOGGER.error("Unknown error processing region %s", region, exc_info=True)
                continue
        return ec2_reservations

    def __process_ec2_reservations(self, ec2_reservations):
        for ec2_reservation in ec2_reservations:
            ec2_instances = ec2_reservation.get('Instances', [])
            LOGGER.info("Processing instances...")
            for ec2_instance in ec2_instances:
                LOGGER.debug("Processing %s", ec2_instance.get('InstanceId'))
                # TODO: This should be separate
                # Get instance Name tag
                tags = ec2_instance.get('Tags', None)
                if tags:
                    ec2_instance['raw_tags'] = {}
                    for tag_object in tags:
                        ec2_instance[tag_object.get('Key')] = tag_object.get('Value')
                        ec2_instance['raw_tags'][tag_object.get('Key')] = tag_object.get('Value')

                security_groups = ec2_instance.get('SecurityGroups')
                security_groups_names = []
                security_groups_ids = []

                if security_groups:
                    for group in security_groups:
                        security_groups_names.append(group.get('GroupName'))
                        security_groups_ids.append(group.get('GroupId'))

                ec2_instance['security_groups'] = ','.join(security_groups_names)
                ec2_instance['security_group_ids'] = ','.join(security_groups_ids)

                if not ec2_instance.get('InstanceName'):
                    ec2_instance['InstanceName'] = "Unknown"

                # Get State
                state = ec2_instance['State'].get('Name')
                ec2_instance['state'] = state

                # Get Zone
                zone = ec2_instance['Placement'].get('AvailabilityZone')
                ec2_instance['zone'] = zone

                ec2_instance['region'] = zone[:-1]

                yield ec2_instance

    def _load_records(self, options):
        LOGGER.debug("Attempting connection test with %s", options)
        retry_count = 0
        while not self.do_test_connection(options=options) and retry_count <= MAX_RETRY_COUNT:
            LOGGER.error(
                "Unable to connect to AWS. Probably a credentials problem....but I'm going to sleep on it for %s",
                MAX_SLEEP_SECONDS)
            time.sleep(MAX_SLEEP_SECONDS)
            LOGGER.info("Done sleeping let's try this one more time")
            retry_count += 1
        if retry_count >= MAX_RETRY_COUNT:
            raise NoCredentialsError()

        LOGGER.debug("Iterating over EC2 data by region...")
        ec2_reservations = self.__process_regions()

        LOGGER.info("EC2 data fetch complete, processing reservations")
        # self.__process_ec2_reservations(ec2_reservations)
        for ec2_reservation in ec2_reservations:
            ec2_instances = ec2_reservation.get('Instances', [])
            LOGGER.info("Processing instances...")
            for ec2_instance in ec2_instances:
                LOGGER.debug("Processing %s", ec2_instance.get('InstanceId'))
                # TODO: This should be separate
                # Get instance Name tag
                tags = ec2_instance.get('Tags', None)
                if tags:
                    ec2_instance['raw_tags'] = {}
                    for tag_object in tags:
                        ec2_instance[tag_object.get('Key')] = tag_object.get('Value')
                        ec2_instance['raw_tags'][tag_object.get('Key')] = tag_object.get('Value')

                security_groups = ec2_instance.get('SecurityGroups')
                security_groups_names = []
                security_groups_ids = []

                if security_groups:
                    for group in security_groups:
                        security_groups_names.append(group.get('GroupName'))
                        security_groups_ids.append(group.get('GroupId'))

                ec2_instance['security_groups'] = ','.join(security_groups_names)
                ec2_instance['security_group_ids'] = ','.join(security_groups_ids)

                if not ec2_instance.get('InstanceName'):
                    ec2_instance['InstanceName'] = "Unknown"

                # Get State
                state = ec2_instance['State'].get('Name')
                ec2_instance['state'] = state

                # Get Zone
                zone = ec2_instance['Placement'].get('AvailabilityZone')
                ec2_instance['zone'] = zone

                ec2_instance['region'] = zone[:-1]

                yield ec2_instance
