import asyncio
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

import httpx

from config import settings
from state import IncidentState


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MonitorAgent:
    def __init__(self, on_incident: Callable[[IncidentState], Awaitable[None]]):
        self._on_incident = on_incident
        self._active_alerts: dict[str, str] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self):
        async with httpx.AsyncClient(timeout=10.0) as client:
            self._client = client
            await asyncio.gather(
                self._host_health_loop(),
                self._container_loop(),
                self._observability_loop(),
                self._services_loop(),
            )

    async def _query(self, promql: str) -> list[dict]:
        try:
            resp = await self._client.get(
                f'{settings.prometheus_url}/api/v1/query',
                params={'query': promql}
            )
            resp.raise_for_status()
            return resp.json()['data']['result']
        except Exception:
            return []

    def _emit(self, alert_name: str, source: str, payload: dict) -> Optional[IncidentState]:
        if alert_name in self._active_alerts:
            return None
        self._active_alerts[alert_name] = _now_iso()
        return IncidentState(
            alert_name=alert_name,
            alert_source=source,
            raw_payload=payload,
            triggered_at=self._active_alerts[alert_name],
            severity='low',
            probable_cause='',
            affected_services=[],
            confidence=0.0,
            action_taken='',
            playbook=None,
            summary='',
            notified=False,
        )

    def _resolve(self, alert_name: str):
        self._active_alerts.pop(alert_name, None)

    async def _host_health_loop(self):
        while True:
            await self._check_host_health()
            await asyncio.sleep(60)
            
    async def _container_loop(self):
        while True:
            await self._check_containers()
            await asyncio.sleep(60)

    async def _observability_loop(self):
        while True:
            await self._check_observability()
            await asyncio.sleep(30)

    async def _services_loop(self):
        while True:
            await self._check_services()
            await asyncio.sleep(120)

    async def _check_host_health(self):
        checks = [
            (
                'HighMemory',
                'node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.15',
            ),
            (
                'HighDisk',
                '1 - node_filesystem_avail_bytes{mountpoint="/"} '
                '/ node_filesystem_size_bytes{mountpoint="/"} > 0.88',
            ),
            (
                'HighLoad',
                'node_load1 > 4',
            ),
        ]
        for alert_name, promql in checks:
            results = await self._query(promql)
            if results:
                incident = self._emit(alert_name, 'prometheus', results[0])
                if incident:
                    await self._on_incident(incident)
            else:
                self._resolve(alert_name)

    async def _check_containers(self):
        checks = [
            (
                'ContainerOOM',
                'increase(container_oom_events_total[5m]) > 0',
            ),
            (
                'ContainerRestartLoop',
                'increase(container_restart_count[15m]) > 3',
            ),
            (
                'ContainerMemoryHigh',
                'container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.85',
            ),
        ]
        for alert_name, promql in checks:
            results = await self._query(promql)
            if results:
                incident = self._emit(alert_name, 'prometheus', results[0])
                if incident:
                    await self._on_incident(incident)
            else:
                self._resolve(alert_name)

    async def _check_observability(self):
        checks = [
            (
                'ScrapeTargetDown',
                'up == 0',
            ),
            (
                'PrometheusIngestionStopped',
                'rate(prometheus_tsdb_head_samples_appended_total[5m]) == 0',
            ),
            (
                'LokiIngestionStopped',
                'rate(loki_ingester_streams_created_total[5m]) == 0',
            ),
            (
                'AlertmanagerFailures',
                'increase(alertmanager_notifications_failed_total[5m]) > 0',
            ),
        ]
        for alert_name, promql in checks:
            results = await self._query(promql)
            if results:
                incident = self._emit(alert_name, 'prometheus', results[0])
                if incident:
                    await self._on_incident(incident)
            else:
                self._resolve(alert_name)

    async def _check_services(self):
        checks = [
            (
                'Traefik5xxSpike',
                'rate(traefik_service_requests_total{code=~"5.."}[5m]) > 0.05',
            ),
            (
                'TraefikBackendDown',
                'traefik_service_server_up == 0',
            ),
            (
                'OllamaModelThrashing',
                'ollama_model_load_duration_seconds > 120',
            ),
        ]
        for alert_name, promql in checks:
            results = await self._query(promql)
            if results:
                incident = self._emit(alert_name, 'prometheus', results[0])
                if incident:
                    await self._on_incident(incident)
            else:
                self._resolve(alert_name)