from typing import TypedDict, Literal, Optional


class IncidentState(TypedDict):
    # Set by MonitorAgent
    alert_name: str
    alert_source: Literal['prometheus', 'loki']
    raw_payload: dict
    triggered_at: str

    # Set by TriageAgent
    severity: Literal['low', 'medium', 'high', 'critical']
    probable_cause: str
    affected_services: list[str]
    confidence: float

    # Set by RemediationAgent
    action_taken: str
    playbook: Optional[str]

    # Set by ReporterAgent
    summary: str
    notified: bool
