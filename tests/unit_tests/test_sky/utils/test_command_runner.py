"""Unit tests for sky.utils.command_runner."""

import os
from unittest import mock

import pytest

from sky.utils import auth_utils
from sky.utils import command_runner
from sky.utils import common_utils


def test_docker_runner_passes_proxy_command_to_inner_hop() -> None:
    """Ensure docker-mode runners reuse user proxy for the host hop."""
    proxy_cmd = 'ssh -W %h:%p jump@host'
    user_hash = common_utils.get_user_hash()
    private_key_path, _, _ = auth_utils.get_ssh_key_and_lock_path(user_hash)

    runner = command_runner.SSHCommandRunner(
        node=('10.0.0.5', 22),
        ssh_user='ubuntu',
        ssh_private_key=os.path.expanduser(private_key_path),
        ssh_proxy_command=proxy_cmd,
        docker_user='container',
        ssh_control_name='unit-test-control',
    )

    # Proxy command should be consumed by the docker bridge, not the outer hop.
    assert runner._ssh_proxy_command is None  # type: ignore[attr-defined]

    # Inner hop must include the user proxy command before targeting the host VM.
    inner_cmd = runner._docker_ssh_proxy_command(
        ['ssh', '-T'])  # type: ignore[attr-defined]
    assert "ProxyCommand='ssh -W 10.0.0.5:22 jump@host'" in inner_cmd
    assert inner_cmd.endswith('ubuntu@10.0.0.5')

    outer_cmd = runner.ssh_base_command(
        ssh_mode=command_runner.SshMode.NON_INTERACTIVE,
        port_forward=None,
        connect_timeout=None,
    )
    assert outer_cmd[-1] == 'container@localhost'


def test_kubernetes_runner_adds_container_flag_to_kubectl_exec() -> None:
    captured = {}

    def fake_run_with_log(command: str, *args, **kwargs):
        captured['command'] = command
        require_outputs = kwargs.get('require_outputs', False)
        if require_outputs:
            return 0, '', ''
        return 0

    with mock.patch.object(command_runner.log_lib,
                           'run_with_log',
                           side_effect=fake_run_with_log):
        runner = command_runner.KubernetesCommandRunner((('ns', 'ctx'), 'pod'),
                                                        container='ray-node')
        runner.run('echo hello', require_outputs=True, stream_logs=False)

    assert 'kubectl exec' in captured['command']
    assert 'pod/pod' in captured['command']
    assert '-c ray-node' in captured['command']


def test_kubernetes_runner_rsync_sets_exec_container_envvar() -> None:
    captured = {}

    def fake_run_with_log(command: str, *args, **kwargs):
        captured['command'] = command
        return 0, '', ''

    with mock.patch.object(command_runner.log_lib,
                           'run_with_log',
                           side_effect=fake_run_with_log):
        runner = command_runner.KubernetesCommandRunner((('ns', 'ctx'), 'pod'),
                                                        container='sidecar0')
        runner.rsync('/tmp/src', '/tmp/dst', up=True, stream_logs=False)

    assert 'SKYPILOT_K8S_EXEC_CONTAINER=sidecar0' in captured['command']
    assert 'rsync' in captured['command']


def test_kubernetes_runner_rsync_does_not_set_exec_container_envvar_by_default(
) -> None:
    captured = {}

    def fake_run_with_log(command: str, *args, **kwargs):
        captured['command'] = command
        return 0, '', ''

    with mock.patch.object(command_runner.log_lib,
                           'run_with_log',
                           side_effect=fake_run_with_log):
        runner = command_runner.KubernetesCommandRunner((('ns', 'ctx'), 'pod'))
        runner.rsync('/tmp/src', '/tmp/dst', up=True, stream_logs=False)

    assert 'SKYPILOT_K8S_EXEC_CONTAINER=' not in captured['command']


def test_get_pod_primary_container_prefers_ray_node() -> None:
    from sky.provision.kubernetes import utils as kubernetes_utils

    sidecar = mock.MagicMock()
    sidecar.name = 'sidecar'
    primary = mock.MagicMock()
    primary.name = 'ray-node'

    pod = mock.MagicMock()
    pod.metadata.name = 'p'
    pod.spec.containers = [sidecar, primary]

    assert kubernetes_utils.get_pod_primary_container(pod) is primary


def test_get_pod_primary_container_falls_back_to_first_container() -> None:
    from sky.provision.kubernetes import utils as kubernetes_utils

    c0 = mock.MagicMock()
    c0.name = 'not-ray-node'
    c1 = mock.MagicMock()
    c1.name = 'also-not-ray-node'

    pod = mock.MagicMock()
    pod.metadata.name = 'p'
    pod.spec.containers = [c0, c1]

    assert kubernetes_utils.get_pod_primary_container(pod) is c0


def test_get_pod_primary_container_raises_on_empty_container_list() -> None:
    from sky.provision.kubernetes import utils as kubernetes_utils

    pod = mock.MagicMock()
    pod.metadata.name = 'p'
    pod.spec.containers = []

    with pytest.raises(ValueError):
        kubernetes_utils.get_pod_primary_container(pod)
