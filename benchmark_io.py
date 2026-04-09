import asyncio
import time
import os
import sys

# Add src to path
sys.path.append("src")

from tuner.agent.tools import AgentTools

async def monitor(stop_event):
    start = time.time()
    while not stop_event.is_set():
        tick_start = time.time()
        await asyncio.sleep(0.01)
        tick_end = time.time()
        latency = tick_end - tick_start - 0.01
        if latency > 0.05:
            print(f"⚠️ Event loop lag: {latency*1000:.2f}ms")

async def benchmark():
    tools = AgentTools()
    content = "test content " * 1000000 # ~13MB

    print(f"Starting 10 concurrent write_file calls of {len(content)/1024/1024:.1f}MB each...")
    start = time.time()
    tasks = []
    for i in range(10):
        tasks.append(tools.write_file(f"test_file_{i}.txt", content))

    results = await asyncio.gather(*tasks)
    end = time.time()
    print(f"Finished 10 write_file calls in {end - start:.2f}s")

    # Clean up
    for i in range(10):
        try:
            if os.path.exists(f"test_file_{i}.txt"): os.remove(f"test_file_{i}.txt")
            if os.path.exists(f"test_file_{i}.txt.bak"): os.remove(f"test_file_{i}.txt.bak")
        except:
            pass

async def main():
    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(monitor(stop_event))

    await benchmark()

    stop_event.set()
    await monitor_task

if __name__ == "__main__":
    asyncio.run(main())
