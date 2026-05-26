import os
import pytest
from unittest.mock import patch, MagicMock

from runbooks.container_oom import restart_container
from runbooks.disk_pressure import prune_docker
from runbooks.log_flood import rotate_logs
from runbooks import get_runbook, REGISTRY


# --- registry ---

def test_registry_has_expected_alerts():
    assert 'ContainerOOM' in REGISTRY
    assert 'ContainerRestartLoop' in REGISTRY
    assert 'HighDisk' in REGISTRY
    assert 'LokiIngestionStopped' in REGISTRY


def test_get_runbook_returns_callable():
    runbook = get_runbook('ContainerOOM')
    assert callable(runbook)


def test_get_runbook_returns_none_for_unknown():
    assert get_runbook('UnknownAlert') is None


# --- container_oom ---

def test_restart_container_dry_run(monkeypatch):
    monkeypatch.setenv('DRY_RUN', 'true')
    result = restart_container('grafana')
    assert 'DRY RUN' in result
    assert 'grafana' in result


def test_restart_container_calls_docker(monkeypatch):
    monkeypatch.setenv('DRY_RUN', 'false')
    mock_container = MagicMock()
    with patch('runbooks.container_oom.docker.from_env') as mock_docker:
        mock_docker.return_value.containers.get.return_value = mock_container
        result = restart_container('grafana')
        mock_container.restart.assert_called_once()
        assert 'grafana' in result


# --- disk_pressure ---

def test_prune_docker_dry_run(monkeypatch):
    monkeypatch.setenv('DRY_RUN', 'true')
    result = prune_docker()
    assert 'DRY RUN' in result


def test_prune_docker_calls_subprocess(monkeypatch):
    monkeypatch.setenv('DRY_RUN', 'false')
    with patch('runbooks.disk_pressure.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(stdout='Deleted: 500MB', stderr='',
returncode=0)
        result = prune_docker()
        mock_run.assert_called_once()
        assert 'Deleted' in result


# --- log_flood ---

def test_rotate_logs_dry_run(monkeypatch):
    monkeypatch.setenv('DRY_RUN', 'true')
    result = rotate_logs('loki')
    assert 'DRY RUN' in result
    assert 'loki' in result


def test_rotate_logs_calls_subprocess(monkeypatch):
    monkeypatch.setenv('DRY_RUN', 'false')
    with patch('runbooks.log_flood.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(stdout='', stderr='', returncode=0)
        result = rotate_logs('loki')
        mock_run.assert_called_once()
        assert 'loki' in result