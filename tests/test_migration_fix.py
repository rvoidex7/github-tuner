import asyncio
import sqlite3
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock aiosqlite
mock_aiosqlite = MagicMock()
sys.modules['aiosqlite'] = mock_aiosqlite

# Mock numpy
sys.modules['numpy'] = MagicMock()

from tuner.storage import TunerStorage

async def test_migration_logic():
    print("Testing migration logic...")

    real_db = sqlite3.connect(":memory:")

    class AsyncCursor:
        def __init__(self, cursor):
            self.cursor = cursor
        async def fetchall(self):
            return self.cursor.fetchall()
        async def fetchone(self):
            return self.cursor.fetchone()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass

    class AsyncExecuteManager:
        def __init__(self, conn, sql, parameters):
            self.conn = conn
            self.sql = sql
            self.parameters = parameters

        async def __aenter__(self):
            cursor = self.conn.execute(self.sql, self.parameters)
            return AsyncCursor(cursor)

        async def __aexit__(self, exc_type, exc, tb):
            pass

        def __await__(self):
            # To support: cursor = await db.execute(...)
            async def _do_execute():
                cursor = self.conn.execute(self.sql, self.parameters)
                return AsyncCursor(cursor)
            return _do_execute().__await__()

    class AsyncWrappedConnection:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, sql, parameters=()):
            return AsyncExecuteManager(self.conn, sql, parameters)

        async def commit(self):
            self.conn.commit()

        async def close(self):
            self.conn.close()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

    mock_conn = AsyncWrappedConnection(real_db)
    mock_aiosqlite.connect = AsyncMock(return_value=mock_conn)

    storage = TunerStorage(":memory:")

    # 1. Initialize DB
    print("Step 1: Initializing database...")
    await storage.initialize()

    # Check if columns exist
    cursor = real_db.execute("PRAGMA table_info(feedback_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "category" in columns
    assert "reason" in columns
    print("SUCCESS: Columns 'category' and 'reason' created.")

    # 2. Test _column_exists directly
    print("Step 2: Testing _column_exists...")
    exists = await storage._column_exists(mock_conn, "feedback_logs", "category")
    assert exists is True
    exists = await storage._column_exists(mock_conn, "feedback_logs", "non_existent")
    assert exists is False
    print("SUCCESS: _column_exists works correctly.")

    # 3. Test re-initialization
    print("Step 3: Testing re-initialization...")
    await storage._create_tables(mock_conn)
    print("SUCCESS: Re-initialization succeeded without error.")

    # 4. Test partial table
    print("Step 4: Testing migration from old schema...")
    real_db.execute("DROP TABLE feedback_logs")
    real_db.execute("""
        CREATE TABLE feedback_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id INTEGER,
            action TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor = real_db.execute("PRAGMA table_info(feedback_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "category" not in columns
    assert "reason" not in columns

    await storage._create_tables(mock_conn)

    cursor = real_db.execute("PRAGMA table_info(feedback_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "category" in columns
    assert "reason" in columns
    print("SUCCESS: Columns added to existing table.")

    await storage.close()
    print("\nAll migration logic tests passed!")

if __name__ == "__main__":
    asyncio.run(test_migration_logic())
