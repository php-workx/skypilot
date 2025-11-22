"""AWS CloudWatch logging agent."""

from typing import Any, Dict, Literal, Optional

import pydantic

from sky.logs.agent import FluentbitAgent
from sky.utils import resources_utils
from sky.utils import yaml_utils

EC2_MD_URL = '"${AWS_EC2_METADATA_SERVICE_ENDPOINT:-http://169.254.169.254/}"'


class _CloudwatchLoggingConfig(pydantic.BaseModel):
    """Configuration for AWS CloudWatch logging agent."""
    region: Optional[str] = None
    credentials_file: Optional[str] = None
    log_group_name: str = 'skypilot-logs'
    log_stream_prefix: str = 'skypilot-'
    auto_create_group: bool = True
    additional_tags: Optional[Dict[str, str]] = None
    apply_to: Optional[Literal['controller_only']] = None

    @pydantic.validator('apply_to')
    @classmethod
    def validate_apply_to(cls, v):
        """Validate apply_to field accepts only 'controller_only' or None."""
        if v is not None and v != 'controller_only':
            raise ValueError(f'Invalid value for \'apply_to\': {v!r}. '
                             'Only \'controller_only\' is supported.')
        return v


class _CloudWatchOutputConfig(pydantic.BaseModel):
    """Auxiliary model for building CloudWatch output config in YAML.

    Ref: https://docs.fluentbit.io/manual/pipeline/outputs/cloudwatch
    """
    name: str = 'cloudwatch_logs'
    match: str = '*'
    region: Optional[str] = None
    log_group_name: Optional[str] = None
    log_stream_prefix: Optional[str] = None
    auto_create_group: bool = True
    additional_tags: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        config = self.model_dump(exclude_none=True)
        if 'auto_create_group' in config:
            config['auto_create_group'] = 'true' if config[
                'auto_create_group'] else 'false'
        return config


class CloudwatchLoggingAgent(FluentbitAgent):
    """AWS CloudWatch logging agent.

    This agent forwards logs from SkyPilot clusters to AWS CloudWatch using
    Fluent Bit. It supports authentication via IAM roles (preferred), AWS
    credentials file, or environment variables.

    Example configuration:
    ```yaml
    logs:
      store: aws
      aws:
        region: us-west-2
        log_group_name: skypilot-logs
        log_stream_prefix: my-cluster-
        auto_create_group: true
        apply_to: controller_only  # Optional: only setup logging on controllers
    ```

    The `apply_to` option accepts 'controller_only' (or None, the default) to
    skip logging setup on replica VMs. This is useful when replicas run on
    external cloud providers (e.g., RunPod, Lambda) that don't have AWS
    credentials, while the controller runs on AWS EC2 with IAM role access.
    Replicas are identified by the presence of the SKYPILOT_SERVE_REPLICA_ID
    environment variable. Any other value will raise a ValueError.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the CloudWatch logging agent.

        Args:
            config: The configuration for the CloudWatch logging agent.
                   See the class docstring for the expected format.
        """
        self.config = _CloudwatchLoggingConfig(**config)
        super().__init__()

    def get_setup_command(self,
                          cluster_name: resources_utils.ClusterName) -> str:
        """Get the command to set up the CloudWatch logging agent.

        Args:
            cluster_name: The name of the cluster.

        Returns:
            The command to set up the CloudWatch logging agent.
        """
        # If apply_to is set to 'controller_only', skip logging setup on
        # replica VMs. Replicas are identified by the presence of the
        # SKYPILOT_SERVE_REPLICA_ID environment variable.
        controller_only_check = ''
        if self.config.apply_to == 'controller_only':
            controller_only_check = (
                'if [ -n "$SKYPILOT_SERVE_REPLICA_ID" ]; then '
                'echo "Skipping CloudWatch logging setup on replica VM '
                '(apply_to=controller_only)"; '
                'exit 0; '
                'fi; ')

        if self.config.credentials_file:
            credential_path = self.config.credentials_file

        # Set AWS credentials and check whether credentials are valid.
        # CloudWatch plugin supports IAM roles, credentials file, and
        # environment variables. We prefer IAM roles when available
        # (on EC2 instances). If credentials file is provided, we use
        # it. Otherwise, we check if credentials are available in
        # the environment.
        pre_cmd = ''
        if self.config.credentials_file:
            pre_cmd = (
                f'export AWS_SHARED_CREDENTIALS_FILE={credential_path}; '
                f'if [ ! -f {credential_path} ]; then '
                f'echo "ERROR: AWS credentials file {credential_path} '
                f'not found. Please check if the file exists and is '
                f'accessible." && exit 1; '
                f'fi; '
                f'if ! grep -q "\\[.*\\]" {credential_path} || '
                f'! grep -q "aws_access_key_id" {credential_path}; then '
                f'echo "ERROR: AWS credentials file {credential_path} is '
                f'invalid. It should contain a profile section '
                f'[profile_name] and aws_access_key_id." && exit 1; '
                f'fi;')
        else:
            # Check if we're running on EC2 with an IAM role or if
            # AWS credentials are available in the environment
            pre_cmd = (
                f'if ! curl -s -m 1 {EC2_MD_URL}'
                'latest/meta-data/iam/security-credentials/ > /dev/null; '
                'then '
                # failed EC2 check, look for env vars
                'if [ -z "$AWS_ACCESS_KEY_ID" ] || '
                '[ -z "$AWS_SECRET_ACCESS_KEY" ]; then '
                'echo "WARNING: AWS CloudWatch logging configuration error. '
                'Not running on EC2 with IAM role and AWS credentials not '
                'found in environment. Skipping CloudWatch logging setup. '
                'Please do one of the following: '
                '1. Run on an EC2 instance with an IAM role that has '
                'CloudWatch permissions, 2. Set AWS_ACCESS_KEY_ID and '
                'AWS_SECRET_ACCESS_KEY environment variables, or '
                '3. Provide a credentials file via logs.aws.credentials_file '
                'in SkyPilot config."; exit 0; '
                'fi; '
                'fi;')

        # If region is specified, set it in the environment
        if self.config.region:
            pre_cmd += (f' export AWS_REGION={self.config.region}'
                        f' AWS_DEFAULT_REGION={self.config.region};'
                        ' command -v aws &>/dev/null && '
                        f'aws configure set region {self.config.region};')
        else:
            # If region is not specified, check if it's available in
            # the environment or credentials file
            pre_cmd += (
                ' if [ -z "$AWS_REGION" ] && '
                '[ -z "$AWS_DEFAULT_REGION" ]; then '
                'echo "WARNING: AWS region not specified in configuration or '
                'environment. CloudWatch logging may fail if the region '
                'cannot be determined. Consider setting logs.aws.region in '
                'SkyPilot config."; '
                'fi; ')

        # Add a test command to verify AWS credentials work with CloudWatch
        pre_cmd += (
            ' echo "Verifying AWS CloudWatch access..."; '
            'if command -v aws > /dev/null; then '
            'aws cloudwatch list-metrics --namespace AWS/Logs --max-items 1 '
            '> /dev/null 2>&1 || '
            '{ echo "WARNING: Failed to access AWS CloudWatch. Please check '
            'your credentials and permissions."; '
            'echo "The IAM role or user must have cloudwatch:ListMetrics '
            'and logs:* permissions."; '
            'echo "Skipping CloudWatch logging setup."; '
            'exit 0; }; '
            'else echo "AWS CLI not installed, skipping CloudWatch access '
            'verification."; '
            'fi; ')

        return (controller_only_check + pre_cmd + ' ' +
                super().get_setup_command(cluster_name))

    def fluentbit_config(self,
                         cluster_name: resources_utils.ClusterName) -> str:
        """Get the Fluent Bit configuration for CloudWatch.

        This overrides the base method to add a fallback output for local file
        logging in case CloudWatch logging fails.

        Args:
            cluster_name: The name of the cluster.

        Returns:
            The Fluent Bit configuration as a YAML string.
        """
        cfg_dict = yaml_utils.read_yaml_str(
            super().fluentbit_config(cluster_name))
        display_name = cluster_name.display_name
        unique_name = cluster_name.name_on_cloud
        # Build tags for the log stream
        tags = {
            'skypilot.cluster_name': display_name,
            'skypilot.cluster_id': unique_name,
        }

        # Add additional tags if provided
        if self.config.additional_tags:
            tags.update(self.config.additional_tags)

        log_processors = []
        for key, value in tags.items():
            log_processors.append({
                'name': 'content_modifier',
                'action': 'upsert',
                'key': key,
                'value': value
            })

        # Add log processors to config
        processors_config = cfg_dict['pipeline']['inputs'][0].get(
            'processors', {})
        processors_logs_config = processors_config.get('logs', [])
        processors_logs_config.extend(log_processors)
        processors_config['logs'] = processors_logs_config
        cfg_dict['pipeline']['inputs'][0]['processors'] = processors_config

        return yaml_utils.dump_yaml_str(cfg_dict)

    def fluentbit_output_config(
            self, cluster_name: resources_utils.ClusterName) -> Dict[str, Any]:
        """Get the Fluent Bit output configuration for CloudWatch.

        Args:
            cluster_name: The name of the cluster.

        Returns:
            The Fluent Bit output configuration for CloudWatch.
        """
        unique_name = cluster_name.name_on_cloud

        # Format the log stream name to include cluster information
        # This helps with identifying logs in CloudWatch
        log_stream_prefix = f'{self.config.log_stream_prefix}{unique_name}-'

        # Create the CloudWatch output configuration with error handling options
        return _CloudWatchOutputConfig(
            region=self.config.region,
            log_group_name=self.config.log_group_name,
            log_stream_prefix=log_stream_prefix,
            auto_create_group=self.config.auto_create_group,
        ).to_dict()

    def get_credential_file_mounts(self) -> Dict[str, str]:
        """Get the credential file mounts for the CloudWatch logging agent.

        Returns:
            A dictionary mapping local credential file paths to remote paths.
        """
        if self.config.credentials_file:
            return {self.config.credentials_file: self.config.credentials_file}
        return {}
