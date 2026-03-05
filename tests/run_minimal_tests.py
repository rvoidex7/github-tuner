import asyncio
import os
import sys
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['tuner.hunter'] = MagicMock()
sys.modules['tuner.agent.perception'] = MagicMock()

import tests.verify_io_logic
import tests.benchmark_tools

async def main():
    print("Running functionality verification...")
    await tests.verify_io_logic.test_read_write_functionality()

    print("\nRunning benchmark...")
    await tests.benchmark_tools.run_benchmark()

    print("\nAll verifications completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
