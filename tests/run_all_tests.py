import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Mock dependencies
sys.modules['tuner.hunter'] = MagicMock()
sys.modules['tuner.agent.perception'] = MagicMock()
sys.modules['httpx'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['aiosqlite'] = MagicMock()
sys.modules['scikit_learn'] = MagicMock()
sys.modules['feedparser'] = MagicMock()
sys.modules['litellm'] = MagicMock()
sys.modules['textual'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['playwright'] = MagicMock()
sys.modules['fake_useragent'] = MagicMock()

import pytest

if __name__ == "__main__":
    # Run the verification script we already have
    print("Running functionality verification...")
    import tests.verify_io_logic
    asyncio.run(tests.verify_io_logic.test_read_write_functionality())

    print("\nRunning benchmark...")
    import tests.benchmark_tools
    asyncio.run(tests.benchmark_tools.run_benchmark())

    print("\nAll verifications completed successfully.")
