import sys
from unittest.mock import MagicMock, AsyncMock

# Mock dependencies
mock_httpx = MagicMock()
mock_httpx.AsyncClient = MagicMock()
sys.modules["httpx"] = mock_httpx

import asyncio
import time
from tuner.hunter import Hunter, RawFinding

async def benchmark():
    hunter = Hunter()

    # Mock _process_item to simulate network delay
    async def mocked_process_item(item):
        await asyncio.sleep(0.1) # Simulate 100ms latency
        return RawFinding(
            title=item["full_name"],
            url=item["html_url"],
            description=item["description"] or "",
            stars=item["stargazers_count"],
            language=item["language"] or "Unknown",
            readme_content="mocked readme"
        )

    hunter._process_item = mocked_process_item

    items = [{"full_name": f"repo/{i}", "html_url": f"url/{i}", "description": "desc", "stargazers_count": i, "language": "Python"} for i in range(10)]

    print(f"Benchmarking with {len(items)} items...")

    # Sequential (current implementation style)
    start_time = time.perf_counter()
    findings_seq = []
    for item in items:
        findings_seq.append(await hunter._process_item(item))
    sequential_time = time.perf_counter() - start_time
    print(f"Sequential time: {sequential_time:.4f}s")

    # Concurrent (proposed implementation style)
    start_time = time.perf_counter()
    findings_con = await asyncio.gather(*(hunter._process_item(item) for item in items))
    concurrent_time = time.perf_counter() - start_time
    print(f"Concurrent time: {concurrent_time:.4f}s")

    assert len(findings_seq) == len(findings_con) == len(items)

    print(f"Improvement: {(sequential_time - concurrent_time) / sequential_time * 100:.2f}%")

if __name__ == "__main__":
    asyncio.run(benchmark())
