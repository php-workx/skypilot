import dataclasses

from sky.serve import autoscalers
from sky.serve import serve_state
from sky.serve import service_spec


@dataclasses.dataclass(frozen=True)
class _Replica:
    replica_id: int
    version: int
    status: serve_state.ReplicaStatus
    is_ready: bool
    is_terminal: bool


class _DummyAutoscaler(autoscalers.Autoscaler):

    def _calculate_target_num_replicas(self) -> int:
        return 0

    def collect_request_information(self, request_aggregator_info):
        return

    def _generate_scaling_decisions(self, replica_infos):
        return [
            autoscalers.AutoscalerDecision(
                autoscalers.AutoscalerDecisionOperator.SCALE_DOWN, 1),
        ] + [
            autoscalers.AutoscalerDecision(
                autoscalers.AutoscalerDecisionOperator.SCALE_UP, None)
            for _ in range(10)
        ]

    def _dump_dynamic_states(self):
        return {}

    def _load_dynamic_states(self, dynamic_states):
        return


def _set_strict_max_capacity(monkeypatch, enabled: bool) -> None:
    from sky import skypilot_config

    def _mock_get_nested(keys, default_value, override_configs=None):  # pylint: disable=unused-argument
        if tuple(keys) == ('serve', 'strict_max_capacity'):
            return enabled
        return default_value

    monkeypatch.setattr(skypilot_config, 'get_nested', _mock_get_nested)


def test_strict_max_capacity_disabled_allows_scale_up_past_cap(monkeypatch):
    _set_strict_max_capacity(monkeypatch, False)
    spec = service_spec.SkyServiceSpec(
        readiness_path='/health',
        initial_delay_seconds=0,
        readiness_timeout_seconds=1,
        min_replicas=0,
        max_replicas=3,
        target_qps_per_replica=1.0,
    )
    autoscaler = _DummyAutoscaler('svc', spec)
    autoscaler.latest_version_ever_ready = autoscaler.latest_version

    replica_infos = [
        _Replica(1, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
        _Replica(2, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
        _Replica(3, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
    ]
    decisions = autoscaler.generate_scaling_decisions(replica_infos, [])
    operators = [d.operator for d in decisions]
    assert operators.count(
        autoscalers.AutoscalerDecisionOperator.SCALE_DOWN) == 1
    assert operators.count(
        autoscalers.AutoscalerDecisionOperator.SCALE_UP) == 10


def test_hard_max_replicas_drops_scale_ups_at_capacity(monkeypatch):
    _set_strict_max_capacity(monkeypatch, True)
    spec = service_spec.SkyServiceSpec(
        readiness_path='/health',
        initial_delay_seconds=0,
        readiness_timeout_seconds=1,
        min_replicas=0,
        max_replicas=3,
        target_qps_per_replica=1.0,
    )
    autoscaler = _DummyAutoscaler('svc', spec)
    autoscaler.latest_version_ever_ready = autoscaler.latest_version

    replica_infos = [
        _Replica(1, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
        _Replica(2, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
        _Replica(3, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
    ]
    decisions = autoscaler.generate_scaling_decisions(replica_infos, [])

    assert [d.operator for d in decisions
           ] == [autoscalers.AutoscalerDecisionOperator.SCALE_DOWN]


def test_hard_max_replicas_allows_scale_ups_below_capacity(monkeypatch):
    _set_strict_max_capacity(monkeypatch, True)
    spec = service_spec.SkyServiceSpec(
        readiness_path='/health',
        initial_delay_seconds=0,
        readiness_timeout_seconds=1,
        min_replicas=0,
        max_replicas=3,
        target_qps_per_replica=1.0,
    )
    autoscaler = _DummyAutoscaler('svc', spec)
    autoscaler.latest_version_ever_ready = autoscaler.latest_version

    replica_infos = [
        _Replica(1, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
    ]
    decisions = autoscaler.generate_scaling_decisions(replica_infos, [])

    operators = [d.operator for d in decisions]
    assert operators.count(
        autoscalers.AutoscalerDecisionOperator.SCALE_DOWN) == 1
    assert operators.count(autoscalers.AutoscalerDecisionOperator.SCALE_UP) == 2


def test_hard_max_replicas_includes_overprovision(monkeypatch):
    _set_strict_max_capacity(monkeypatch, True)
    spec = service_spec.SkyServiceSpec(
        readiness_path='/health',
        initial_delay_seconds=0,
        readiness_timeout_seconds=1,
        min_replicas=0,
        max_replicas=3,
        num_overprovision=2,
        target_qps_per_replica=1.0,
    )
    autoscaler = _DummyAutoscaler('svc', spec)
    autoscaler.latest_version_ever_ready = autoscaler.latest_version

    replica_infos = [
        _Replica(1, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
        _Replica(2, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
        _Replica(3, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
        _Replica(4, autoscaler.latest_version, serve_state.ReplicaStatus.READY,
                 True, False),
    ]
    decisions = autoscaler.generate_scaling_decisions(replica_infos, [])

    operators = [d.operator for d in decisions]
    assert operators.count(
        autoscalers.AutoscalerDecisionOperator.SCALE_DOWN) == 1
    assert operators.count(autoscalers.AutoscalerDecisionOperator.SCALE_UP) == 1
