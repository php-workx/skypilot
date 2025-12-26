import time

import pytest

from sky.serve import autoscalers
from sky.serve import constants as serve_constants
from sky.serve import service_spec


def _build_metric_spec(**overrides) -> service_spec.AutoscalingMetricSpec:
    data = {
        'name': 'concurrent_users',
        'target_per_replica': 5,
        'kind': 'gauge',
        'aggregation': 'avg',
        'window_seconds': 60,
        'stale_after_seconds': 180,
    }
    data.update(overrides)
    return service_spec.AutoscalingMetricSpec(**data)


def _build_service_spec(metric_spec: service_spec.AutoscalingMetricSpec,
                        **overrides) -> service_spec.SkyServiceSpec:
    data = {
        'readiness_path': '/',
        'initial_delay_seconds': serve_constants.DEFAULT_INITIAL_DELAY_SECONDS,
        'readiness_timeout_seconds':
            serve_constants.DEFAULT_READINESS_PROBE_TIMEOUT_SECONDS,
        'min_replicas': 1,
        'max_replicas': 5,
        'autoscaling_metric': metric_spec,
    }
    data.update(overrides)
    return service_spec.SkyServiceSpec(**data)


def test_service_spec_autoscaling_metric_roundtrip():
    config = {
        'readiness_probe': '/',
        'replica_policy': {
            'min_replicas': 1,
            'max_replicas': 3,
            'autoscaling_metric': {
                'name': 'concurrent_users',
                'target_per_replica': 5,
                'kind': 'GAUGE',
                'aggregation': 'MAX',
                'window_seconds': 60,
                'stale_after_seconds': 180,
            },
        },
    }
    spec = service_spec.SkyServiceSpec.from_yaml_config(config)
    assert spec.autoscaling_metric is not None
    assert spec.autoscaling_metric.kind == 'gauge'
    assert spec.autoscaling_metric.aggregation == 'max'

    yaml_config = spec.to_yaml_config()
    metric_config = yaml_config['replica_policy']['autoscaling_metric']
    assert metric_config['name'] == 'concurrent_users'
    assert metric_config['target_per_replica'] == 5
    assert metric_config['kind'] == 'gauge'
    assert metric_config['aggregation'] == 'max'


def test_service_spec_autoscaling_metric_conflicts_with_qps():
    config = {
        'readiness_probe': '/',
        'replica_policy': {
            'min_replicas': 1,
            'max_replicas': 3,
            'target_qps_per_replica': 2,
            'autoscaling_metric': {
                'name': 'concurrent_users',
                'target_per_replica': 5,
            },
        },
    }
    with pytest.raises(ValueError):
        service_spec.SkyServiceSpec.from_yaml_config(config)


def test_external_metric_autoscaler_gauge_max():
    metric_spec = _build_metric_spec(aggregation='max', target_per_replica=5)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    assert isinstance(autoscaler, autoscalers.ExternalMetricAutoscaler)

    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 4,
            'timestamp': now - 5,
        },
        {
            'name': 'concurrent_users',
            'value': 11,
            'timestamp': now - 2,
        },
    ])
    assert autoscaler._calculate_target_num_replicas() == 3


def test_external_metric_autoscaler_stale_metric():
    metric_spec = _build_metric_spec(stale_after_seconds=1)
    spec = _build_service_spec(metric_spec, min_replicas=1, max_replicas=3)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)

    now = time.time()
    autoscaler.collect_external_metrics([{
        'name': 'concurrent_users',
        'value': 20,
        'timestamp': now - 10,
    }])
    assert autoscaler._calculate_target_num_replicas() == 1


def test_external_metric_autoscaler_rate():
    metric_spec = _build_metric_spec(name='interactions',
                                     kind='rate',
                                     target_per_replica=2,
                                     window_seconds=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)

    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'interactions',
            'value': 25,
            'timestamp': now - 5,
        },
        {
            'name': 'interactions',
            'value': 15,
            'timestamp': now - 1,
        },
    ])
    assert autoscaler._calculate_target_num_replicas() == 2


def test_external_metric_autoscaler_fallback_variant():
    metric_spec = _build_metric_spec()
    spec = _build_service_spec(metric_spec, base_ondemand_fallback_replicas=1)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    assert isinstance(autoscaler, autoscalers.FallbackExternalMetricAutoscaler)
