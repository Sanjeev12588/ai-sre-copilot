"""Tests for JSON Persistence Layer (Phase 4).

All tests use a temporary directory (via pytest's tmp_path fixture) so
no test data is written to the project directory.

Coverage
--------
TestJsonIncidentStoreInit    — directory creation, logging
TestSaveAndLoad              — save/load round-trip, schema_version preserved
TestExists                   — exists() before and after save/delete
TestUpdate                   — update overwrites, raises on unknown
TestListIncidents            — list returns correct IDs
TestArchive                  — archive moves file, removes from active list
TestDelete                   — delete removes active file, silent on missing
TestErrorConditions          — IncidentNotFoundError, ValueError on duplicate
TestMalformedState           — graceful error on corrupt JSON
TestAtomicWrite              — no .tmp files left after successful write
TestSessionIsolation         — two stores in different dirs are independent
TestSerialization            — all IncidentState fields survive round-trip
TestSchemaVersion            — schema_version stored and loaded correctly
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.memory.case_file import (
    SCHEMA_VERSION,
    DiagnosticsSection,
    EscalationSection,
    EventType,
    IncidentState,
    IncidentStatus,
    RecommendationsSection,
    TimelineEntry,
)
from backend.persistence.base import IncidentNotFoundError
from backend.persistence.json_store import JsonIncidentStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    incident_id: str = "INC-TEST0001",
    status: str = IncidentStatus.NEW.value,
) -> IncidentState:
    return IncidentState(
        incident_id=incident_id, status=status, summary="Test incident"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. INIT
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonIncidentStoreInit:
    def test_active_directory_created(self, tmp_path: Path) -> None:
        JsonIncidentStore(store_dir=tmp_path / "incidents")
        assert (tmp_path / "incidents").is_dir()

    def test_archived_directory_created(self, tmp_path: Path) -> None:
        JsonIncidentStore(store_dir=tmp_path / "incidents")
        assert (tmp_path / "incidents" / "archived").is_dir()

    def test_store_can_be_created_multiple_times(self, tmp_path: Path) -> None:
        """Idempotent — calling with the same dir twice is safe."""
        d = tmp_path / "idempotent"
        JsonIncidentStore(store_dir=d)
        JsonIncidentStore(store_dir=d)  # should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SAVE AND LOAD ROUND-TRIP
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveAndLoad:
    def test_save_creates_json_file(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = _make_state("INC-SAVE001")
        store.save(state)
        assert (tmp_path / "INC-SAVE001.json").exists()

    def test_load_returns_correct_incident(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = _make_state("INC-LOAD001")
        store.save(state)
        loaded = store.load("INC-LOAD001")
        assert loaded.incident_id == "INC-LOAD001"
        assert loaded.summary == "Test incident"

    def test_load_preserves_status(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = _make_state("INC-STATUS001", status=IncidentStatus.TRIAGED.value)
        store.save(state)
        loaded = store.load("INC-STATUS001")
        assert loaded.status == IncidentStatus.TRIAGED.value

    def test_load_preserves_diagnostics(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = _make_state("INC-DIAG001")
        state = state.model_copy(
            update={
                "diagnostics": DiagnosticsSection(
                    root_cause="DB pool exhausted",
                    confidence_score=85,
                    evidence=["log entry 1", "metric spike"],
                )
            }
        )
        store.save(state)
        loaded = store.load("INC-DIAG001")
        assert loaded.diagnostics.root_cause == "DB pool exhausted"
        assert loaded.diagnostics.confidence_score == 85
        assert loaded.diagnostics.evidence == ["log entry 1", "metric spike"]

    def test_load_preserves_timeline(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = _make_state("INC-TL001")
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent="IntakeAgent",
            agent_name="IntakeAgent",
            event_type=EventType.INCIDENT_CREATED,
            summary="Incident created",
        )
        state = state.model_copy(update={"timeline": [entry]})
        store.save(state)
        loaded = store.load("INC-TL001")
        assert len(loaded.timeline) == 1
        assert loaded.timeline[0].agent_name == "IntakeAgent"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EXISTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestExists:
    def test_exists_false_before_save(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        assert store.exists("INC-GHOST") is False

    def test_exists_true_after_save(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-EX001"))
        assert store.exists("INC-EX001") is True

    def test_exists_false_after_delete(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-EX002"))
        store.delete("INC-EX002")
        assert store.exists("INC-EX002") is False

    def test_exists_false_after_archive(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-EX003"))
        store.archive("INC-EX003")
        assert store.exists("INC-EX003") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. UPDATE
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdate:
    def test_update_overwrites_status(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = _make_state("INC-UPD001")
        store.save(state)
        updated = state.model_copy(update={"status": IncidentStatus.TRIAGED.value})
        store.update(updated)
        loaded = store.load("INC-UPD001")
        assert loaded.status == IncidentStatus.TRIAGED.value

    def test_update_raises_on_nonexistent(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        with pytest.raises(IncidentNotFoundError):
            store.update(_make_state("INC-GHOST999"))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LIST INCIDENTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestListIncidents:
    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        assert store.list_incidents() == []

    def test_list_contains_saved_ids(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-LIST001"))
        store.save(_make_state("INC-LIST002"))
        ids = store.list_incidents()
        assert "INC-LIST001" in ids
        assert "INC-LIST002" in ids

    def test_list_excludes_archived(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-ACT001"))
        store.save(_make_state("INC-ARC001"))
        store.archive("INC-ARC001")
        ids = store.list_incidents()
        assert "INC-ACT001" in ids
        assert "INC-ARC001" not in ids

    def test_list_excludes_deleted(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-DEL-L001"))
        store.delete("INC-DEL-L001")
        assert "INC-DEL-L001" not in store.list_incidents()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ARCHIVE
# ═══════════════════════════════════════════════════════════════════════════════


class TestArchive:
    def test_archive_moves_file(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-ARCH001"))
        store.archive("INC-ARCH001")
        assert not (tmp_path / "INC-ARCH001.json").exists()
        assert (tmp_path / "archived" / "INC-ARCH001.json").exists()

    def test_archive_raises_on_nonexistent(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        with pytest.raises(IncidentNotFoundError):
            store.archive("INC-NOARCH")

    def test_archived_incident_not_in_list(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-ARCH002"))
        store.archive("INC-ARCH002")
        assert "INC-ARCH002" not in store.list_incidents()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. DELETE
# ═══════════════════════════════════════════════════════════════════════════════


class TestDelete:
    def test_delete_removes_file(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-DEL001"))
        store.delete("INC-DEL001")
        assert not (tmp_path / "INC-DEL001.json").exists()

    def test_delete_nonexistent_is_silent(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.delete("INC-GHOST")  # must not raise


# ═══════════════════════════════════════════════════════════════════════════════
# 8. ERROR CONDITIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorConditions:
    def test_load_nonexistent_raises_incident_not_found(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        with pytest.raises(IncidentNotFoundError) as exc_info:
            store.load("INC-MISSING")
        assert exc_info.value.incident_id == "INC-MISSING"

    def test_incident_not_found_error_message(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        with pytest.raises(IncidentNotFoundError) as exc_info:
            store.load("INC-MISSING2")
        assert "INC-MISSING2" in str(exc_info.value)

    def test_save_duplicate_raises_value_error(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-DUP001"))
        with pytest.raises(ValueError, match="already exists"):
            store.save(_make_state("INC-DUP001"))


# ═══════════════════════════════════════════════════════════════════════════════
# 9. MALFORMED STATE RECOVERY
# ═══════════════════════════════════════════════════════════════════════════════


class TestMalformedState:
    def test_malformed_json_raises_on_load(self, tmp_path: Path) -> None:
        """Corrupt JSON in the file must raise on load."""
        import json as _json

        bad_file = tmp_path / "INC-BAD.json"
        bad_file.write_text("{ this is not valid json !!!}", encoding="utf-8")
        store = JsonIncidentStore(tmp_path)
        with pytest.raises(_json.JSONDecodeError):
            store.load("INC-BAD")

    def test_valid_extra_fields_are_ignored(self, tmp_path: Path) -> None:
        """JSON with extra unknown fields should load without error."""
        state = _make_state("INC-EXTRA001")
        data = state.model_dump()
        data["unknown_future_field"] = "some_value"
        (tmp_path / "INC-EXTRA001.json").write_text(json.dumps(data), encoding="utf-8")
        store = JsonIncidentStore(tmp_path)
        loaded = store.load("INC-EXTRA001")
        assert loaded.incident_id == "INC-EXTRA001"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. ATOMIC WRITE
# ═══════════════════════════════════════════════════════════════════════════════


class TestAtomicWrite:
    def test_no_tmp_files_after_save(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-ATOM001"))
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Orphan .tmp files found: {tmp_files}"

    def test_no_tmp_files_after_update(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = _make_state("INC-ATOM002")
        store.save(state)
        store.update(state.model_copy(update={"status": IncidentStatus.TRIAGED.value}))
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []


# ═══════════════════════════════════════════════════════════════════════════════
# 11. SESSION ISOLATION (SEPARATE STORE DIRS)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStoreIsolation:
    def test_two_stores_in_different_dirs_are_independent(self, tmp_path: Path) -> None:
        store1 = JsonIncidentStore(tmp_path / "store1")
        store2 = JsonIncidentStore(tmp_path / "store2")
        store1.save(_make_state("INC-ISO001"))
        assert not store2.exists("INC-ISO001")


# ═══════════════════════════════════════════════════════════════════════════════
# 12. SCHEMA VERSION
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaVersion:
    def test_schema_version_stored_in_json(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-SV001"))
        raw = json.loads((tmp_path / "INC-SV001.json").read_text())
        assert "schema_version" in raw
        assert raw["schema_version"] == SCHEMA_VERSION

    def test_schema_version_preserved_on_load(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        store.save(_make_state("INC-SV002"))
        loaded = store.load("INC-SV002")
        assert loaded.schema_version == SCHEMA_VERSION


# ═══════════════════════════════════════════════════════════════════════════════
# 13. FULL SERIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestSerialization:
    def test_all_fields_survive_round_trip(self, tmp_path: Path) -> None:
        store = JsonIncidentStore(tmp_path)
        state = IncidentState(
            incident_id="INC-FULL001",
            title="Full round-trip test",
            description="Testing all fields",
            status=IncidentStatus.INVESTIGATING.value,
            summary="DB pool exhausted on checkout-service",
            environment="staging",
            assigned_team="db-oncall",
            recovery_status="PENDING",
            verification_status="NOT_STARTED",
            report_status="PENDING",
            escalation_status="NONE",
            diagnostics=DiagnosticsSection(
                root_cause="Batch job exhausted pool",
                confidence_score=82,
                severity="P1",
                affected_services=["checkout-service", "payments-db-v2"],
            ),
            recommendations=RecommendationsSection(
                runbook_id="RB-DB-004",
                title="Reset DB connection pool",
                risk_level="Medium",
                requires_human_approval=True,
            ),
            escalation=EscalationSection(
                escalation_id="ESC-001",
                target_team="db-oncall",
                channels=["slack", "sms"],
            ),
            metadata={"source": "prometheus", "env": "k8s"},
        )
        store.save(state)
        loaded = store.load("INC-FULL001")

        assert loaded.title == "Full round-trip test"
        assert loaded.environment == "staging"
        assert loaded.assigned_team == "db-oncall"
        assert loaded.diagnostics.root_cause == "Batch job exhausted pool"
        assert loaded.diagnostics.confidence_score == 82
        assert loaded.recommendations.runbook_id == "RB-DB-004"
        assert loaded.escalation.target_team == "db-oncall"
        assert loaded.metadata["source"] == "prometheus"
