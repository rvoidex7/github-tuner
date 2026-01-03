import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

class TunerStorage:
    def __init__(self, db_path: str = "data/tuner.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
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

    def save_finding(self, title: str, url: str, description: str, stars: int, language: str, embedding: bytes = None) -> int:
        """Save a new finding or ignore if exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO findings (title, url, description, stars, language, embedding, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (title, url, description, stars, language, embedding))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # URL already exists
                return -1

    def update_finding_analysis(self, finding_id: int, summary: str, score: float):
        """Update a finding with AI analysis."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE findings
                SET ai_summary = ?, match_score = ?
                WHERE id = ?
            """, (summary, score, finding_id))

    def update_finding_status(self, finding_id: int, status: str):
        """Update status (pending, liked, disliked, archived)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE findings SET status = ? WHERE id = ?", (status, finding_id))

    def log_feedback(self, finding_id: int, action: str):
        """Log user feedback."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback_logs (finding_id, action)
                VALUES (?, ?)
            """, (finding_id, action))

    def save_strategy(self, config: Dict[str, Any]):
        """Save a search strategy."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO strategies (search_config)
                VALUES (?)
            """, (json.dumps(config),))

    def get_latest_strategy(self) -> Optional[Dict[str, Any]]:
        """Get the most recent strategy."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT search_config FROM strategies ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def get_pending_findings(self) -> List[Dict[str, Any]]:
        """Get all pending findings."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings WHERE status = 'pending' ORDER BY match_score DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_feedback_history(self) -> List[Dict[str, Any]]:
        """Get feedback history for analysis."""
        with sqlite3.connect(self.db_path) as conn:
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
