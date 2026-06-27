"""Tests for Session Memory — MemoryStore interface + InMemoryStore (Phase 4).

Coverage
--------
TestMemoryStoreInterface  — ABC cannot be instantiated directly
TestInMemoryStoreBasic    — CRUD operations: create, get, update, delete
TestSessionIsolation      — multiple sessions do not bleed state
TestSessionContext        — agent output, tool call, decision recording
TestExistsMethod          — exists() returns correct bool
TestConcurrency           — thread-safe concurrent create/update/delete
TestErrorHandling         — KeyError on duplicate create, missing update
TestConvenienceHelpers    — record_agent_output and record_tool_call wrappers
"""

from __future__ import annotations

import threading

import pytest

from backend.memory.case_file import IncidentState, IncidentStatus
from backend.memory.session import InMemoryStore, MemoryStore, SessionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(incident_id: str = "INC-TEST0001", status: str = "NEW") -> IncidentState:
    return IncidentState(incident_id=incident_id, status=status)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ABSTRACT INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════


class TestMemoryStoreInterface:
    """MemoryStore is abstract — cannot be instantiated."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        with pytest.raises(TypeError):
            MemoryStore()  # type: ignore[abstract]

    def test_in_memory_store_is_memory_store(self) -> None:
        store = InMemoryStore()
        assert isinstance(store, MemoryStore)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BASIC CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestInMemoryStoreBasic:
    """Core CRUD operations work correctly."""

    def setup_method(self) -> None:
        self.store = InMemoryStore()

    def test_create_and_get(self) -> None:
        state = _state("INC-CRUD001")
        self.store.create_session("sess-1", state)
        retrieved = self.store.get("sess-1")
        assert retrieved is not None
        assert retrieved.incident_id == "INC-CRUD001"

    def test_get_unknown_session_returns_none(self) -> None:
        assert self.store.get("nonexistent-session") is None

    def test_update_state(self) -> None:
        state = _state("INC-UPD001")
        self.store.create_session("sess-upd", state)
        updated = state.model_copy(update={"status": IncidentStatus.TRIAGED.value})
        self.store.update("sess-upd", updated)
        retrieved = self.store.get("sess-upd")
        assert retrieved.status == IncidentStatus.TRIAGED.value

    def test_delete_session(self) -> None:
        self.store.create_session("sess-del", _state())
        self.store.delete("sess-del")
        assert self.store.get("sess-del") is None

    def test_delete_nonexistent_is_silent(self) -> None:
        # Should not raise
        self.store.delete("never-existed")

    def test_list_sessions(self) -> None:
        self.store.create_session("sess-a", _state("INC-A"))
        self.store.create_session("sess-b", _state("INC-B"))
        sessions = self.store.list_sessions()
        assert "sess-a" in sessions
        assert "sess-b" in sessions

    def test_list_sessions_empty(self) -> None:
        assert self.store.list_sessions() == []

    def test_session_count(self) -> None:
        self.store.create_session("s1", _state("INC-C1"))
        self.store.create_session("s2", _state("INC-C2"))
        assert self.store.session_count() == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SESSION ISOLATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionIsolation:
    """Multiple sessions must not bleed state into each other."""

    def setup_method(self) -> None:
        self.store = InMemoryStore()

    def test_separate_sessions_hold_separate_states(self) -> None:
        s1 = _state("INC-ISO001", status="NEW")
        s2 = _state("INC-ISO002", status="TRIAGED")
        self.store.create_session("iso-sess-1", s1)
        self.store.create_session("iso-sess-2", s2)

        assert self.store.get("iso-sess-1").status == "NEW"
        assert self.store.get("iso-sess-2").status == "TRIAGED"

    def test_updating_session1_does_not_affect_session2(self) -> None:
        self.store.create_session("iso-a", _state("INC-ISOA"))
        self.store.create_session("iso-b", _state("INC-ISOB"))

        updated = _state("INC-ISOA", status="INVESTIGATING")
        self.store.update("iso-a", updated)

        assert self.store.get("iso-b").status == "NEW"

    def test_deleting_session1_leaves_session2_intact(self) -> None:
        self.store.create_session("iso-del-a", _state("INC-DELA"))
        self.store.create_session("iso-del-b", _state("INC-DELB"))
        self.store.delete("iso-del-a")

        assert self.store.get("iso-del-b") is not None

    def test_two_stores_are_fully_independent(self) -> None:
        """Two InMemoryStore instances share no state."""
        store1 = InMemoryStore()
        store2 = InMemoryStore()

        store1.create_session("shared-key", _state("INC-S1"))
        assert store2.get("shared-key") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SESSION CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionContext:
    """SessionContext correctly records agent outputs, tool calls, decisions."""

    def setup_method(self) -> None:
        self.store = InMemoryStore()
        self.store.create_session("ctx-sess", _state("INC-CTX001"))

    def test_get_context_returns_session_context(self) -> None:
        ctx = self.store.get_context("ctx-sess")
        assert isinstance(ctx, SessionContext)

    def test_get_context_unknown_returns_none(self) -> None:
        assert self.store.get_context("no-such-session") is None

    def test_record_agent_output(self) -> None:
        ctx = self.store.get_context("ctx-sess")
        ctx.record_agent_output("IntakeAgent", {"incident_id": "INC-CTX001"})
        assert "IntakeAgent" in ctx.agent_outputs
        assert ctx.agent_outputs["IntakeAgent"]["incident_id"] == "INC-CTX001"

    def test_record_tool_call(self) -> None:
        ctx = self.store.get_context("ctx-sess")
        ctx.record_tool_call(
            agent="TriageAgent",
            tool="get_alerts",
            args={},
            result=[{"alert_id": "ALT-001"}],
        )
        assert len(ctx.tool_call_history) == 1
        assert ctx.tool_call_history[0]["tool"] == "get_alerts"

    def test_record_decision(self) -> None:
        ctx = self.store.get_context("ctx-sess")
        ctx.record_decision("Escalating to P1 based on blast radius")
        assert len(ctx.decision_log) == 1
        assert "P1" in ctx.decision_log[0]

    def test_summary_is_dict(self) -> None:
        ctx = self.store.get_context("ctx-sess")
        summary = ctx.summary()
        assert isinstance(summary, dict)
        assert "session_id" in summary
        assert "incident_id" in summary

    def test_context_timestamps_are_set(self) -> None:
        ctx = self.store.get_context("ctx-sess")
        assert ctx.created_at != ""
        assert ctx.updated_at != ""


# ═══════════════════════════════════════════════════════════════════════════════
# 5. EXISTS METHOD
# ═══════════════════════════════════════════════════════════════════════════════


class TestExistsMethod:
    """exists() returns True/False correctly without deserializing state."""

    def setup_method(self) -> None:
        self.store = InMemoryStore()

    def test_exists_true_after_create(self) -> None:
        self.store.create_session("exists-test", _state())
        assert self.store.exists("exists-test") is True

    def test_exists_false_for_unknown(self) -> None:
        assert self.store.exists("ghost-session") is False

    def test_exists_false_after_delete(self) -> None:
        self.store.create_session("ephemeral", _state())
        self.store.delete("ephemeral")
        assert self.store.exists("ephemeral") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Error conditions raise the correct exceptions."""

    def setup_method(self) -> None:
        self.store = InMemoryStore()

    def test_create_duplicate_raises_key_error(self) -> None:
        self.store.create_session("dup-sess", _state())
        with pytest.raises(KeyError, match="already exists"):
            self.store.create_session("dup-sess", _state())

    def test_update_nonexistent_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="not found"):
            self.store.update("ghost", _state())


# ═══════════════════════════════════════════════════════════════════════════════
# 7. THREAD SAFETY
# ═══════════════════════════════════════════════════════════════════════════════


class TestConcurrency:
    """InMemoryStore is thread-safe under concurrent access."""

    def test_concurrent_creates_are_safe(self) -> None:
        store = InMemoryStore()
        errors: list[Exception] = []

        def create_session(i: int) -> None:
            try:
                store.create_session(f"thread-{i}", _state(f"INC-TH{i:03d}"))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=create_session, args=(i,)) for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert store.session_count() == 20

    def test_concurrent_reads_are_safe(self) -> None:
        store = InMemoryStore()
        store.create_session("shared-read", _state("INC-READ"))
        results: list[IncidentState | None] = []
        lock = threading.Lock()

        def read() -> None:
            state = store.get("shared-read")
            with lock:
                results.append(state)

        threads = [threading.Thread(target=read) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is not None for r in results)
        assert len(results) == 10


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CONVENIENCE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConvenienceHelpers:
    """InMemoryStore convenience wrappers delegate to SessionContext correctly."""

    def setup_method(self) -> None:
        self.store = InMemoryStore()
        self.store.create_session("helper-sess", _state("INC-HELP"))

    def test_record_agent_output_via_store(self) -> None:
        self.store.record_agent_output(
            "helper-sess", "RootCauseAgent", "DB pool exhausted"
        )
        ctx = self.store.get_context("helper-sess")
        assert ctx.agent_outputs["RootCauseAgent"] == "DB pool exhausted"

    def test_record_tool_call_via_store(self) -> None:
        self.store.record_tool_call(
            "helper-sess",
            agent="LogAnalyzerAgent",
            tool="query_logs",
            args={"service": "checkout-service"},
            result=[],
        )
        ctx = self.store.get_context("helper-sess")
        assert len(ctx.tool_call_history) == 1
        assert ctx.tool_call_history[0]["tool"] == "query_logs"

    def test_record_on_nonexistent_session_is_silent(self) -> None:
        """Convenience helpers should not crash on missing sessions."""
        # Should not raise
        self.store.record_agent_output("no-session", "Agent", "output")
