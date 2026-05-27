import asyncio
import httpx
import json
import time

from langfuse import observe

from config import settings
from state import IncidentState

SEVERITY_PRIORITY = {
    'low': 'low',
    'medium': 'default',
    'high': 'high',
    'critical': 'urgent',
}

SEVERITY_EMOJI = {
    'low': 'INFO',
    'medium': 'WARN',
    'high': 'HIGH',
    'critical': 'CRIT',
}

async def _push_ntfy(client: httpx.AsyncClient, state: IncidentState):
    severity = state['severity']
    await client.post(
        settings.ntfy_url,
        json={
            'topic':    settings.ntfy_topic,
            'title':    f"[{SEVERITY_EMOJI[severity]}] {state['alert_name']}",
            'message':  state['probable_cause'],
            'priority': SEVERITY_PRIORITY[severity],
            'tags': state['affected_services'],
        },
        headers={'Authorization': f'Bearer {settings.ntfy_token}'},
    )


async def _push_loki(client: httpx.AsyncClient, state: IncidentState):
    await client.post(
        f'{settings.loki_url}/loki/api/v1/push',
        json={
            'streams': [{
                'stream': {
                    'job':          'sre-agent',
                    'severity':     state['severity'],
                    'alert_name':   state['alert_name'],
                    'alert_source': state['alert_source'],
                },
                'values': [[
                    str(time.time_ns()),
                    json.dumps({
                        'probable_cause':    state['probable_cause'],
                        'affected_services': state['affected_services'],
                        'action_taken':      state['action_taken'],
                        'confidence':        state['confidence'],
                    }),
                ]],
            }],
        },
    )


async def _push_grafana_annotation(client: httpx.AsyncClient, state: IncidentState):
    await client.post(
        f'{settings.grafana_url}/api/annotations',
        json={
            'text': (
                f"[{state['severity'].upper()}] {state['alert_name']}: "
                f"{state['probable_cause']}"
            ),
            'tags': ['sre-agent', state['severity']] + state['affected_services'],
            'time': int(time.time() * 1000),
        },
        headers={
            'Authorization': f'Bearer {settings.grafana_api_key}',
            'Content-Type':  'application/json',
        },
    )

@observe()
async def reporter_agent(state: IncidentState) -> dict:
    summary = (
        f"{state['severity'].upper()} | {state['alert_name']} | "
        f"{state['probable_cause']} | action: {state['action_taken']}"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        await asyncio.gather(
            _push_ntfy(client, state),
            _push_loki(client, state),
            _push_grafana_annotation(client, state),
        )
    return {'summary': summary, 'notified': True}