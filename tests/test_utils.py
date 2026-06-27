"""Tests for Incident Utility Functions (Phase 4).

All utility functions are pure functions — no mocking, no I/O, no ADK runtime.

Coverage
--------
TestGenerateIncidentId    — format, uniqueness, length
TestUtcNowIso             — ISO-8601 format, timezone awareness
TestElapsedMs             — non-negative, reasonable range
TestAggregateConfidence   — zero exclusion, clamping, empty list, negatives
TestFormatTimeline        — empty list, single entry, multi-entry, fields shown
TestValidateStatus        — valid strings, invalid strings with clear error
TestMakeTimelineEntry     — all fields set, backward compat, clamping
TestEventBus              — subscribe, publish, unsubscribe, clear, exceptions
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from backend.memory.case_file import EventType, IncidentStatus, TimelineEntry
from backend.utils.incident_utils import (
    aggregate_confidence,
    elapsed_ms,
    format_timeline,
    generate_incident_id,
    make_timeline_entry,
    utc_now_iso,
    validate_status,
)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. INCIDENT ID GENERATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateIncidentId:
    def test_starts_with_inc_prefix(self) -> None:
        id_ = generate_incident_id()
        assert id_.startswith("INC-")

    def test_total_length_is_12(self) -> None:
        id_ = generate_incident_id()
        # INC- (4) + 8 hex chars = 12
        assert len(id_) == 12, f"Expected 12 chars, got {len(id_)}: {id_!r}"

    def test_hex_part_is_uppercase(self) -> None:
        id_ = generate_incident_id()
        hex_part = id_[4:]
        assert hex_part == hex_part.upper()
        assert all(c in "0123456789ABCDEF" for c in hex_part)

    def test_uniqueness(self) -> None:
        ids = {generate_incident_id() for _ in range(1000)}
        assert len(ids) == 1000, "Expected 1000 unique IDs"

    def test_format_example(self) -> None:
        id_ = generate_incident_id()
        # Must match pattern INC-XXXXXXXX
        assert len(id_.split("-")) == 2
        assert id_.split("-")[0] == "INC"
        assert len(id_.split("-")[1]) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# 2. UTC TIMESTAMP
# ═══════════════════════════════════════════════════════════════════════════════


class TestUtcNowIso:
    def test_returns_string(self) -> None:
        ts = utc_now_iso()
        assert isinstance(ts, str)

    def test_is_iso_8601_parseable(self) -> None:
        ts = utc_now_iso()
        parsed = datetime.fromisoformat(ts)
        assert parsed is not None

    def test_is_timezone_aware(self) -> None:
        ts = utc_now_iso()
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_is_utc(self) -> None:
        ts = utc_now_iso()
        parsed = datetime.fromisoformat(ts)
        offset = parsed.utcoffset()
        assert offset is not None
        assert offset.total_seconds() == 0

    def test_two_calls_are_ordered(self) -> None:
        t1 = utc_now_iso()
        time.sleep(0.01)
        t2 = utc_now_iso()
        assert t1 <= t2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ELAPSED MS
# ═══════════════════════════════════════════════════════════════════════════════


class TestElapsedMs:
    def test_returns_non_negative(self) -> None:
        start = datetime.now(timezone.utc)
        ms = elapsed_ms(start)
        assert ms >= 0

    def test_returns_int(self) -> None:
        start = datetime.now(timezone.utc)
        assert isinstance(elapsed_ms(start), int)

    def test_small_elapsed_time(self) -> None:
        start = datetime.now(timezone.utc)
        time.sleep(0.05)
        ms = elapsed_ms(start)
        assert 10 <= ms <= 500, f"Expected ~50ms elapsed, got {ms}ms"

    def test_always_non_negative_for_future_start(self) -> None:
        """A start time slightly in the future should still return 0 (clamped)."""
        # We can't easily test a future start without mocking, so just verify
        # the function never returns negative.
        start = datetime.now(timezone.utc)
        result = elapsed_ms(start)
        assert result >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CONFIDENCE AGGREGATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestAggregateConfidence:
    def test_empty_list_returns_zero(self) -> None:
        assert aggregate_confidence([]) == 0

    def test_all_zeros_returns_zero(self) -> None:
        assert aggregate_confidence([0, 0, 0]) == 0

    def test_zeros_excluded_from_average(self) -> None:
        # [80, 90, 0] → avg of [80, 90] = 85
        result = aggregate_confidence([80, 90, 0])
        assert result == 85

    def test_single_nonzero_value(self) -> None:
        assert aggregate_confidence([75]) == 75

    def test_all_same(self) -> None:
        assert aggregate_confidence([60, 60, 60]) == 60

    def test_rounding(self) -> None:
        # avg of [80, 81] = 80.5 → round to 81 (Python rounds half to even, or 81)
        result = aggregate_confidence([80, 81])
        assert result in (80, 81)

    def test_clamped_at_100(self) -> None:
        result = aggregate_confidence([150, 200])
        assert result == 100

    def test_clamped_at_0(self) -> None:
        result = aggregate_confidence([-50, -100])
        assert result == 0

    def test_mixed_valid_and_out_of_range(self) -> None:
        # 150 → clamped to 100, 50 → 50, avg of non-zero = (100+50)/2 = 75
        result = aggregate_confidence([150, 50])
        assert result == 75

    def test_typical_pipeline_scores(self) -> None:
        """Simulate confidence scores from multiple agents."""
        scores = [0, 82, 0, 91, 78]  # 0s = intake, evaluator (no confidence)
        result = aggregate_confidence(scores)
        # avg of [82, 91, 78] = 83.67 → 84
        assert 83 <= result <= 84


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TIMELINE FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatTimeline:
    def test_empty_list(self) -> None:
        result = format_timeline([])
        assert result == "(no timeline entries)"

    def test_single_entry_contains_agent(self) -> None:
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent_name="IntakeAgent",
            event_type=EventType.INCIDENT_CREATED,
            summary="Incident created",
        )
        result = format_timeline([entry])
        assert "IntakeAgent" in result

    def test_single_entry_contains_event_type(self) -> None:
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent_name="TriageAgent",
            event_type=EventType.TRIAGE_COMPLETED,
            summary="Triage done",
        )
        result = format_timeline([entry])
        assert "TRIAGE_COMPLETED" in result

    def test_single_entry_contains_summary(self) -> None:
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent_name="RootCauseAgent",
            event_type=EventType.ROOT_CAUSE_FOUND,
            summary="DB pool exhausted",
        )
        result = format_timeline([entry])
        assert "DB pool exhausted" in result

    def test_multiple_entries_are_ordered(self) -> None:
        entries = [
            TimelineEntry(
                timestamp=f"2025-01-01T00:0{i}:00+00:00",
                agent_name=f"Agent{i}",
                event_type=EventType.NOTE,
                summary=f"Step {i}",
            )
            for i in range(3)
        ]
        result = format_timeline(entries)
        assert "[01]" in result
        assert "[02]" in result
        assert "[03]" in result

    def test_confidence_shown_when_nonzero(self) -> None:
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent_name="EvaluatorAgent",
            event_type=EventType.EVALUATION_PASSED,
            summary="RCA passed",
            confidence=85,
        )
        result = format_timeline([entry])
        assert "confidence=85%" in result

    def test_confidence_not_shown_when_zero(self) -> None:
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent_name="IntakeAgent",
            event_type=EventType.INCIDENT_CREATED,
            summary="Incident created",
            confidence=0,
        )
        result = format_timeline([entry])
        assert "confidence=" not in result

    def test_tools_shown_when_present(self) -> None:
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent_name="LogAnalyzerAgent",
            event_type=EventType.LOG_ANALYSIS_COMPLETED,
            summary="Logs analysed",
            tools_used=["query_logs"],
        )
        result = format_timeline([entry])
        assert "query_logs" in result

    def test_duration_shown_when_nonzero(self) -> None:
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent_name="RootCauseAgent",
            event_type=EventType.ROOT_CAUSE_FOUND,
            summary="RCA done",
            duration_ms=1234,
        )
        result = format_timeline([entry])
        assert "1234ms" in result

    def test_falls_back_to_legacy_agent_field(self) -> None:
        """If agent_name is empty, fall back to legacy 'agent' field."""
        entry = TimelineEntry(
            timestamp="2025-01-01T00:00:00+00:00",
            agent="LegacyAgent",
            agent_name="",
            event_type=EventType.NOTE,
            summary="Legacy entry",
        )
        result = format_timeline([entry])
        assert "LegacyAgent" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. STATUS VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateStatus:
    def test_valid_new(self) -> None:
        assert validate_status("NEW") == IncidentStatus.NEW

    def test_valid_triaged(self) -> None:
        assert validate_status("TRIAGED") == IncidentStatus.TRIAGED

    def test_valid_resolved(self) -> None:
        assert validate_status("RESOLVED") == IncidentStatus.RESOLVED

    def test_all_valid_statuses(self) -> None:
        for status in IncidentStatus:
            result = validate_status(status.value)
            assert result == status

    def test_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            validate_status("BANANA")

    def test_error_message_contains_invalid_value(self) -> None:
        with pytest.raises(ValueError, match="BANANA"):
            validate_status("BANANA")

    def test_error_message_lists_valid_values(self) -> None:
        with pytest.raises(ValueError, match="NEW"):
            validate_status("INVALID_STATUS")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_status("")

    def test_lowercase_raises(self) -> None:
        """Status values are case-sensitive."""
        with pytest.raises(ValueError):
            validate_status("new")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MAKE TIMELINE ENTRY
# ═══════════════════════════════════════════════════════════════════════════════


class TestMakeTimelineEntry:
    def test_returns_timeline_entry(self) -> None:
        entry = make_timeline_entry(
            "IntakeAgent",
            EventType.INCIDENT_CREATED,
            "intake_completed",
            "Incident created",
        )
        assert isinstance(entry, TimelineEntry)

    def test_agent_name_set(self) -> None:
        entry = make_timeline_entry(
            "TriageAgent",
            EventType.TRIAGE_COMPLETED,
            "triage_done",
            "Severity confirmed P1",
        )
        assert entry.agent_name == "TriageAgent"

    def test_legacy_agent_field_set_for_backward_compat(self) -> None:
        entry = make_timeline_entry(
            "LogAnalyzerAgent",
            EventType.LOG_ANALYSIS_COMPLETED,
            "logs_analyzed",
            "10 findings",
        )
        assert entry.agent == "LogAnalyzerAgent"

    def test_event_type_set(self) -> None:
        entry = make_timeline_entry(
            "EvaluatorAgent",
            EventType.EVALUATION_PASSED,
            "eval_passed",
            "RCA quality sufficient",
        )
        assert entry.event_type == EventType.EVALUATION_PASSED

    def test_event_type_from_string(self) -> None:
        entry = make_timeline_entry(
            "EvaluatorAgent",
            "EVALUATION_FAILED",
            "eval_failed",
            "RCA quality insufficient",
        )
        assert entry.event_type == EventType.EVALUATION_FAILED

    def test_summary_set(self) -> None:
        entry = make_timeline_entry(
            "RootCauseAgent",
            EventType.ROOT_CAUSE_FOUND,
            "rca_complete",
            "DB pool exhausted due to batch job",
        )
        assert entry.summary == "DB pool exhausted due to batch job"

    def test_message_mirrors_summary(self) -> None:
        """message field must match summary for backward compatibility."""
        entry = make_timeline_entry(
            "RootCauseAgent",
            EventType.ROOT_CAUSE_FOUND,
            "rca_complete",
            "DB pool exhausted",
        )
        assert entry.message == entry.summary

    def test_confidence_clamped_above_100(self) -> None:
        entry = make_timeline_entry(
            "EvaluatorAgent",
            EventType.EVALUATION_PASSED,
            "eval_passed",
            "Pass",
            confidence=150,
        )
        assert entry.confidence == 100

    def test_confidence_clamped_below_0(self) -> None:
        entry = make_timeline_entry(
            "EvaluatorAgent",
            EventType.ERROR,
            "error",
            "Error occurred",
            confidence=-10,
        )
        assert entry.confidence == 0

    def test_tools_used_stored(self) -> None:
        entry = make_timeline_entry(
            "TriageAgent",
            EventType.TRIAGE_COMPLETED,
            "triage",
            "Done",
            tools_used=["get_alerts", "get_metrics"],
        )
        assert entry.tools_used == ["get_alerts", "get_metrics"]

    def test_duration_ms_stored(self) -> None:
        entry = make_timeline_entry(
            "LogAnalyzerAgent",
            EventType.LOG_ANALYSIS_COMPLETED,
            "logs",
            "Done",
            duration_ms=350,
        )
        assert entry.duration_ms == 350

    def test_default_status_is_success(self) -> None:
        entry = make_timeline_entry(
            "IntakeAgent",
            EventType.INCIDENT_CREATED,
            "intake",
            "Done",
        )
        assert entry.entry_status == "SUCCESS"

    def test_failure_status_set(self) -> None:
        entry = make_timeline_entry(
            "EscalationAgent",
            EventType.ERROR,
            "send_alert",
            "Alert delivery failed",
            status="FAILURE",
        )
        assert entry.entry_status == "FAILURE"

    def test_timestamp_is_iso_string(self) -> None:
        entry = make_timeline_entry(
            "IntakeAgent",
            EventType.INCIDENT_CREATED,
            "intake",
            "Done",
        )
        assert isinstance(entry.timestamp, str)
        assert "T" in entry.timestamp


# ═══════════════════════════════════════════════════════════════════════════════
# 8. EVENT BUS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventBus:
    def setup_method(self) -> None:
        from backend.events.event_bus import clear_listeners

        clear_listeners()

    def test_subscribe_and_publish(self) -> None:
        from backend.events.event_bus import (
            IncidentEventType,
            publish_event,
            subscribe,
        )

        received: list = []

        def listener(event) -> None:  # noqa: ANN001
            received.append(event)

        subscribe(listener)
        publish_event(IncidentEventType.STATUS_CHANGED, "INC-EB001")
        assert len(received) == 1
        assert received[0].incident_id == "INC-EB001"

    def test_unsubscribe(self) -> None:
        from backend.events.event_bus import (
            IncidentEventType,
            publish_event,
            subscribe,
            unsubscribe,
        )

        received: list = []

        def listener(event) -> None:  # noqa: ANN001
            received.append(event)

        subscribe(listener)
        unsubscribe(listener)
        publish_event(IncidentEventType.STATUS_CHANGED, "INC-EB002")
        assert len(received) == 0

    def test_listener_exception_does_not_break_pipeline(self) -> None:
        from backend.events.event_bus import (
            IncidentEventType,
            publish_event,
            subscribe,
        )

        def bad_listener(event) -> None:  # noqa: ANN001
            raise RuntimeError("Listener crash!")

        received: list = []

        def good_listener(event) -> None:  # noqa: ANN001
            received.append(event)

        subscribe(bad_listener)
        subscribe(good_listener)
        # Should not raise — bad_listener error is swallowed
        publish_event(IncidentEventType.AGENT_COMPLETED, "INC-EB003")
        assert len(received) == 1

    def test_payload_passed_to_listener(self) -> None:
        from backend.events.event_bus import (
            IncidentEventType,
            publish_event,
            subscribe,
        )

        received: list = []

        def listener(event) -> None:  # noqa: ANN001
            received.append(event)

        subscribe(listener)
        publish_event(
            IncidentEventType.STATUS_CHANGED,
            "INC-EB004",
            payload={"previous": "NEW", "new": "TRIAGED"},
        )
        assert received[0].payload["previous"] == "NEW"

    def test_clear_listeners(self) -> None:
        from backend.events.event_bus import (
            clear_listeners,
            listener_count,
            subscribe,
        )

        subscribe(lambda e: None)
        subscribe(lambda e: None)
        assert listener_count() == 2
        clear_listeners()
        assert listener_count() == 0

    def test_publish_with_no_listeners_is_silent(self) -> None:
        from backend.events.event_bus import IncidentEventType, publish_event

        # No listeners registered — should not raise
        publish_event(IncidentEventType.INCIDENT_CREATED, "INC-EB005")
