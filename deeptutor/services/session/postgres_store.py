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
        self.scope_key = f"student:{self.user_id}"


    async def delete_turn_by_message(self, session_id: str, message_id: int) -> dict:
        """Delete a completed conversation turn without breaking branches."""
        import asyncio
        import json
        import time

        from .thread_attribution import (
            BACKFILL_ATTEMPTED_KEY,
            TUTOR_SOURCE_KEY,
        )

        def decode(value, default):
            try:
                return json.loads(value) if isinstance(value, str) else (
                    value if value is not None else default
                )
            except (TypeError, ValueError):
                return default

        def execute():
            missing = {
                "deleted": False,
                "attachment_ids": [],
                "turn_id": None,
                "was_active": False,
            }

            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id FROM drchen_sessions
                        WHERE id = %s AND user_id = %s
                          AND deleted_at IS NULL
                        FOR UPDATE
                        """,
                        (session_id, self.user_id),
                    )
                    if cur.fetchone() is None:
                        return missing

                    cur.execute(
                        """
                        SELECT id, role, attachments_json, metadata_json,
                               created_at, parent_message_id
                        FROM drchen_messages
                        WHERE id = %s AND session_id = %s
                        """,
                        (message_id, session_id),
                    )
                    msg = cur.fetchone()
                    if msg is None:
                        return missing

                    mid, role, attachments, metadata, created, parent = msg
                    paired = None

                    if role == "user":
                        cur.execute(
                            """
                            SELECT id, role, attachments_json, metadata_json,
                                   created_at, parent_message_id
                            FROM drchen_messages
                            WHERE session_id = %s AND role = 'assistant'
                              AND parent_message_id = %s
                            ORDER BY id LIMIT 1
                            """,
                            (session_id, mid),
                        )
                        paired = cur.fetchone()
                    elif role == "assistant" and parent is not None:
                        cur.execute(
                            """
                            SELECT id, role, attachments_json, metadata_json,
                                   created_at, parent_message_id
                            FROM drchen_messages
                            WHERE session_id = %s AND role = 'user'
                              AND id = %s
                            """,
                            (session_id, parent),
                        )
                        paired = cur.fetchone()

                    user_msg = msg if role == "user" else paired
                    turn = None

                    if role == "assistant":
                        cur.execute(
                            """
                            SELECT id, status FROM drchen_turns
                            WHERE session_id = %s
                              AND assistant_message_id = %s
                            LIMIT 1
                            """,
                            (session_id, mid),
                        )
                        turn = cur.fetchone()

                    if turn is None and user_msg is not None:
                        user_metadata = decode(user_msg[3], {})
                        stamped = (
                            str(user_metadata.get("turn_id") or "").strip()
                            if isinstance(user_metadata, dict) else ""
                        )
                        if stamped:
                            cur.execute(
                                """
                                SELECT id, status FROM drchen_turns
                                WHERE session_id = %s AND id = %s
                                """,
                                (session_id, stamped),
                            )
                            turn = cur.fetchone()

                    if turn is None and user_msg is not None:
                        cur.execute(
                            """
                            SELECT id, status FROM drchen_turns
                            WHERE session_id = %s AND created_at <= %s
                            ORDER BY created_at DESC LIMIT 1
                            """,
                            (session_id, user_msg[4]),
                        )
                        turn = cur.fetchone()

                    turn_id = turn[0] if turn else None
                    if turn and turn[1] in (
                        "queued", "running", "waiting_input"
                    ):
                        return {
                            **missing,
                            "turn_id": turn_id,
                            "was_active": True,
                        }

                    if role == "assistant" and paired is not None:
                        cur.execute(
                            """
                            SELECT 1 FROM drchen_messages
                            WHERE session_id = %s AND role = 'assistant'
                              AND parent_message_id = %s AND id != %s
                            LIMIT 1
                            """,
                            (session_id, paired[0], mid),
                        )
                        if cur.fetchone():
                            paired = None

                    ids = [mid]
                    if paired is not None:
                        ids.append(paired[0])

                    attachment_ids = []
                    for row in (msg, paired):
                        if row is None:
                            continue
                        for att in decode(row[2], []):
                            if isinstance(att, dict):
                                aid = att.get("id") or att.get("attachment_id")
                                if aid:
                                    attachment_ids.append(aid)

                    if turn_id is not None:
                        cur.execute(
                            "DELETE FROM drchen_turns WHERE id = %s AND session_id = %s",
                            (turn_id, session_id),
                        )

                    for deleted_id in sorted(ids, reverse=True):
                        cur.execute(
                            """
                            UPDATE drchen_messages
                            SET parent_message_id = (
                                SELECT parent_message_id
                                FROM drchen_messages WHERE id = %s
                            )
                            WHERE session_id = %s AND parent_message_id = %s
                            """,
                            (deleted_id, session_id, deleted_id),
                        )

                    cur.execute(
                        """
                        DELETE FROM drchen_messages
                        WHERE session_id = %s AND id = ANY(%s)
                        """,
                        (session_id, ids),
                    )

                    cur.execute(
                        """
                        SELECT id, preferences_json
                        FROM drchen_sessions
                        WHERE user_id = %s AND id != %s
                        FOR UPDATE
                        """,
                        (self.user_id, session_id),
                    )
                    children = cur.fetchall()
                    detached = []

                    for child_id, raw_preferences in children:
                        prefs = decode(raw_preferences, {})
                        if not isinstance(prefs, dict):
                            continue
                        if str(prefs.get("parent_session_id") or "") != session_id:
                            continue
                        if str(prefs.get(TUTOR_SOURCE_KEY) or "") not in {
                            str(x) for x in ids
                        }:
                            continue

                        prefs[TUTOR_SOURCE_KEY] = ""
                        prefs[BACKFILL_ATTEMPTED_KEY] = True
                        cur.execute(
                            """
                            UPDATE drchen_sessions
                            SET preferences_json = %s
                            WHERE id = %s AND user_id = %s
                            """,
                            (json.dumps(prefs), child_id, self.user_id),
                        )
                        detached.append(child_id)

                    cur.execute(
                        """
                        UPDATE drchen_sessions
                        SET updated_at = %s,
                            summary_up_to_msg_id =
                                CASE
                                    WHEN summary_up_to_msg_id >= %s THEN 0
                                    ELSE summary_up_to_msg_id
                                END
                        WHERE id = %s AND user_id = %s
                        """,
                        (time.time(), min(ids), session_id, self.user_id),
                    )

                conn.commit()

            return {
                "deleted": True,
                "attachment_ids": attachment_ids,
                "turn_id": turn_id,
                "was_active": False,
                "deleted_message_ids": ids,
                "detached_thread_ids": detached,
            }

        return await asyncio.to_thread(execute)

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
                    WHERE id = %s AND user_id = %s AND deleted_at IS NULL
                    """,
                    (session_id, self.user_id),
                )
                row = cur.fetchone()

        if row is None:
            return None

        import json

        preferences = row[6] or {}
        if isinstance(preferences, str):
            preferences = json.loads(preferences)

        return {
            "id": row[0],
            "session_id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "compressed_summary": row[4],
            "summary_up_to_msg_id": row[5],
            "preferences_json": row[6],
            "preferences": preferences,
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
                    WHERE s.id = %s AND s.user_id = %s AND s.deleted_at IS NULL
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

    async def update_session_title(self, session_id: str, title: str) -> bool:
        """Rename a conversation owned by the current student."""
        import asyncio

        def rename():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE drchen_sessions
                        SET title = %s,
                            updated_at = EXTRACT(EPOCH FROM NOW())
                        WHERE id = %s
                          AND user_id = %s
                          AND deleted_at IS NULL
                        RETURNING id
                        """,
                        (title, session_id, self.user_id),
                    )
                    return cur.fetchone() is not None

        return await asyncio.to_thread(rename)

    async def soft_delete_session(self, session_id: str) -> bool:
        """Move a student's conversation to the recycle bin."""
        import asyncio

        def delete():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE drchen_sessions
                        SET deleted_at = EXTRACT(EPOCH FROM NOW()),
                            updated_at = EXTRACT(EPOCH FROM NOW())
                        WHERE id = %s
                          AND user_id = %s
                          AND deleted_at IS NULL
                        RETURNING id
                        """,
                        (session_id, self.user_id),
                    )
                    return cur.fetchone() is not None

        return await asyncio.to_thread(delete)


    async def delete_session(self, session_id: str) -> bool:
        """Move an owned conversation to the recycle bin."""
        return await self.soft_delete_session(session_id)


    async def list_deleted_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """List deleted conversations belonging to this student."""
        with connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, created_at, updated_at, deleted_at
                    FROM drchen_sessions
                    WHERE user_id = %s AND deleted_at IS NOT NULL
                    ORDER BY deleted_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (self.user_id, limit, offset),
                )
                rows = cur.fetchall()

        return [
            {
                "session_id": row[0],
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "deleted_at": row[4],
            }
            for row in rows
        ]

    async def hard_delete_session(self, session_id: str) -> bool:
        """Permanently delete an owned conversation from the recycle bin."""
        with connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM drchen_sessions
                    WHERE id = %s
                      AND user_id = %s
                      AND deleted_at IS NOT NULL
                    RETURNING id
                    """,
                    (session_id, self.user_id),
                )
                return cur.fetchone() is not None

    async def restore_session(self, session_id: str) -> bool:
        """Restore a deleted conversation belonging to the current student."""
        import asyncio

        def restore():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE drchen_sessions
                        SET deleted_at = NULL,
                            updated_at = EXTRACT(EPOCH FROM NOW())
                        WHERE id = %s
                          AND user_id = %s
                          AND deleted_at IS NOT NULL
                        RETURNING id
                        """,
                        (session_id, self.user_id),
                    )
                    return cur.fetchone() is not None

        return await asyncio.to_thread(restore)



    async def get_session_with_messages(self, session_id: str) -> dict | None:
        """Retrieve a student's conversation with its saved messages."""
        session = await self.get_session(session_id)

        if session is None:
            return None

        session["messages"] = await self.get_messages(session_id)
        session["active_turns"] = await self.list_active_turns(session_id)

        return session


    async def begin_turn(
        self,
        session_id: str,
        capability: str = "",
        *,
        turn_id: str | None = None,
        owner_id: str = "",
        fencing_token: int = 0,
        submission_id: str | None = None,
    ) -> dict:
        import asyncio
        import time
        import uuid

        from .protocol import (
            SUBMISSION_ASSISTANT_FIELD,
            SUBMISSION_PREVIOUS_TURN_FIELD,
            SUBMISSION_REPLAY_FIELD,
            SUBMISSION_USER_FIELD,
            ActiveTurnConflict,
        )

        def create():
            now = time.time()
            resolved_id = turn_id or f"turn_{int(now * 1000)}_{uuid.uuid4().hex[:10]}"
            replay_fields = {}

            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    # Serialize turn creation for this conversation.
                    cur.execute(
                        """
                        SELECT id FROM drchen_sessions
                        WHERE id = %s AND user_id = %s AND deleted_at IS NULL
                        FOR UPDATE
                        """,
                        (session_id, self.user_id),
                    )
                    if cur.fetchone() is None:
                        raise ValueError(f"Session not found: {session_id}")

                    if submission_id:
                        cur.execute(
                            """
                            SELECT session_id, turn_id
                            FROM drchen_turn_submissions
                            WHERE client_submission_id = %s
                            """,
                            (submission_id,),
                        )
                        reservation = cur.fetchone()

                        if reservation and reservation[0] != session_id:
                            raise RuntimeError(
                                "This submission belongs to another conversation."
                            )

                        if reservation and reservation[1]:
                            cur.execute(
                                """
                                SELECT id, status, assistant_message_id
                                FROM drchen_turns
                                WHERE id = %s AND session_id = %s
                                """,
                                (reservation[1], session_id),
                            )
                            old = cur.fetchone()

                            if old:
                                if old[1] not in {"failed", "cancelled"}:
                                    cur.execute(
                                        """
                                        SELECT id FROM drchen_turns
                                        WHERE id = %s
                                        """,
                                        (old[0],),
                                    )
                                    return {
                                        "id": old[0],
                                        "turn_id": old[0],
                                        "session_id": session_id,
                                        "status": old[1],
                                        SUBMISSION_REPLAY_FIELD: True,
                                    }

                                cur.execute(
                                    """
                                    SELECT id FROM drchen_messages
                                    WHERE session_id = %s
                                      AND role = 'user'
                                      AND metadata_json::jsonb
                                          ->> 'client_submission_id' = %s
                                    ORDER BY id LIMIT 1
                                    """,
                                    (session_id, submission_id),
                                )
                                user = cur.fetchone()
                                if user:
                                    replay_fields = {
                                        SUBMISSION_USER_FIELD: user[0],
                                        SUBMISSION_ASSISTANT_FIELD: old[2],
                                        SUBMISSION_PREVIOUS_TURN_FIELD: old[0],
                                    }

                    cur.execute(
                        """
                        SELECT id FROM drchen_turns
                        WHERE session_id = %s
                          AND status IN ('queued', 'running', 'waiting_input')
                        LIMIT 1
                        """,
                        (session_id,),
                    )
                    active = cur.fetchone()

                    if active:
                        raise ActiveTurnConflict(
                            f"Session already has an active turn: {active[0]}",
                            turn_id=str(active[0]),
                        )

                    cur.execute(
                        """
                        INSERT INTO drchen_turns (
                            id, session_id, capability, status, error,
                            created_at, updated_at, finished_at,
                            owner_id, fencing_token, state_version,
                            failure_code, retryable
                        )
                        VALUES (%s, %s, %s, 'running', '', %s, %s,
                                NULL, %s, %s, 1, '', FALSE)
                        """,
                        (
                            resolved_id,
                            session_id,
                            capability or "",
                            now,
                            now,
                            owner_id or "",
                            max(0, int(fencing_token)),
                        ),
                    )

                    if submission_id:
                        cur.execute(
                            """
                            UPDATE drchen_turn_submissions
                            SET turn_id = %s
                            WHERE client_submission_id = %s
                              AND session_id = %s
                            """,
                            (resolved_id, submission_id, session_id),
                        )

            return {
                **replay_fields,
                "id": resolved_id,
                "turn_id": resolved_id,
                "session_id": session_id,
                "capability": capability or "",
                "status": "running",
                "error": "",
                "created_at": now,
                "updated_at": now,
                "finished_at": None,
                "last_seq": 0,
                "owner_id": owner_id or "",
                "fencing_token": max(0, int(fencing_token)),
                "state_version": 1,
                "failure_code": "",
                "retryable": False,
                "assistant_message_id": None,
            }

        try:
            return await asyncio.to_thread(create)
        except Exception as exc:
            if "UniqueViolation" in type(exc).__name__:
                raise ActiveTurnConflict(
                    f"Session already has an active turn: {session_id}"
                ) from exc
            raise

    async def create_turn(
        self,
        session_id: str,
        capability: str = "",
        *,
        submission_id: str | None = None,
    ) -> dict:
        return await self.begin_turn(
            session_id, capability, submission_id=submission_id
        )

    async def get_turn(self, turn_id: str) -> dict | None:
        import asyncio

        def fetch():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id, t.session_id, t.capability, t.status,
                               t.error, t.created_at, t.updated_at,
                               t.finished_at, t.owner_id, t.fencing_token,
                               t.state_version, t.failure_code, t.retryable,
                               t.assistant_message_id,
                               COALESCE(
                                   (SELECT MAX(seq)
                                    FROM drchen_turn_events
                                    WHERE turn_id = t.id), 0
                               )
                        FROM drchen_turns t
                        JOIN drchen_sessions s ON s.id = t.session_id
                        WHERE t.id = %s AND s.user_id = %s
                        """,
                        (turn_id, self.user_id),
                    )
                    row = cur.fetchone()

            if row is None:
                return None

            keys = (
                "id", "session_id", "capability", "status", "error",
                "created_at", "updated_at", "finished_at", "owner_id",
                "fencing_token", "state_version", "failure_code",
                "retryable", "assistant_message_id", "last_seq",
            )
            result = dict(zip(keys, row))
            result["turn_id"] = result["id"]
            return result

        return await asyncio.to_thread(fetch)

    async def get_active_turn(self, session_id: str) -> dict | None:
        import asyncio

        def fetch():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id
                        FROM drchen_turns t
                        JOIN drchen_sessions s ON s.id = t.session_id
                        WHERE t.session_id = %s AND s.user_id = %s
                          AND t.status IN ('queued', 'running', 'waiting_input')
                        ORDER BY t.updated_at DESC
                        LIMIT 1
                        """,
                        (session_id, self.user_id),
                    )
                    row = cur.fetchone()
            return row[0] if row else None

        turn_id = await asyncio.to_thread(fetch)
        return await self.get_turn(turn_id) if turn_id else None

    async def list_active_turns(self, session_id: str) -> list[dict]:
        active = await self.get_active_turn(session_id)
        return [active] if active else []

    async def transition_turn(
        self,
        turn_id: str,
        status: str,
        *,
        expected_status: str | None = None,
        fencing_token: int | None = None,
        error: str = "",
        failure_code: str = "",
        retryable: bool = False,
    ) -> bool:
        import asyncio
        import time

        allowed = {
            "queued", "running", "waiting_input",
            "completed", "failed", "cancelled",
        }
        if status not in allowed:
            raise ValueError(f"Invalid turn status: {status}")

        def update():
            now = time.time()
            terminal = status in {"completed", "failed", "cancelled"}

            clauses = ["id = %s", "session_id IN (SELECT id FROM drchen_sessions WHERE user_id = %s)"]
            params = [status, error, now, now if terminal else None,
                      failure_code, retryable, turn_id, self.user_id]

            if expected_status is not None:
                clauses.append("status = %s")
                params.append(expected_status)

            if fencing_token is not None:
                clauses.append("fencing_token = %s")
                params.append(fencing_token)

            query = f"""
                UPDATE drchen_turns
                SET status = %s, error = %s, updated_at = %s,
                    finished_at = COALESCE(%s, finished_at),
                    failure_code = %s, retryable = %s,
                    state_version = state_version + 1
                WHERE {" AND ".join(clauses)}
                RETURNING id
            """

            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchone() is not None

        return await asyncio.to_thread(update)

    async def append_events(
        self,
        turn_id: str,
        events: list[dict],
        *,
        fencing_token: int | None = None,
    ) -> list[dict]:
        import asyncio
        import json
        import time

        def append():
            saved = []
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id
                        FROM drchen_turns t
                        JOIN drchen_sessions s ON s.id = t.session_id
                        WHERE t.id = %s AND s.user_id = %s
                        FOR UPDATE OF t
                        """,
                        (turn_id, self.user_id),
                    )
                    if cur.fetchone() is None:
                        raise PermissionError("Turn not found or access denied")

                    if fencing_token is not None:
                        cur.execute(
                            "SELECT fencing_token FROM drchen_turns WHERE id = %s",
                            (turn_id,),
                        )
                        if cur.fetchone()[0] != fencing_token:
                            raise RuntimeError("Turn fencing token mismatch")

                    cur.execute(
                        "SELECT COALESCE(MAX(seq), 0) FROM drchen_turn_events WHERE turn_id = %s",
                        (turn_id,),
                    )
                    seq = cur.fetchone()[0]

                    for event in events:
                        seq += 1
                        now = time.time()
                        item = {
                            "seq": seq,
                            "type": str(event.get("type") or "message"),
                            "source": str(event.get("source") or ""),
                            "stage": str(event.get("stage") or ""),
                            "content": str(event.get("content") or ""),
                            "metadata": event.get("metadata") or {},
                            "timestamp": event.get("timestamp") or now,
                            "created_at": now,
                        }
                        cur.execute(
                            """
                            INSERT INTO drchen_turn_events
                                (turn_id, seq, type, source, stage, content,
                                 metadata_json, timestamp, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                turn_id, seq, item["type"], item["source"],
                                item["stage"], item["content"],
                                json.dumps(item["metadata"]),
                                item["timestamp"], now,
                            ),
                        )
                        saved.append(item)
            return saved

        return await asyncio.to_thread(append)

    async def get_events(
        self, turn_id: str, after_seq: int = 0
    ) -> list[dict]:
        import asyncio
        import json

        def fetch():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT e.seq, e.type, e.source, e.stage, e.content,
                               e.metadata_json, e.timestamp, e.created_at
                        FROM drchen_turn_events e
                        JOIN drchen_turns t ON t.id = e.turn_id
                        JOIN drchen_sessions s ON s.id = t.session_id
                        WHERE e.turn_id = %s AND s.user_id = %s
                          AND e.seq > %s
                        ORDER BY e.seq
                        """,
                        (turn_id, self.user_id, after_seq),
                    )
                    rows = cur.fetchall()

            return [
                {
                    "seq": r[0], "type": r[1], "source": r[2],
                    "stage": r[3], "content": r[4],
                    "metadata": json.loads(r[5] or "{}"),
                    "timestamp": r[6], "created_at": r[7],
                }
                for r in rows
            ]

        return await asyncio.to_thread(fetch)


    async def link_turn_message(
        self,
        turn_id: str,
        assistant_message_id: int | str,
    ) -> bool:
        """Link an assistant message to its turn."""
        import asyncio

        def link():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE drchen_turns t
                        SET assistant_message_id = %s,
                            updated_at = EXTRACT(EPOCH FROM NOW())
                        FROM drchen_sessions s
                        WHERE t.session_id = s.id
                          AND t.id = %s
                          AND s.user_id = %s
                          AND s.deleted_at IS NULL
                          AND EXISTS (
                              SELECT 1
                              FROM drchen_messages m
                              WHERE m.id = %s
                                AND m.session_id = t.session_id
                          )
                        RETURNING t.id
                        """,
                        (
                            assistant_message_id,
                            turn_id,
                            self.user_id,
                            assistant_message_id,
                        ),
                    )
                    return cur.fetchone() is not None

        return await asyncio.to_thread(link)

    async def ensure_session(
        self,
        session_id: str | None = None,
    ) -> dict:
        """Return an existing student-owned session or create one."""
        if session_id:
            session = await self.get_session(session_id)
            if session is not None:
                return session

        return await self.create_session()

    async def update_turn_status(
        self,
        turn_id: str,
        status: str,
        error: str = "",
    ) -> bool:
        """Update a turn's status."""
        return await self.transition_turn(
            turn_id,
            status,
            error=error,
        )




    async def get_messages_for_context(
        self,
        session_id: str,
        leaf_message_id: int | None = None,
    ) -> list[dict]:
        """Load student-owned conversation history for AI context."""
        import asyncio
        import json

        def parse_json(value, default):
            if value is None:
                return default
            if isinstance(value, (dict, list)):
                return value
            return json.loads(value)

        def load():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT m.id, m.role, m.content,
                               m.events_json, m.metadata_json,
                               m.parent_message_id
                        FROM drchen_messages m
                        JOIN drchen_sessions s
                          ON s.id = m.session_id
                        WHERE s.id = %s
                          AND s.user_id = %s
                          AND s.deleted_at IS NULL
                          AND m.role IN ('user', 'assistant', 'system')
                        ORDER BY m.id ASC
                        """,
                        (session_id, self.user_id),
                    )
                    rows = cur.fetchall()

            messages = {
                row[0]: {
                    "id": row[0],
                    "role": row[1],
                    "content": row[2] or "",
                    "events": parse_json(row[3], []),
                    "metadata": parse_json(row[4], {}),
                    "parent_message_id": row[5],
                }
                for row in rows
            }

            if leaf_message_id is None:
                selected = list(messages.values())
            else:
                selected = []
                current = leaf_message_id
                visited = set()

                while current is not None and current not in visited:
                    visited.add(current)
                    message = messages.get(current)
                    if message is None:
                        break
                    selected.append(message)
                    current = message["parent_message_id"]

                selected.reverse()

            return [
                {
                    "id": message["id"],
                    "role": message["role"],
                    "content": message["content"],
                    "events": message["events"],
                    "metadata": message["metadata"],
                }
                for message in selected
            ]

        return await asyncio.to_thread(load)





    async def update_session_preferences(
        self,
        session_id: str,
        preferences: dict,
        *,
        touch: bool = True,
    ) -> bool:
        """Merge preferences for a student-owned conversation."""
        import asyncio
        import json
        import time

        def update():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT preferences_json
                        FROM drchen_sessions
                        WHERE id = %s
                          AND user_id = %s
                          AND deleted_at IS NULL
                        FOR UPDATE
                        """,
                        (session_id, self.user_id),
                    )
                    row = cur.fetchone()

                    if row is None:
                        return False

                    current = row[0] or {}
                    if isinstance(current, str):
                        current = json.loads(current)

                    merged = {
                        **current,
                        **(preferences or {}),
                    }

                    cur.execute(
                        """
                        UPDATE drchen_sessions
                        SET preferences_json = %s,
                            updated_at = CASE
                                WHEN %s THEN %s
                                ELSE updated_at
                            END
                        WHERE id = %s
                          AND user_id = %s
                          AND deleted_at IS NULL
                        """,
                        (
                            json.dumps(merged),
                            touch,
                            time.time(),
                            session_id,
                            self.user_id,
                        ),
                    )

                    return cur.rowcount > 0

        return await asyncio.to_thread(update)





    async def list_orphaned_failed_turns(
        self,
        session_id: str,
    ) -> list[dict]:
        """Find failed turns without an assistant message."""
        import asyncio

        def load():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id
                        FROM drchen_turns AS t
                        JOIN drchen_sessions AS s
                          ON s.id = t.session_id
                        WHERE t.session_id = %s
                          AND s.user_id = %s
                          AND s.deleted_at IS NULL
                          AND t.status = 'failed'
                          AND t.assistant_message_id IS NULL
                        ORDER BY t.created_at, t.id
                        """,
                        (session_id, self.user_id),
                    )
                    return [row[0] for row in cur.fetchall()]

        turn_ids = await asyncio.to_thread(load)
        results = []

        for turn_id in turn_ids:
            turn = await self.get_turn(turn_id)
            if turn is not None:
                results.append(turn)

        return results




    async def append_turn_event(
        self, turn_id: str, event: dict
    ) -> dict:
        events = await self.append_turn_events(turn_id, [event])
        return events[0]

    async def append_turn_events(
        self, turn_id: str, events: list[dict]
    ) -> list[dict]:
        saved = await self.append_events(turn_id, events)
        turn = await self.get_turn(turn_id)
        if turn is None:
            raise ValueError(f"Turn not found: {turn_id}")

        return [
            {
                **item,
                "turn_id": turn_id,
                "session_id": turn["session_id"],
            }
            for item in saved
        ]


    async def get_message_trace(
        self,
        session_id: str,
        message_id: int | str,
        after_seq: int = 0,
        limit: int | None = None,
    ) -> dict | None:
        """Retrieve AI response events for a student's message."""
        import asyncio

        try:
            mid = int(message_id)
        except (TypeError, ValueError):
            return None

        def find_turn():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id
                        FROM drchen_messages m
                        JOIN drchen_sessions s ON s.id = m.session_id
                        LEFT JOIN drchen_turns t
                          ON t.assistant_message_id = m.id
                         AND t.session_id = m.session_id
                        WHERE m.id = %s
                          AND m.session_id = %s
                          AND s.user_id = %s
                          AND s.deleted_at IS NULL
                        """,
                        (mid, session_id, self.user_id),
                    )
                    row = cur.fetchone()
                    return None if row is None else row[0]

        if await self.get_session(session_id) is None:
            return None

        turn_id = await asyncio.to_thread(find_turn)

        if turn_id is None:
            messages = await self.get_messages(session_id)
            if not any(int(m.get("id", -1)) == mid for m in messages):
                return None
            return {
                "session_id": session_id,
                "message_id": mid,
                "turn_id": None,
                "events": [],
                "total": 0,
                "last_seq": 0,
                "next_seq": None,
                "complete": True,
            }

        all_events = await self.get_turn_events(turn_id, 0)
        total = len(all_events)
        last_seq = max((int(e["seq"]) for e in all_events), default=0)

        page_size = 500 if limit is None else min(1000, max(1, int(limit)))
        events = [
            e for e in all_events
            if int(e["seq"]) > max(0, int(after_seq))
        ][:page_size]

        last_loaded = int(events[-1]["seq"]) if events else int(after_seq)
        complete = last_loaded >= last_seq

        return {
            "session_id": session_id,
            "message_id": mid,
            "turn_id": turn_id,
            "events": events,
            "total": total,
            "last_seq": last_seq,
            "next_seq": None if complete else last_loaded,
            "complete": complete,
        }

    async def get_turn_events(
        self, turn_id: str, after_seq: int = 0
    ) -> list[dict]:
        events = await self.get_events(turn_id, after_seq)
        turn = await self.get_turn(turn_id)
        if turn is None:
            return []

        return [
            {
                **item,
                "turn_id": turn_id,
                "session_id": turn["session_id"],
            }
            for item in events
        ]

    async def migrate_workspace_preferences(self) -> int:
        """No SQLite legacy preferences to migrate in PostgreSQL."""
        return 0
    async def list_nonterminal_turns(self) -> list[dict]:
        """Return unfinished turns belonging to this student."""
        import asyncio

        def load():
            with connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id
                        FROM drchen_turns AS t
                        JOIN drchen_sessions AS s
                          ON s.id = t.session_id
                        WHERE s.user_id = %s
                          AND s.deleted_at IS NULL
                          AND t.status IN (
                              'queued', 'running', 'waiting_input'
                          )
                        ORDER BY t.created_at, t.id
                        """,
                        (self.user_id,),
                    )
                    return [row[0] for row in cur.fetchall()]

        turn_ids = await asyncio.to_thread(load)
        results = []

        for turn_id in turn_ids:
            turn = await self.get_turn(turn_id)
            if turn is not None:
                results.append(turn)

        return results
    async def get_last_message(
        self, session_id: str, role: str | None = None
    ) -> dict | None:
        """Return the latest message in a student's session."""

        messages = await self.get_messages(session_id)

        if role is not None:
            messages = [
                message
                for message in messages
                if message.get("role") == role
            ]

        return messages[-1] if messages else None
