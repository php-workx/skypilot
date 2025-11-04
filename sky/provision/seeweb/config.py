"""Configuration for Seeweb provisioning."""

from sky.provision import common


def bootstrap_instances(
        region: str, cluster_name_on_cloud: str,
        config: common.ProvisionConfig) -> common.ProvisionConfig:
    """Bootstrap instances for Seeweb.

    Seeweb doesn't require any special configuration bootstrapping,
    so we just return the config as-is.
    """
    del region, cluster_name_on_cloud  # unused
    return config
