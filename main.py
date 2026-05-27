import asyncio
import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from agents.monitor import MonitorAgent
from graph import build_graph
from state import IncidentState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)


async def main():
    async with AsyncSqliteSaver.from_conn_string('incidents.db') as checkpointer:
        app = build_graph(checkpointer)

        async def run_graph(incident: IncidentState) -> None:
            thread_id = f"{incident['alert_name']}-{incident['triggered_at']}"
            config = {'configurable': {'thread_id': thread_id}}

            log.info('Incident received: %s', incident['alert_name'])
            result = await app.ainvoke(incident, config=config)

            # In LangGraph 0.3.x, interrupt metadata lives on the graph state
            # object, not in the ainvoke return value.
            graph_state = await app.aget_state(config)
            pending_interrupts = [
                i for task in graph_state.tasks for i in task.interrupts
            ]

            if pending_interrupts:
                data = pending_interrupts[0].value
                print(f"\n{'=' * 60}")
                print(f"  APPROVAL REQUIRED")
                print(f"  Alert:    {data['alert_name']}")
                print(f"  Severity: {data['severity']}")
                print(f"\n{data['playbook']}")
                print('=' * 60)
                decision = await asyncio.to_thread(input, '\nApprove? [y/N]: ')
                approved = decision.strip().lower() == 'y'

                await app.ainvoke(
                    Command(resume={'approved': approved}),
                    config=config,
                )
                status = 'approved and executed' if approved else 'rejected'
                log.info('Incident %s: %s', incident['alert_name'], status)
            else:
                log.info(
                    'Incident %s complete. Action: %s | Notified: %s',
                    incident['alert_name'],
                    result.get('action_taken', 'unknown'),
                    result.get('notified', False),
                )

        agent = MonitorAgent(on_incident=run_graph)
        log.info('Ulinzi started. Monitoring...')
        await agent.start()

if __name__ == '__main__':
    asyncio.run(main())