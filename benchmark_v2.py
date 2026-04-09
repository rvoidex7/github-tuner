import asyncio
import time
import os

async def blocking_write(path, content):
    # This simulates what was presumably there before
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return "Done"

async def optimized_write(path, content):
    def _sync():
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    return await asyncio.to_thread(_sync)

async def tick(stop_event, lags):
    while not stop_event.is_set():
        start = time.time()
        await asyncio.sleep(0.01)
        latency = time.time() - start - 0.01
        if latency > 0.005:
            lags.append(latency)

async def run_test(write_func, name):
    print(f"Testing {name}...")
    lags = []
    stop_event = asyncio.Event()
    tick_task = asyncio.create_task(tick(stop_event, lags))

    content = "A" * (5 * 1024 * 1024) # 5MB
    tasks = [write_func(f"test_{name}_{i}.txt", content) for i in range(10)]

    start = time.time()
    await asyncio.gather(*tasks)
    duration = time.time() - start

    stop_event.set()
    await tick_task

    print(f"  Duration: {duration:.4f}s")
    print(f"  Max Lag: {max(lags)*1000 if lags else 0:.2f}ms")
    print(f"  Total Lags: {len(lags)}")

    # Cleanup
    for i in range(10):
        if os.path.exists(f"test_{name}_{i}.txt"): os.remove(f"test_{name}_{i}.txt")

async def main():
    await run_test(blocking_write, "Blocking")
    print("-" * 20)
    await run_test(optimized_write, "Optimized (to_thread)")

if __name__ == "__main__":
    asyncio.run(main())
