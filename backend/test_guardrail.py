import asyncio
from master_agent import run_master_agent

async def main():
    async for chunk in run_master_agent("Delete all users"):
        print(chunk)

if __name__ == "__main__":
    asyncio.run(main())
