import aiosqlite
import json
import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

class TunerStorage:
    def __init__(self, db_path: str = "data/tuner.db"):
        self.db_path = db_path
        # For :memory:, we need to keep the connection alive if we want data to persist between calls
        # within the same process. aiosqlite.connect returns a context manager, but we can also await it
        # to get a connection object.
        self._memory_conn = None

    async def initialize(self):
        """Initialize the database schema."""
        if self.db_path != ":memory:":
             os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
             async with aiosqlite.connect(self.db_path) as db:
                 await self._create_tables(db)
        else:
            # For memory, we create a persistent connection
            self._memory_conn = await aiosqlite.connect(self.db_path)
            await self._create_tables(self._memory_conn)

    async def close(self):
        if self._memory_conn:
            await self._memory_conn.close()
            self._memory_conn = None

    async def _create_tables(self, db):
        # Findings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                description TEXT,
                stars INTEGER,
                language TEXT,
                embedding BLOB,
                ai_summary TEXT,
                match_score REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Strategies table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                search_config TEXT NOT NULL
            )
        """)

        # Feedback logs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_id INTEGER,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (finding_id) REFERENCES findings (id)
            )
        """)
        await db.commit()

    def _get_conn_ctx(self):
        if self.db_path == ":memory:":
            if self._memory_conn:
                # To simulate context manager behavior for persistent connection
                class MockContext:
                    def __init__(self, conn): self.conn = conn
                    async def __aenter__(self): return self.conn
                    async def __aexit__(self, exc_type, exc, tb): pass
                return MockContext(self._memory_conn)
            else:
                 # Should have been initialized
                 return aiosqlite.connect(self.db_path)
        else:
            return aiosqlite.connect(self.db_path)

    async def save_finding(self, title: str, url: str, description: str, stars: int, language: str, embedding: bytes = None) -> int:
        """Save a new finding or ignore if exists."""
        async with self._get_conn_ctx() as db:
            try:
                cursor = await db.execute("""
                    INSERT INTO findings (title, url, description, stars, language, embedding, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (title, url, description, stars, language, embedding))
                await db.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # URL already exists
                return -1

    async def update_finding_analysis(self, finding_id: int, summary: str, score: float):
        """Update a finding with AI analysis."""
        async with self._get_conn_ctx() as db:
            await db.execute("""
                UPDATE findings
                SET ai_summary = ?, match_score = ?
                WHERE id = ?
            """, (summary, score, finding_id))
            await db.commit()

    async def update_finding_status(self, finding_id: int, status: str):
        """Update status (pending, liked, disliked, archived)."""
        async with self._get_conn_ctx() as db:
            await db.execute("UPDATE findings SET status = ? WHERE id = ?", (status, finding_id))
            await db.commit()

    async def log_feedback(self, finding_id: int, action: str):
        """Log user feedback."""
        async with self._get_conn_ctx() as db:
            await db.execute("""
                INSERT INTO feedback_logs (finding_id, action)
                VALUES (?, ?)
            """, (finding_id, action))
            await db.commit()

    async def get_finding(self, finding_id: int) -> Optional[Dict[str, Any]]:
        """Get a single finding by ID."""
        async with self._get_conn_ctx() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def save_strategy(self, config: Dict[str, Any]):
        """Save a search strategy."""
        async with self._get_conn_ctx() as db:
            await db.execute("""
                INSERT INTO strategies (search_config)
                VALUES (?)
            """, (json.dumps(config),))
            await db.commit()

    async def get_latest_strategy(self) -> Optional[Dict[str, Any]]:
        """Get the most recent strategy."""
        async with self._get_conn_ctx() as db:
            async with db.execute("SELECT search_config FROM strategies ORDER BY id DESC LIMIT 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None

    async def get_pending_findings(self) -> List[Dict[str, Any]]:
        """Get all pending findings."""
        async with self._get_conn_ctx() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM findings WHERE status = 'pending' ORDER BY match_score DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_feedback_history(self) -> List[Dict[str, Any]]:
        """Get feedback history for analysis."""
        async with self._get_conn_ctx() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT f.title, f.description, fl.action
                FROM feedback_logs fl
                JOIN findings f ON fl.finding_id = f.id
                ORDER BY fl.timestamp ASC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
