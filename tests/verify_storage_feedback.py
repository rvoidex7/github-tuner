import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock aiosqlite before importing TunerStorage
class MockCursor:
    def __init__(self, data=None):
        self.data = data or []
        self.index = 0
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def fetchone(self):
        if self.index < len(self.data):
            res = self.data[self.index]
            self.index += 1
            return res
        return None
    async def fetchall(self):
        return self.data
    @property
    def lastrowid(self):
        return 1

class MockDB:
    def __init__(self):
        self.executed_queries = []
        self.row_factory = None
    async def execute(self, query, params=None):
        self.executed_queries.append((query, params))
        if "PRAGMA table_info(feedback_logs)" in query:
            return MockCursor([
                (0, "id", "INTEGER", 0, None, 1),
                (1, "finding_id", "INTEGER", 0, None, 0),
                (2, "action", "TEXT", 1, None, 0),
                (3, "category", "TEXT", 0, None, 0),
                (4, "reason", "TEXT", 0, None, 0),
                (5, "timestamp", "TIMESTAMP", 0, "CURRENT_TIMESTAMP", 0)
            ])
        if "SELECT * FROM feedback_logs" in query:
            return MockCursor([(1, 1, "liked", "machine-learning", "Interesting use of transformers", "2023-01-01")])
        return MockCursor()
    async def commit(self): pass
    async def close(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass

mock_db = MockDB()
mock_aiosqlite = MagicMock()
mock_aiosqlite.connect = AsyncMock(return_value=mock_db)
sys.modules['aiosqlite'] = mock_aiosqlite

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tuner.storage import TunerStorage

async def test_storage_feedback():
    print("Initializing TunerStorage with mocked aiosqlite...")
    storage = TunerStorage(":memory:")
    await storage.initialize()

    print("Testing log_feedback...")
    await storage.log_feedback(
        finding_id=1,
        action="liked",
        category="machine-learning",
        reason="Interesting use of transformers"
    )

    # Check executed queries
    db = mock_db

    found_insert = False
    for query, params in db.executed_queries:
        if "INSERT INTO feedback_logs" in query:
            found_insert = True
            assert params == (1, "liked", "machine-learning", "Interesting use of transformers")
            break
    assert found_insert, "INSERT INTO feedback_logs not found in executed queries"
    print("Feedback logging SQL verified.")

    # Verify columns exist via PRAGMA (this uses the mock's responses)
    async with await db.execute("PRAGMA table_info(feedback_logs)") as cursor:
        columns = await cursor.fetchall()
        col_names = [col[1] for col in columns]
        assert "category" in col_names
        assert "reason" in col_names

    print("Table schema (mocked) verified via PRAGMA.")

if __name__ == "__main__":
    asyncio.run(test_storage_feedback())
