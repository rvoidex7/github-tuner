import json
import uuid
import datetime
from typing import Dict, Any, List, Optional
from tuner.storage import TunerStorage
import aiosqlite

class AgentMemory:
    def __init__(self, storage: TunerStorage):
        self.storage = storage

    async def create_session(self, target_repo: str, model_config: Dict[str, Any]) -> str:
        """Create a new agent session."""
        session_id = str(uuid.uuid4())
        async with self.storage._get_conn_ctx() as db:
            await db.execute("""
                INSERT INTO conversations (id, target_repo, model_config)
                VALUES (?, ?, ?)
            """, (session_id, target_repo, json.dumps(model_config)))
            await db.commit()
        return session_id

    async def log_turn(self, session_id: str, role: str, content: str, tool_calls: Optional[List[Dict]] = None, input_tokens: int = 0, output_tokens: int = 0):
        """Log a single turn (observation, thought, or action)."""
        async with self.storage._get_conn_ctx() as db:
            await db.execute("""
                INSERT INTO turns (conversation_id, role, content, tool_calls, input_tokens, output_tokens)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, json.dumps(tool_calls) if tool_calls else None, input_tokens, output_tokens))
            await db.commit()

    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve full history of a session."""
        async with self.storage._get_conn_ctx() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT role, content, tool_calls
                FROM turns
                WHERE conversation_id = ?
                ORDER BY id ASC
            """, (session_id,)) as cursor:
                rows = await cursor.fetchall()
                history = []
                for row in rows:
                    history.append({
                        "role": row['role'],
                        "content": row['content'],
                        "tool_calls": json.loads(row['tool_calls']) if row['tool_calls'] else None
                    })
                return history

    async def update_knowledge(self, file_path: str, fingerprint: str, summary: str = None):
        """Update file knowledge."""
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self.storage._get_conn_ctx() as db:
            await db.execute("""
                INSERT INTO knowledge_graph (file_path, ast_fingerprint, last_analyzed, summary)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    ast_fingerprint = excluded.ast_fingerprint,
                    last_analyzed = excluded.last_analyzed,
                    summary = coalesce(excluded.summary, knowledge_graph.summary)
            """, (file_path, fingerprint, now, summary))
            await db.commit()

    async def get_knowledge(self, file_path: str) -> Optional[Dict[str, Any]]:
        async with self.storage._get_conn_ctx() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM knowledge_graph WHERE file_path = ?", (file_path,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
