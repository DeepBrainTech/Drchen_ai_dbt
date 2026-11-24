"""PostgreSQL conversation storage for Dr. Chen AI.

Implementation in progress. SQLite remains the default backend.
"""

from __future__ import annotations

from .postgres_config import connect_postgres


class PostgresSessionStore:
    """Student-scoped PostgreSQL conversation repository."""

    def __init__(self, user_id: str):
        if not user_id or not user_id.strip():
            raise ValueError("A student user_id is required")

        self.user_id = user_id

    async def create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Create a conversation owned by the authenticated student."""
        import time
        import uuid

        sid = session_id or str(uuid.uuid4())
        now = time.time()
        session_title = title or "New conversation"

        with connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO drchen_sessions
                        (id, user_id, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, title, created_at, updated_at
                    """,
                    (sid, self.user_id, session_title, now, now),
                )
                row = cur.fetchone()

        return {
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
        }

    async def get_session(self, session_id: str) -> dict | None:
        """Retrieve a conversation belonging to this student."""
        with connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, created_at, updated_at,
                           compressed_summary, summary_up_to_msg_id,
                           preferences_json, deleted_at
                    FROM drchen_sessions
                    WHERE id = %s AND user_id = %s
                    """,
                    (session_id, self.user_id),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "compressed_summary": row[4],
            "summary_up_to_msg_id": row[5],
            "preferences_json": row[6],
            "deleted_at": row[7],
        }

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        capability: str = "",
        events: list[dict] | None = None,
        attachments: list[dict] | None = None,
        metadata: dict | None = None,
        parent_message_id: int | str | None = None,
    ) -> int:
        """Save a message only in a conversation owned by this student."""
        import json
        import time

        with connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO drchen_messages
                        (session_id, role, content, capability,
                         events_json, attachments_json, metadata_json,
                         created_at, parent_message_id)
                    SELECT id, %s, %s, %s, %s, %s, %s, %s, %s
                    FROM drchen_sessions
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                    """,
                    (
                        role,
                        content,
                        capability,
                        json.dumps(events or []),
                        json.dumps(attachments or []),
                        json.dumps(metadata or {}),
                        time.time(),
                        parent_message_id,
                        session_id,
                        self.user_id,
                    ),
                )
                row = cur.fetchone()

        if row is None:
            raise PermissionError("Conversation not found or access denied")

        return row[0]

    async def get_messages(self, session_id: str) -> list[dict]:
        """Retrieve messages only from a conversation owned by this student."""
        import json

        with connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT m.id, m.session_id, m.role, m.content,
                           m.capability, m.events_json,
                           m.attachments_json, m.metadata_json,
                           m.created_at, m.parent_message_id
                    FROM drchen_messages AS m
                    JOIN drchen_sessions AS s ON s.id = m.session_id
                    WHERE s.id = %s AND s.user_id = %s
                    ORDER BY m.created_at ASC, m.id ASC
                    """,
                    (session_id, self.user_id),
                )
                rows = cur.fetchall()

        return [
            {
                "id": row[0],
                "session_id": row[1],
                "role": row[2],
                "content": row[3],
                "capability": row[4],
                "events": json.loads(row[5] or "[]"),
                "attachments": json.loads(row[6] or "[]"),
                "metadata": json.loads(row[7] or "{}"),
                "created_at": row[8],
                "parent_message_id": row[9],
            }
            for row in rows
        ]


    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        workspace_id: str | None = None,
    ) -> list[dict]:
        """List this student's conversations, newest first."""
        import asyncio
        import json
        from psycopg.rows import dict_row
        from .postgres_config import connect_postgres

        def load_sessions():
            with connect_postgres() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT
                            s.id,
                            s.title,
                            s.created_at,
                            s.updated_at,
                            s.compressed_summary,
                            s.summary_up_to_msg_id,
                            s.preferences_json,
                            (
                                SELECT COUNT(*)
                                FROM drchen_messages m
                                WHERE m.session_id = s.id
                                  AND m.role != 'system'
                            ) AS message_count,
                            'idle' AS status,
                            '' AS active_turn_id,
                            '' AS capability,
                            COALESCE((
                                SELECT m.content
                                FROM drchen_messages m
                                WHERE m.session_id = s.id
                                  AND m.role != 'system'
                                  AND TRIM(m.content) != ''
                                ORDER BY m.id DESC
                                LIMIT 1
                            ), '') AS last_message
                        FROM drchen_sessions s
                        WHERE s.user_id = %s
                          AND s.deleted_at IS NULL
                          AND s.id NOT LIKE 'imported\\_%%' ESCAPE '\\'
                        ORDER BY s.updated_at DESC, s.id ASC
                        LIMIT %s OFFSET %s
                        """,
                        (self.user_id, max(0, limit), max(0, offset)),
                    )
                    rows = cur.fetchall()

            results = []
            for row in rows:
                row["session_id"] = row["id"]
                row["preferences"] = json.loads(
                    row.pop("preferences_json") or "{}"
                )
                if workspace_id is not None:
                    prefs = row["preferences"]
                    if (
                        prefs.get("workspace_id") != workspace_id
                        or prefs.get("archived")
                        or prefs.get("parent_session_id")
                    ):
                        continue
                results.append(row)
            return results

        return await asyncio.to_thread(load_sessions)
