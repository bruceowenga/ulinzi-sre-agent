import pytest
from unittest.mock import patch, MagicMock

from agents.triage import triage_agent, TriageResult, _build_prompt
from state import IncidentState


def make_state(**overrides) -> IncidentState:
    base = IncidentState(
        alert_name='HighMemory',
        alert_source='prometheus',
        raw_payload={'value': '0.12'},
        triggered_at='2026-05-26T10:00:00+00:00',
        severity='low',
        probable_cause='',
        affected_services=[],
        confidence=0.0,
        action_taken='',
        playbook=None,
        summary='',
        notified=False,
    )
    base.update(overrides)
    return base


# --- _build_prompt ---

def test_build_prompt_contains_alert_name():
    state = make_state()
    prompt = _build_prompt(state)
    assert 'HighMemory' in prompt


def test_build_prompt_contains_source():
    state = make_state()
    prompt = _build_prompt(state)
    assert 'prometheus' in prompt


# --- TriageResult schema validation ---

def test_triage_result_valid():
    result = TriageResult(
        severity='high',
        probable_cause='Memory usage exceeded threshold due to container leak.',
        affected_services=['grafana'],
        confidence=0.85,
    )
    assert result.severity == 'high'
    assert result.confidence == 0.85


def test_triage_result_rejects_invalid_severity():
    with pytest.raises(Exception):
        TriageResult(
            severity='catastrophic',
            probable_cause='Something bad.',
            affected_services=[],
            confidence=0.9,
        )


def test_triage_result_rejects_confidence_out_of_range():
    with pytest.raises(Exception):
        TriageResult(
            severity='low',
            probable_cause='Minor issue.',
            affected_services=[],
            confidence=1.5,
        )


def test_triage_result_rejects_long_probable_cause():
    with pytest.raises(Exception):
        TriageResult(
            severity='low',
            probable_cause='x' * 121,
            affected_services=[],
            confidence=0.8,
        )


# --- triage_agent ---

@patch('agents.triage._call_llm')
def test_triage_agent_returns_correct_keys(mock_llm):
    mock_llm.return_value = TriageResult(
        severity='high',
        probable_cause='Memory pressure from grafana container.',
        affected_services=['grafana'],
        confidence=0.9,
    )
    result = triage_agent(make_state())
    assert set(result.keys()) == {'severity', 'probable_cause', 'affected_services',
'confidence'}


@patch('agents.triage._call_llm')
def test_triage_agent_uses_primary_model_when_confident(mock_llm):
    mock_llm.return_value = TriageResult(
        severity='medium',
        probable_cause='Disk usage approaching limit.',
        affected_services=[],
        confidence=0.8,
    )
    triage_agent(make_state())
    mock_llm.assert_called_once()


@patch('agents.triage._call_llm')
def test_triage_agent_falls_back_when_low_confidence(mock_llm):
    low_confidence = TriageResult(
        severity='low',
        probable_cause='Unknown issue.',
        affected_services=[],
        confidence=0.4,
    )
    high_confidence = TriageResult(
        severity='high',
        probable_cause='Memory leak in grafana container.',
        affected_services=['grafana'],
        confidence=0.85,
    )
    mock_llm.side_effect = [low_confidence, high_confidence]
    result = triage_agent(make_state())
    assert mock_llm.call_count == 2
    assert result['confidence'] == 0.85