import time

import pytest

from sky.serve import autoscalers
from sky.serve import constants as serve_constants
from sky.serve.service_spec import AutoscalingMetricSpec
from sky.serve.service_spec import SkyServiceSpec


def _build_metric_spec(**overrides) -> AutoscalingMetricSpec:
    # Default to 'sum' for gauge, as it's the default for multi-source.
    data = {
        'name': 'concurrent_users',
        'target_per_replica': 5,
        'kind': 'gauge',
        'aggregation': 'sum',
        'window_seconds': 60,
        'stale_after_seconds': 180,
    }
    data.update(overrides)
    return AutoscalingMetricSpec(**data)


def _build_service_spec(metric_spec: AutoscalingMetricSpec,
                        **overrides) -> SkyServiceSpec:
    data = {
        'readiness_path': '/',
        'initial_delay_seconds': serve_constants.DEFAULT_INITIAL_DELAY_SECONDS,
        'readiness_timeout_seconds':
            serve_constants.DEFAULT_READINESS_PROBE_TIMEOUT_SECONDS,
        'min_replicas': 1,
        'max_replicas': 10,
        'autoscaling_metric': metric_spec,
    }
    data.update(overrides)
    return SkyServiceSpec(**data)


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
    spec = SkyServiceSpec.from_yaml_config(config)
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
        SkyServiceSpec.from_yaml_config(config)


def test_external_metric_autoscaler_gauge_single_source():
    # Tests 'max' aggregation for a single source.
    metric_spec = _build_metric_spec(aggregation='max', target_per_replica=5)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    assert isinstance(autoscaler, autoscalers.ExternalMetricAutoscaler)

    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 4,
            'timestamp': now - 5
        },
        {
            'name': 'concurrent_users',
            'value': 11,
            'timestamp': now - 2
        },
    ])
    # With a single (default) source, latest value is 11. Replicas = ceil(11/5) = 3.
    assert autoscaler._calculate_target_num_replicas() == 3


def test_stale_metric_fail_static():
    # Tests that the autoscaler holds the current replica count if metrics are stale.
    metric_spec = _build_metric_spec(stale_after_seconds=10)
    spec = _build_service_spec(metric_spec, min_replicas=1, max_replicas=5)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    autoscaler.target_num_replicas = 3  # Set a current target

    now = time.time()
    autoscaler.collect_external_metrics([{
        'name': 'concurrent_users',
        'value': 100,
        'timestamp': now - 20,
    }])
    # Should keep current replicas (3) due to stale metrics, not scale down.
    assert autoscaler._calculate_target_num_replicas() == 3


def test_external_metric_autoscaler_rate_single_source():
    # Test rate calculation for a single source with a cumulative counter.
    metric_spec = _build_metric_spec(name='interactions',
                                     kind='rate',
                                     target_per_replica=2,
                                     window_seconds=20)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)

    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'interactions',
            'value': 100,
            'timestamp': now - 10
        },
        {
            'name': 'interactions',
            'value': 125,
            'timestamp': now - 5
        },
    ])
    # Rate = (125 - 100) / 5s = 5/s. Replicas = ceil(5 / 2) = 3.
    assert autoscaler._calculate_target_num_replicas() == 3


def test_multi_source_gauge_sum():
    metric_spec = _build_metric_spec(aggregation='sum', target_per_replica=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 25,
            'timestamp': now - 5,
            'source_id': 'proxy1'
        },
        {
            'name': 'concurrent_users',
            'value': 18,
            'timestamp': now - 2,
            'source_id': 'proxy2'
        },
    ])
    # Total value = 25 + 18 = 43. Replicas = ceil(43 / 10) = 5.
    assert autoscaler._calculate_target_num_replicas() == 5


def test_multi_source_gauge_avg():
    metric_spec = _build_metric_spec(aggregation='avg', target_per_replica=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 25,
            'timestamp': now - 5,
            'source_id': 'proxy1'
        },
        {
            'name': 'concurrent_users',
            'value': 15,
            'timestamp': now - 2,
            'source_id': 'proxy2'
        },
    ])
    # Total value = (25 + 15) / 2 = 20. Replicas = ceil(20 / 10) = 2.
    assert autoscaler._calculate_target_num_replicas() == 2


def test_multi_source_rate():
    metric_spec = _build_metric_spec(name='interactions',
                                     kind='rate',
                                     target_per_replica=5)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    now = time.time()
    # Source 1: Rate of (150-100)/10s = 5/s
    autoscaler.collect_external_metrics([
        {
            'name': 'interactions',
            'value': 100,
            'timestamp': now - 10,
            'source_id': 'proxy1'
        },
        {
            'name': 'interactions',
            'value': 150,
            'timestamp': now,
            'source_id': 'proxy1'
        },
    ])
    # Source 2: Rate of (30-10)/5s = 4/s
    autoscaler.collect_external_metrics([
        {
            'name': 'interactions',
            'value': 10,
            'timestamp': now - 5,
            'source_id': 'proxy2'
        },
        {
            'name': 'interactions',
            'value': 30,
            'timestamp': now,
            'source_id': 'proxy2'
        },
    ])
    # Total rate = 5 + 4 = 9. Replicas = ceil(9 / 5) = 2.
    assert autoscaler._calculate_target_num_replicas() == 2


def test_stale_source_expiry():
    metric_spec = _build_metric_spec(aggregation='sum', target_per_replica=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    # Reduce TTL for testing purposes
    autoscaler._metric_window.source_ttl_seconds = 5

    now = time.time()
    # Stale source, should be expired
    autoscaler.collect_external_metrics([{
        'name': 'concurrent_users',
        'value': 100,
        'timestamp': now,
        'source_id': 'stale_proxy'
    }])
    # Active source
    autoscaler.collect_external_metrics([{
        'name': 'concurrent_users',
        'value': 30,
        'timestamp': now,
        'source_id': 'active_proxy'
    }])

    # Simulate a stale source by moving its last update time past the TTL.
    stale_offset = autoscaler._metric_window.source_ttl_seconds + 1
    autoscaler._metric_window.last_updated_at['stale_proxy'] = (now -
                                                                stale_offset)
    autoscaler._metric_window.last_updated_at['active_proxy'] = now
    autoscaler._metric_window.prune(now)

    # Total value should only be from the active proxy (30).
    # Replicas = ceil(30 / 10) = 3.
    assert autoscaler._calculate_target_num_replicas() == 3


def test_legacy_proxy_id_support():
    metric_spec = _build_metric_spec(aggregation='sum', target_per_replica=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 25,
            'timestamp': now - 5,
            'proxy_id': 'legacy_proxy1'
        },
        {
            'name': 'concurrent_users',
            'value': 18,
            'timestamp': now - 2,
            'source_id': 'proxy2'
        },
    ])
    # Total value = 25 + 18 = 43. Replicas = ceil(43 / 10) = 5.
    assert autoscaler._calculate_target_num_replicas() == 5


def test_default_source_id():
    metric_spec = _build_metric_spec(aggregation='sum', target_per_replica=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 25,
            'timestamp': now - 5
        },
        {
            'name': 'concurrent_users',
            'value': 18,
            'timestamp': now - 2
        },
    ])
    # Both metrics go to the 'default' source. The latest value is 18.
    # Replicas = ceil(18 / 10) = 2.
    assert autoscaler._calculate_target_num_replicas() == 2


def test_external_metric_autoscaler_fallback_variant():
    metric_spec = _build_metric_spec()
    spec = _build_service_spec(metric_spec, base_ondemand_fallback_replicas=1)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    assert isinstance(autoscaler, autoscalers.FallbackExternalMetricAutoscaler)


def test_external_metric_autoscaler_out_of_order():
    # Test that out-of-order metrics are handled correctly.
    metric_spec = _build_metric_spec(name='interactions',
                                     kind='rate',
                                     target_per_replica=3,
                                     window_seconds=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)

    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'interactions',
            'value': 150,
            'timestamp': now,
            'source_id': 'proxy1'
        },
        {
            'name': 'interactions',
            'value': 100,
            'timestamp': now - 10,
            'source_id': 'proxy1'
        },
    ])
    # Rate = (150 - 100) / 10s = 5/s. Replicas = ceil(5 / 3) = 2.
    assert autoscaler._calculate_target_num_replicas() == 2


def test_external_metric_autoscaler_pruning_multiple():
    # Test that multiple old metrics are pruned correctly from a single source.
    metric_spec = _build_metric_spec(name='interactions',
                                     kind='rate',
                                     target_per_replica=5,
                                     window_seconds=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)

    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'interactions',
            'value': 100,
            'timestamp': now - 20
        },
        {
            'name': 'interactions',
            'value': 110,
            'timestamp': now - 15
        },
        {
            'name': 'interactions',
            'value': 120,
            'timestamp': now - 8
        },
        {
            'name': 'interactions',
            'value': 150,
            'timestamp': now - 2
        },
    ])
    # Only samples at t-8 and t-2 are in the window.
    # Rate = (150 - 120) / 6s = 5/s. Replicas = ceil(5 / 5) = 1.
    assert autoscaler._calculate_target_num_replicas() == 1


def test_multi_source_gauge_max():
    metric_spec = _build_metric_spec(aggregation='max', target_per_replica=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 25,
            'timestamp': now - 5,
            'source_id': 'proxy1'
        },
        {
            'name': 'concurrent_users',
            'value': 18,
            'timestamp': now - 2,
            'source_id': 'proxy2'
        },
    ])
    # Max value is 25. Replicas = ceil(25 / 10) = 3.
    assert autoscaler._calculate_target_num_replicas() == 3


def test_multi_source_gauge_min():
    metric_spec = _build_metric_spec(aggregation='min', target_per_replica=10)
    spec = _build_service_spec(metric_spec)
    autoscaler = autoscalers.Autoscaler.from_spec('svc', spec)
    now = time.time()
    autoscaler.collect_external_metrics([
        {
            'name': 'concurrent_users',
            'value': 25,
            'timestamp': now - 5,
            'source_id': 'proxy1'
        },
        {
            'name': 'concurrent_users',
            'value': 18,
            'timestamp': now - 2,
            'source_id': 'proxy2'
        },
    ])
    # Min value is 18. Replicas = ceil(18 / 10) = 2.
    assert autoscaler._calculate_target_num_replicas() == 2
