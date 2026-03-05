import asyncio
import time
import os
import sys
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['tuner.hunter'] = MagicMock()
sys.modules['tuner.agent.perception'] = MagicMock()

from tuner.agent.tools import AgentTools

async def heartbeat(stop_event):
    intervals = []
    last_time = time.perf_counter()
    while not stop_event.is_set():
        await asyncio.sleep(0.01)
        now = time.perf_counter()
        intervals.append(now - last_time)
        last_time = now
    return intervals

async def run_benchmark():
    tools = AgentTools()
    stop_event = asyncio.Event()
    hb_task = asyncio.create_task(heartbeat(stop_event))

    content = "A" * (5 * 1024 * 1024) # 5MB
    num_writes = 10

    print(f"Starting benchmark with {num_writes} writes of 5MB each...")
    start_time = time.perf_counter()
    tasks = []
    for i in range(num_writes):
        tasks.append(tools.write_file(f"bench_tool_{i}.txt", content))

    await asyncio.gather(*tasks)
    end_time = time.perf_counter()

    stop_event.set()
    intervals = await hb_task

    total_time = end_time - start_time
    max_interval = max(intervals) if intervals else 0

    print(f"Benchmark Results:")
    print(f"Total Time: {total_time:.4f}s")
    print(f"Max Heartbeat Interval: {max_interval:.4f}s (Target: ~0.01s)")

    if max_interval < 0.1:
        print("PASS: Event loop was NOT significantly blocked.")
    else:
        print("FAIL: Event loop WAS significantly blocked.")

    # Cleanup
    for i in range(num_writes):
        for p in [f"bench_tool_{i}.txt", f"bench_tool_{i}.txt.bak"]:
            if os.path.exists(p):
                os.remove(p)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
