import asyncio
from app.main import app
import main
from app.core.data_store import data_store

async def run_test():
    print("Starting background test...")
    await main.on_startup()
    print("Startup complete. Waiting 16 seconds for analyzer to run...")
    await asyncio.sleep(16)
    print("Done waiting.")
    
if __name__ == "__main__":
    asyncio.run(run_test())
