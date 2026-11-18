from __future__ import annotations

import asyncio

import pytest

from deeptutor.services.session import postgres_store as module


class FakeCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])
        self.calls = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, params))

    def fetchone(self):
        if self.fetchone_values:
            return self.fetchone_values.pop(0)
        return None

    def fetchall(self):
        if self.fetchall_values:
            return self.fetchall_values.pop(0)
        return []


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        pass


def run(coro):
    return asyncio.run(coro)


def patch_connection(monkeypatch, cursor):
    conn = FakeConnection(cursor)
    monkeypatch.setattr(module, "connect_postgres", lambda: conn)


def test_delete_message_is_owner_scoped(monkeypatch):
    cursor = FakeCursor(
        fetchone_values=[("session-1",), (17,)],
        fetchall_values=[[]],
    )
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    assert run(store.delete_message("17")) is True

    assert "JOIN drchen_sessions s ON s.id = m.session_id" in cursor.calls[0][0]
    assert cursor.calls[0][1] == (17, "alice")
    assert cursor.calls[1][1] == (17, "session-1")


def test_get_message_role_is_owner_scoped(monkeypatch):
    cursor = FakeCursor(fetchone_values=[("assistant",)])
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    assert run(store.get_message_role("session-1", "22")) == "assistant"
    assert cursor.calls[0][1] == (22, "session-1", "alice")
    assert "s.user_id = %s" in cursor.calls[0][0]


def test_get_session_summaries_is_owner_scoped_and_deduplicates(monkeypatch):
    cursor = FakeCursor(fetchall_values=[[{
        "id": "session-1",
        "title": "One",
        "created_at": 1.0,
        "updated_at": 2.0,
        "compressed_summary": "",
        "summary_up_to_msg_id": 0,
        "preferences_json": '{"workspace_id":"w1"}',
        "message_count": 2,
        "status": "idle",
        "active_turn_id": "",
        "capability": "",
        "last_message": "answer",
    }]])
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    summaries = run(store.get_session_summaries(["session-1", "session-1"]))

    assert summaries[0]["session_id"] == "session-1"
    assert summaries[0]["preferences"] == {"workspace_id": "w1"}
    assert cursor.calls[0][1] == (["session-1"], "alice")


def test_search_sessions_uses_literal_position_and_owner(monkeypatch):
    cursor = FakeCursor(fetchone_values=[(1,),], fetchall_values=[[]])
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    result = run(store.search_sessions("100%_literal", limit=10, offset=0))

    assert result == {"sessions": [], "total": 1}
    assert cursor.calls[0][1] == ("alice", "100%_literal", "100%_literal")
    assert "STRPOS(" in cursor.calls[0][0]


def test_import_legacy_session_does_not_cross_owner(monkeypatch):
    cursor = FakeCursor(fetchone_values=[('{"import":{"source":"x"}}',), None])
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    result = run(store.import_legacy_session(
        "imported_x_1", "Imported", 1.0, 2.0,
        {"import": {"source": "x"}}, [],
    ))

    assert result["imported"] is False
    assert cursor.calls[1][1] == ("imported_x_1", "alice")


def test_update_session_preferences_if_unset_checks_and_merges(monkeypatch):
    cursor = FakeCursor(fetchone_values=[('{"old":true}',)])
    cursor.rowcount = 1
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    assert run(store.update_session_preferences_if_unset(
        "session-1", {"parent_session_id": "parent"}, unset=("parent_session_id",)
    )) is True

    params = cursor.calls[1][1]
    assert params[-2:] == ("session-1", "alice")
    assert '"parent_session_id": "parent"' in params[0]


def test_update_summary_is_owner_scoped(monkeypatch):
    cursor = FakeCursor(fetchone_values=[("session-1",)])
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    assert run(store.update_summary("session-1", "Summary", "7")) is True
    assert cursor.calls[0][1] == ("Summary", 7, "session-1", "alice")


def test_usage_records_is_owner_scoped(monkeypatch):
    cursor = FakeCursor(fetchall_values=[[
        (31, "session-1", 123.0, "[]", '{}', None, None, None)
    ]])
    patch_connection(monkeypatch, cursor)

    store = module.PostgresSessionStore("alice")
    records = run(store.usage_records(100.0, 200.0))

    assert records == [{
        "session_id": "session-1",
        "turn_id": None,
        "created_at": 123.0,
        "summaries": [],
    }]
    assert cursor.calls[0][1] == (100.0, 200.0, "alice")
