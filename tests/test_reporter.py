import pytest
import respx
import json
from httpx import Response

from agents.reporter import reporter_agent

INCIDENT = {
    'alert_name':        'ContainerRestartLoop',
    'alert_source':      'prometheus',
    'raw_payload':       {},
    'triggered_at':      '2026-05-26T08:14:32+00:00',
    'severity':          'medium',
    'probable_cause':    'Loki container restarting due to memory pressure.',
    'affected_services': ['loki-loki-1'],
    'confidence':        0.82,
    'action_taken':      'restart_container',
    'playbook':          None,
    'summary':           '',
    'notified':          False,
}


@pytest.mark.asyncio
@respx.mock
async def test_reporter_ntfy_payload():
    ntfy_route     = respx.post('http://localhost:8070').mock(return_value=Response(200))
    loki_route     = respx.post('http://localhost:3100/loki/api/v1/push').mock(return_value=Response(204))
    grafana_route  = respx.post('http://localhost:3000/api/annotations').mock(return_value=Response(200))

    await reporter_agent(INCIDENT)

    assert ntfy_route.called
    body = json.loads(ntfy_route.calls[0].request.content)
    assert body['title'] == '[WARN] ContainerRestartLoop'
    assert body['priority'] == 'default'
    assert 'loki-loki-1' in body['tags']


@pytest.mark.asyncio
@respx.mock
async def test_reporter_loki_payload():
    respx.post('http://localhost:8070').mock(return_value=Response(200))
    loki_route = respx.post('http://localhost:3100/loki/api/v1/push').mock(return_value=Response(204))
    respx.post('http://localhost:3000/api/annotations').mock(return_value=Response(200))

    await reporter_agent(INCIDENT)

    body = json.loads(loki_route.calls[0].request.content)
    stream = body['streams'][0]['stream']
    assert stream['job'] == 'sre-agent'
    assert stream['severity'] == 'medium'
    assert stream['alert_name'] == 'ContainerRestartLoop'

    log_line = json.loads(body['streams'][0]['values'][0][1])
    assert log_line['action_taken'] == 'restart_container'
    assert log_line['confidence'] == 0.82


@pytest.mark.asyncio
@respx.mock
async def test_reporter_grafana_payload():
    respx.post('http://localhost:8070').mock(return_value=Response(200))
    respx.post('http://localhost:3100/loki/api/v1/push').mock(return_value=Response(204))
    grafana_route = respx.post('http://localhost:3000/api/annotations').mock(return_value=Response(200))

    await reporter_agent(INCIDENT)

    body = json.loads(grafana_route.calls[0].request.content)
    assert 'MEDIUM' in body['text']
    assert 'ContainerRestartLoop' in body['text']
    assert 'sre-agent' in body['tags']
    assert 'medium' in body['tags']


@pytest.mark.asyncio
@respx.mock
async def test_reporter_returns_summary_and_notified():
    respx.post('http://localhost:8070').mock(return_value=Response(200))
    respx.post('http://localhost:3100/loki/api/v1/push').mock(return_value=Response(204))
    respx.post('http://localhost:3000/api/annotations').mock(return_value=Response(200))

    result = await reporter_agent(INCIDENT)

    assert result['notified'] is True
    assert 'MEDIUM' in result['summary']
    assert 'ContainerRestartLoop' in result['summary']
    assert 'restart_container' in result['summary']