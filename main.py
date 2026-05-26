import asyncio

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from graph import build_graph


async def main():
    async with AsyncSqliteSaver.from_conn_string('incidents.db') as checkpointer:
        app = build_graph(checkpointer)
        print('Ulinzi started. Monitoring...')
        # Polling loops will be added here in Phase 1
        await asyncio.sleep(3600)


if __name__ == '__main__':
    asyncio.run(main())