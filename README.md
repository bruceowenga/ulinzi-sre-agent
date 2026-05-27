# Ulinzi

A multi-agent SRE incident responder built with LangGraph, Ollama, and Prometheus. Monitors a Linux/Docker stack, classifies incidents with a local or cloud LLM, executes safe runbooks automatically, and routes high-severity incidents to a human-in-the-loop approval flow.

![Python](https://img.shields.io/badge/python-3.12+-blue)
![Tests](https://img.shields.io/badge/tests-39%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

---

## An incident, from detection to notification

*Output captured from a live run against the Odin homelab stack. 2026-05-27.*

Two incidents fired in the same polling cycle. They took different paths through the graph.

---

### Path 1 -- auto remediation (low/medium severity)

**Alert fired**

```
alert:    ContainerMemoryHigh
source:   prometheus (cAdvisor)
payload:  container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.85
fired at: 2026-05-27T17:39:54+00:00
```

**TriageAgent** classified the incident using MiniMax M2.7 via NVIDIA NIM:

```json
{
  "severity": "medium",
  "probable_cause": "Container memory usage exceeds 85% of the allocated limit.",
  "affected_services": ["prometheus"],
  "confidence": 0.88
}
```

**RemediationAgent** looked up the runbook registry -- no runbook registered for this alert type, so it logged the action and moved on:

```
runbook:  (none registered)
result:   no runbook
```

**ReporterAgent** pushed to three sinks:

```
ntfy:    pushed to odin-alerts      [17:40:55 +00:00]
Loki:    incident log written       [job=sre-agent, severity=medium]
Grafana: annotation posted          [time=17:40:55]
```

Total time from alert to notification: **61 seconds** (MiniMax M2.7 classification via NVIDIA NIM).

---

### Path 2 -- human-in-the-loop (high/critical severity)

**Alert fired**

```
alert:    LokiIngestionStopped
source:   prometheus
payload:  rate(loki_ingester_streams_created_total[5m]) == 0
fired at: 2026-05-27T17:39:54+00:00
```

**TriageAgent** classified the incident:

```json
{
  "severity": "high",
  "probable_cause": "Loki ingestion pipeline has stopped -- no new streams created in the last 5 minutes.",
  "affected_services": ["loki"],
  "confidence": 0.94
}
```

**RemediationAgent** generated a 10-step playbook and paused for approval. Excerpt:

```
| # | Action                                   | Command                                         |
|---|------------------------------------------|-------------------------------------------------|
| 1 | Verify the Loki container is running     | sudo docker ps -a --filter name=loki            |
| 2 | Pull recent logs from the container      | sudo docker logs loki --tail=300 2>&1           |
| 3 | Check disk space on the volume Loki      | df -h /var/lib/loki                             |
|   | writes to                                |                                                 |
| 4 | Verify inode availability                | df -i /var/lib/loki                             |
| 5 | Inspect Docker storage usage             | sudo docker system df                           |
| 6 | If disk/inodes are exhausted, free space | sudo docker system prune -af --volumes          |
| 7 | Confirm write permissions on Loki data   | ls -la /var/lib/loki                            |
| 8 | Restart the Loki container               | sudo docker restart loki                        |
| 9 | Verify ingestion has resumed             | curl -sf http://localhost:3100/ready            |
```

Operator approved at the terminal. **ReporterAgent** pushed to three sinks:

```
ntfy:    pushed to odin-alerts      [17:57:22 +00:00]
Loki:    incident log written       [job=sre-agent, severity=high]
Grafana: annotation posted          [time=17:57:22]
```

---

## What it is

Ulinzi polls a Prometheus instance across four async loops (host health, containers, observability stack, services), classifies any threshold crossing using a local or cloud LLM with structured output validation, and routes the incident through a LangGraph state machine. Low and medium severity incidents execute a runbook automatically. High and critical incidents generate a step-by-step playbook and wait for human approval before proceeding.

Small models are the deliberate default. The primary model (`qwen2.5:1.5b`) uses approximately 1.8 GB of RAM and runs locally via Ollama with no external API calls, no per-token cost, and no data leaving the machine. The fallback (`phi3.5:mini`) loads only when classification confidence falls below 0.6.

For teams with access to larger models or cloud inference, the model layer is configurable. Setting `NVIDIA_BUILD_API_KEY` in `.env` routes all inference to NVIDIA NIM instead of local Ollama. Any OpenAI-compatible endpoint works as a drop-in via `PRIMARY_MODEL`, `FALLBACK_MODEL`, and the relevant API key. The architecture is designed for BYOM (Bring Your Own Model): swap the endpoint, keep the pipeline.

Ulinzi is also the core prototype for **Linzi AI**, an agentic SRE platform targeting SMBs in Kenya and East Africa. The delta between this prototype and a multi-tenant SaaS product is a configuration layer and a REST API wrapper. The agentic logic does not change.

---

## Architecture

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
        __start__([<p>__start__</p>]):::first
        triage(triage)
        auto_fix(auto_fix)
        gen_playbook(gen_playbook)
        report(report)
        __end__([<p>__end__</p>]):::last
        __start__ --> triage;
        auto_fix --> report;
        gen_playbook --> report;
        triage -. &nbsp;auto&nbsp; .-> auto_fix;
        triage -. &nbsp;manual&nbsp; .-> gen_playbook;
        report --> __end__;
        classDef default fill:#f2f0ff,line-height:1.2
        classDef first fill-opacity:0
        classDef last fill:#bfb6fc
```

| Agent | Responsibility | Uses LLM |
|---|---|---|
| MonitorAgent | Polls Prometheus and Loki across 4 async loops | No |
| TriageAgent | Classifies severity, probable cause, affected services | Yes (configurable model) |
| RemediationAgent | Executes runbook or generates playbook with human approval | Yes (playbook path only) |
| ReporterAgent | Pushes to ntfy, Loki, and Grafana annotations | No |

---

## Prerequisites

- Python 3.12+
- One of:
  - [Ollama](https://ollama.com) running locally with models pulled: `ollama pull qwen2.5:1.5b && ollama pull phi3.5:mini`
  - An NVIDIA NIM API key (or any OpenAI-compatible endpoint)
- A Prometheus instance with Node Exporter and cAdvisor scrape targets
- A Loki instance (optional, for log-based alerts)
- An ntfy instance (optional, for mobile notifications)

---

## Installation

```bash
git clone https://github.com/bruceowenga/ulinzi-sre-agent
cd ulinzi-sre-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your endpoints and tokens
```

---

## Configuration

All configuration is loaded from `.env`. See `.env.example` for the full list. Key variables:

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus query endpoint |
| `LOKI_URL` | `http://localhost:3100` | Loki push and query endpoint |
| `GRAFANA_URL` | `http://localhost:3000` | Grafana instance for annotations |
| `GRAFANA_API_KEY` | (required) | Grafana service account token |
| `NTFY_URL` | `http://localhost:8070` | ntfy server URL |
| `NTFY_TOKEN` | (required) | ntfy access token |
| `NTFY_TOPIC` | `odin-alerts` | ntfy topic name |
| `PRIMARY_MODEL` | `qwen2.5:1.5b` | Model for triage and playbook generation |
| `FALLBACK_MODEL` | `phi3.5:mini` | Fallback when confidence falls below threshold |
| `CONFIDENCE_THRESHOLD` | `0.6` | Threshold below which fallback model is used |
| `NVIDIA_BUILD_API_KEY` | (optional) | Set to route inference to NVIDIA NIM instead of Ollama |
| `DRY_RUN` | `false` | Set to `true` to log runbook actions without executing |

To use NVIDIA NIM:

```
NVIDIA_BUILD_API_KEY=nvapi-...
PRIMARY_MODEL=minimaxai/minimax-m2.7
FALLBACK_MODEL=minimaxai/minimax-m2.7
```

---

## Running

```bash
# Dry run: polling and triage work, runbooks log actions but do not execute
DRY_RUN=true python main.py

# Live
python main.py
```

The process opens `incidents.db` (SQLite) on startup. In-flight incidents, including those paused at the human approval step, survive restarts.

---

## Tests

```bash
pytest -v
```

39 tests covering MonitorAgent deduplication and polling logic, TriageResult schema validation and fallback behaviour, runbook dry-run correctness, and ReporterAgent sink payloads. All HTTP calls to Prometheus, Ollama, ntfy, Loki, and Grafana are mocked.

---

## Project structure

```
ulinzi/
├── agents/
│   ├── monitor.py       # Prometheus + Loki polling, 4 async loops
│   ├── triage.py        # instructor + structured output classification
│   ├── remediation.py   # runbook dispatch + playbook generation + interrupt
│   ├── reporter.py      # ntfy, Loki, and Grafana annotation sinks
│   └── llm.py           # instructor client factory (Ollama or NVIDIA NIM)
├── runbooks/
│   ├── __init__.py      # registry mapping alert names to callables
│   ├── container_oom.py # docker restart
│   ├── disk_pressure.py # docker system prune
│   └── log_flood.py     # container log truncation
├── prompts/
│   ├── triage.txt       # system prompt for TriageAgent
│   └── playbook.txt     # system prompt for playbook generation
├── dashboards/
│   └── sre-agent.json   # 5-panel Grafana dashboard
├── tests/
├── state.py             # IncidentState TypedDict (shared graph state)
├── config.py            # pydantic-settings config loaded from .env
├── graph.py             # LangGraph state machine
├── main.py              # entry point
└── .env.example
```

---

## Path to Linzi AI

The agentic core (all four agents) does not change between prototype and product. Only the delivery layer changes.

| Component | This prototype | Linzi AI v1 |
|---|---|---|
| Config | `.env` per server | Multi-tenant database row per customer |
| Prometheus source | Hardcoded Odin endpoint | Customer-supplied endpoint |
| Entry point | Polling loop in `main.py` | REST API: `POST /incidents/ingest` |
| LLM | Local Ollama or NVIDIA NIM | Groq free tier (Llama 3.1 70B) |
| Notifications | Personal ntfy topic | Configurable: Slack, PagerDuty, WhatsApp Business |
| Runbooks | Python functions | YAML-defined marketplace with approval policies |

East Africa market constraints built in from day one: offline-tolerant incident buffering via SQLite, WhatsApp Business API as a notification sink, near-zero inference cost using Groq rather than OpenAI.

---

## License

MIT
