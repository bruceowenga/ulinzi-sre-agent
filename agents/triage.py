from pathlib import Path
import instructor
from agents.llm import make_instructor_client
from pydantic import BaseModel, Field
from typing import Literal
from langfuse import observe

from config import settings
from state import IncidentState

PROMPTS_DIR = Path(__file__).parent.parent / 'prompts'


class TriageResult(BaseModel):
    severity:          Literal['low', 'medium', 'high', 'critical']
    probable_cause:    str = Field(max_length=120)
    affected_services: list[str]
    confidence:        float = Field(ge=0.0, le=1.0)


def _build_prompt(state: IncidentState) -> str:
    return (
        f"Alert: {state['alert_name']}\n"
        f"Source: {state['alert_source']}\n"
        f"Triggered at: {state['triggered_at']}\n"
        f"Raw data: {state['raw_payload']}\n\n"
        "Classify this incident. Be concise, probable_cause must be one sentence under 120 characters."
    )


def _call_llm(model: str, prompt: str) -> TriageResult:
    client = make_instructor_client()
    return client.chat.completions.create(
        model=model,
        messages=[
            {
                'role': 'system',
                'content': (PROMPTS_DIR / 'triage.txt').read_text(),
            },
            {
                'role': 'user',
                'content': prompt,
            },
        ],
        response_model=TriageResult,
        max_retries=3,
    )


@observe()
def triage_agent(state: IncidentState) -> dict:
    prompt = _build_prompt(state)
    result = _call_llm(settings.primary_model, prompt)

    if result.confidence < settings.confidence_threshold:
        result = _call_llm(settings.fallback_model, prompt)

    return {
        'severity': result.severity,
        'probable_cause': result.probable_cause,
        'affected_services': result.affected_services,
        'confidence': result.confidence,
    }