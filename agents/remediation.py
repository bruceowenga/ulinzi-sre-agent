from langgraph.types import interrupt
import instructor
from ollama import Client
from pathlib import Path
from langfuse import observe

from config import settings
from state import IncidentState
from runbooks import get_runbook

PROMPTS_DIR = Path(__file__).parent.parent / 'prompts'


def _generate_playbook(state: IncidentState) -> str:
    client = instructor.from_ollama(Client())
    prompt = (
        f"Incident: {state['alert_name']}\n"
        f"Severity: {state['severity']}\n"
        f"Probable cause: {state['probable_cause']}\n"
        f"Affected services: {', '.join(state['affected_services'])}\n\n"
        "Write a numbered step-by-step remediation playbook for an SRE."
    )
    response = client.chat(
        model=settings.primary_model,
        messages=[
            {
                'role': 'system',
                'content': (PROMPTS_DIR / 'playbook.txt').read_text(),
            },
            {
                'role': 'user',
                'content': prompt,
            },
        ],
        response_model=None,
    )
    return response.message.content


@observe()
def auto_remediation_agent(state: IncidentState) -> dict:
    runbook = get_runbook(state['alert_name'])
    if not runbook:
        return {'action_taken': 'no runbook'}

    services = state['affected_services'] or ['unknown']
    result = runbook(services[0])
    return {'action_taken': result}


@observe()
def gen_playbook_agent(state: IncidentState) -> dict:
    playbook = _generate_playbook(state)
    approval = interrupt({
        'message': 'Approve this playbook?',
        'playbook': playbook,
        'severity': state['severity'],
        'alert_name': state['alert_name'],
    })
    if approval.get('approved'):
        return {'action_taken': 'manual', 'playbook': playbook}
    return {'action_taken': 'rejected', 'playbook': playbook}