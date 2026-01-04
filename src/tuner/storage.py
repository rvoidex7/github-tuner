import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

class TunerStorage:
    def __init__(self, db_path: str = "data/tuner.db"):
        self.db_path = db_path
        self._conn = None
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(self.db_path)
            self._init_db(self._conn)
        else:
            self._init_db()

    def _get_conn(self):
        if self.db_path == ":memory:" and self._conn:
            return self._conn
        return sqlite3.connect(self.db_path)

    def _init_db(self, conn=None):
        """Initialize the database schema."""
        # Ensure directory exists
        import os
        if self.db_path != ":memory:":
             os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        should_close = False
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            should_close = True

        try:
            cursor = conn.cursor()

            # Findings table
            cursor.execute("""
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    search_config TEXT NOT NULL
                )
            """)

            # Feedback logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    finding_id INTEGER,
                    action TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (finding_id) REFERENCES findings (id)
                )
            """)
            conn.commit()
        finally:
            if should_close:
                conn.close()

    def save_finding(self, title: str, url: str, description: str, stars: int, language: str, embedding: bytes = None) -> int:
        """Save a new finding or ignore if exists."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO findings (title, url, description, stars, language, embedding, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (title, url, description, stars, language, embedding))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # URL already exists
                return -1
        finally:
            if should_close:
                conn.close()

    def update_finding_analysis(self, finding_id: int, summary: str, score: float):
        """Update a finding with AI analysis."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE findings
                SET ai_summary = ?, match_score = ?
                WHERE id = ?
            """, (summary, score, finding_id))
            conn.commit()
        finally:
            if should_close:
                conn.close()

    def update_finding_status(self, finding_id: int, status: str):
        """Update status (pending, liked, disliked, archived)."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE findings SET status = ? WHERE id = ?", (status, finding_id))
            conn.commit()
        finally:
            if should_close:
                conn.close()

    def log_feedback(self, finding_id: int, action: str):
        """Log user feedback."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback_logs (finding_id, action)
                VALUES (?, ?)
            """, (finding_id, action))
            conn.commit()
        finally:
            if should_close:
                conn.close()

    def get_finding(self, finding_id: int) -> Optional[Dict[str, Any]]:
        """Get a single finding by ID."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings WHERE id = ?", (finding_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if should_close:
                conn.close()

    def save_strategy(self, config: Dict[str, Any]):
        """Save a search strategy."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO strategies (search_config)
                VALUES (?)
            """, (json.dumps(config),))
            conn.commit()
        finally:
            if should_close:
                conn.close()

    def get_latest_strategy(self) -> Optional[Dict[str, Any]]:
        """Get the most recent strategy."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT search_config FROM strategies ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            if should_close:
                conn.close()

    def get_pending_findings(self) -> List[Dict[str, Any]]:
        """Get all pending findings."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings WHERE status = 'pending' ORDER BY match_score DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if should_close:
                conn.close()

    def get_feedback_history(self) -> List[Dict[str, Any]]:
        """Get feedback history for analysis."""
        conn = self._get_conn()
        should_close = (conn != self._conn)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.title, f.description, fl.action
                FROM feedback_logs fl
                JOIN findings f ON fl.finding_id = f.id
                ORDER BY fl.timestamp ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            if should_close:
                conn.close()
