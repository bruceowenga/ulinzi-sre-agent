import pytest
import httpx
import respx

from unittest.mock import AsyncMock

from agents.monitor import MonitorAgent
from state import IncidentState

PROMETHEUS_BASE = 'http://localhost:9090/api/v1/query'

FIRING = {'data': {'result': [{'metric': {}, 'value': [1234567890, '1']}]}}
CLEAR = {'data': {'result': []}}

@pytest.fixture
def callback():
    return AsyncMock()

@pytest.fixture
def agent(callback):
    return MonitorAgent(on_incident=callback)

# --- _emit and _resolve (sync, no HTTP) ---

def test_emit_returns_incident(agent):
    incident = agent._emit('HighMemory', 'prometheus', {})
    assert incident is not None
    assert incident['alert_name'] == 'HighMemory'
    assert incident['alert_source'] == 'prometheus'
    assert incident['notified'] is False

def test_emit_deduplicates(agent):
    agent._emit('HighMemory', 'prometheus', {})
    second = agent._emit('HighMemory', 'prometheus', {})
    assert second is None


def test_resolve_allows_re_emit(agent):
    agent._emit('HighMemory', 'prometheus', {})
    agent._resolve('HighMemory')
    incident = agent._emit('HighMemory', 'prometheus', {})
    assert incident is not None


def test_resolve_unknown_alert_is_safe(agent):
    agent._resolve('DoesNotExist')


# --- _query ---

@pytest.fixture
async def connected_agent(agent):
    async with httpx.AsyncClient() as client:
        agent._client = client
        yield agent


@pytest.mark.asyncio
async def test_query_returns_results(connected_agent):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=FIRING))
        results = await connected_agent._query('node_load1 > 4')
        assert len(results) == 1


@pytest.mark.asyncio
async def test_query_returns_empty_on_http_error(connected_agent):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(500))
        results = await connected_agent._query('node_load1 > 4')
        assert results == []


@pytest.mark.asyncio
async def test_query_returns_empty_on_network_error(connected_agent):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(side_effect=httpx.ConnectError('down'))
        results = await connected_agent._query('node_load1 > 4')
        assert results == []


# --- _check_host_health ---

@pytest.mark.asyncio
async def test_host_health_fires_incident_when_threshold_crossed(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=FIRING))
        await connected_agent._check_host_health()
        assert callback.call_count == 3


@pytest.mark.asyncio
async def test_host_health_no_incident_when_clear(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=CLEAR))
        await connected_agent._check_host_health()
        callback.assert_not_called()


@pytest.mark.asyncio
async def test_host_health_deduplicates_across_calls(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=FIRING))
        await connected_agent._check_host_health()
        await connected_agent._check_host_health()
        assert callback.call_count == 3

# --- _check_containers (3 checks) ---

@pytest.mark.asyncio
async def test_containers_fires_incidents_when_threshold_crossed(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=FIRING))
        await connected_agent._check_containers()
        assert callback.call_count == 3


@pytest.mark.asyncio
async def test_containers_no_incident_when_clear(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=CLEAR))
        await connected_agent._check_containers()
        callback.assert_not_called()


@pytest.mark.asyncio
async def test_containers_deduplicates_across_calls(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=FIRING))
        await connected_agent._check_containers()
        await connected_agent._check_containers()
        assert callback.call_count == 3


# --- _check_observability (4 checks) ---

@pytest.mark.asyncio
async def test_observability_fires_incidents_when_threshold_crossed(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=FIRING))
        await connected_agent._check_observability()
        assert callback.call_count == 4


@pytest.mark.asyncio
async def test_observability_no_incident_when_clear(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=CLEAR))
        await connected_agent._check_observability()
        callback.assert_not_called()


# --- _check_services (3 checks) ---

@pytest.mark.asyncio
async def test_services_fires_incidents_when_threshold_crossed(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=FIRING))
        await connected_agent._check_services()
        assert callback.call_count == 3


@pytest.mark.asyncio
async def test_services_no_incident_when_clear(connected_agent, callback):
    with respx.mock:
        respx.get(PROMETHEUS_BASE).mock(return_value=httpx.Response(200, json=CLEAR))
        await connected_agent._check_services()
        callback.assert_not_called()