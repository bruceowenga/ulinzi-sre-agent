from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from state import IncidentState
from agents.triage import triage_agent
from agents.remediation import auto_remediation_agent, gen_playbook_agent


def reporter_agent(state: IncidentState) -> dict:
    return {}


def route_by_severity(state: IncidentState) -> str:
    if state['severity'] in ('low', 'medium'):
        return 'auto'
    return 'manual'


def build_graph(checkpointer):
    graph = StateGraph(IncidentState)

    graph.add_node('triage',   triage_agent)
    graph.add_node('auto_fix', auto_remediation_agent)
    graph.add_node('gen_playbook', gen_playbook_agent)
    graph.add_node('report',       reporter_agent)

    graph.set_entry_point('triage')

    graph.add_conditional_edges('triage', route_by_severity, {
        'auto':   'auto_fix',
        'manual': 'gen_playbook',
    })
    graph.add_edge('auto_fix',     'report')
    graph.add_edge('gen_playbook', 'report')
    graph.add_edge('report', END)

    return graph.compile(checkpointer=checkpointer)