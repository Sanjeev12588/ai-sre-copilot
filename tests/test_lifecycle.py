"""Tests for the Incident Lifecycle State Machine (Phase 4).

Coverage
--------
TestValidTransitions      — every documented valid transition succeeds
TestInvalidTransitions    — invalid transitions raise InvalidTransitionError
TestTerminalState         — CLOSED state blocks all outgoing transitions
TestCanTransition         — can_transition() helper accuracy
TestTransitionSideEffects — transition() updates status, updated_at, timeline
TestEvaluatorRetryPath    — EVALUATING → ROOT_CAUSE_IDENTIFIED (FAIL retry)
TestAllowedTransitions    — get_allowed_transitions() returns correct targets
TestIsTerminal            — is_terminal() returns True only for CLOSED
"""

from __future__ import annotations

import pytest

from backend.memory.case_file import EventType, IncidentState, IncidentStatus
from backend.memory.lifecycle import (
    InvalidTransitionError,
    can_transition,
    get_allowed_transitions,
    is_terminal,
    transition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(status: IncidentStatus) -> IncidentState:
    """Return a minimal IncidentState with the given status."""
    return IncidentState(incident_id="INC-TEST0001", status=status.value)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VALID TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidTransitions:
    """Every transition that should succeed does succeed."""

    def test_new_to_triaged(self) -> None:
        s = transition(_state(IncidentStatus.NEW), IncidentStatus.TRIAGED)
        assert s.status == IncidentStatus.TRIAGED.value

    def test_triaged_to_investigating(self) -> None:
        s = transition(_state(IncidentStatus.TRIAGED), IncidentStatus.INVESTIGATING)
        assert s.status == IncidentStatus.INVESTIGATING.value

    def test_investigating_to_root_cause_identified(self) -> None:
        s = transition(
            _state(IncidentStatus.INVESTIGATING),
            IncidentStatus.ROOT_CAUSE_IDENTIFIED,
        )
        assert s.status == IncidentStatus.ROOT_CAUSE_IDENTIFIED.value

    def test_root_cause_identified_to_evaluating(self) -> None:
        s = transition(
            _state(IncidentStatus.ROOT_CAUSE_IDENTIFIED),
            IncidentStatus.EVALUATING,
        )
        assert s.status == IncidentStatus.EVALUATING.value

    def test_evaluating_to_pending_approval(self) -> None:
        s = transition(
            _state(IncidentStatus.EVALUATING),
            IncidentStatus.PENDING_APPROVAL,
        )
        assert s.status == IncidentStatus.PENDING_APPROVAL.value

    def test_pending_approval_to_mitigating(self) -> None:
        s = transition(
            _state(IncidentStatus.PENDING_APPROVAL),
            IncidentStatus.MITIGATING,
        )
        assert s.status == IncidentStatus.MITIGATING.value

    def test_pending_approval_to_escalated(self) -> None:
        s = transition(
            _state(IncidentStatus.PENDING_APPROVAL),
            IncidentStatus.ESCALATED,
        )
        assert s.status == IncidentStatus.ESCALATED.value

    def test_mitigating_to_escalated(self) -> None:
        s = transition(_state(IncidentStatus.MITIGATING), IncidentStatus.ESCALATED)
        assert s.status == IncidentStatus.ESCALATED.value

    def test_mitigating_to_resolved(self) -> None:
        s = transition(_state(IncidentStatus.MITIGATING), IncidentStatus.RESOLVED)
        assert s.status == IncidentStatus.RESOLVED.value

    def test_escalated_to_resolved(self) -> None:
        s = transition(_state(IncidentStatus.ESCALATED), IncidentStatus.RESOLVED)
        assert s.status == IncidentStatus.RESOLVED.value

    def test_resolved_to_closed(self) -> None:
        s = transition(_state(IncidentStatus.RESOLVED), IncidentStatus.CLOSED)
        assert s.status == IncidentStatus.CLOSED.value

    def test_full_happy_path(self) -> None:
        """Walk the entire happy-path pipeline without error."""
        s = _state(IncidentStatus.NEW)
        path = [
            IncidentStatus.TRIAGED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.ROOT_CAUSE_IDENTIFIED,
            IncidentStatus.EVALUATING,
            IncidentStatus.PENDING_APPROVAL,
            IncidentStatus.MITIGATING,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        ]
        for next_status in path:
            s = transition(s, next_status)
        assert s.status == IncidentStatus.CLOSED.value


# ═══════════════════════════════════════════════════════════════════════════════
# 2. INVALID TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvalidTransitions:
    """Every documented invalid transition raises InvalidTransitionError."""

    def test_new_to_investigating(self) -> None:
        with pytest.raises(InvalidTransitionError):
            transition(_state(IncidentStatus.NEW), IncidentStatus.INVESTIGATING)

    def test_new_to_resolved(self) -> None:
        with pytest.raises(InvalidTransitionError):
            transition(_state(IncidentStatus.NEW), IncidentStatus.RESOLVED)

    def test_triaged_to_closed(self) -> None:
        with pytest.raises(InvalidTransitionError):
            transition(_state(IncidentStatus.TRIAGED), IncidentStatus.CLOSED)

    def test_investigating_to_pending_approval(self) -> None:
        with pytest.raises(InvalidTransitionError):
            transition(
                _state(IncidentStatus.INVESTIGATING),
                IncidentStatus.PENDING_APPROVAL,
            )

    def test_resolved_to_new(self) -> None:
        with pytest.raises(InvalidTransitionError):
            transition(_state(IncidentStatus.RESOLVED), IncidentStatus.NEW)

    def test_error_message_contains_allowed_states(self) -> None:
        """InvalidTransitionError message must list allowed next states."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            transition(_state(IncidentStatus.NEW), IncidentStatus.CLOSED)
        msg = str(exc_info.value)
        assert "TRIAGED" in msg  # the only allowed next state from NEW

    def test_error_exposes_current_and_target(self) -> None:
        """InvalidTransitionError attributes are accessible programmatically."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            transition(_state(IncidentStatus.NEW), IncidentStatus.RESOLVED)
        err = exc_info.value
        assert err.current == IncidentStatus.NEW
        assert err.target == IncidentStatus.RESOLVED


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TERMINAL STATE
# ═══════════════════════════════════════════════════════════════════════════════


class TestTerminalState:
    """CLOSED is a terminal state — no transitions out."""

    def test_closed_to_any_raises(self) -> None:
        for target in IncidentStatus:
            if target == IncidentStatus.CLOSED:
                continue
            with pytest.raises(InvalidTransitionError):
                transition(_state(IncidentStatus.CLOSED), target)

    def test_is_terminal_closed(self) -> None:
        assert is_terminal(IncidentStatus.CLOSED) is True

    def test_is_terminal_resolved_is_false(self) -> None:
        assert is_terminal(IncidentStatus.RESOLVED) is False

    def test_is_terminal_new_is_false(self) -> None:
        assert is_terminal(IncidentStatus.NEW) is False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CAN_TRANSITION HELPER
# ═══════════════════════════════════════════════════════════════════════════════


class TestCanTransition:
    """can_transition() must match the VALID_TRANSITIONS graph exactly."""

    def test_true_for_new_to_triaged(self) -> None:
        assert can_transition(IncidentStatus.NEW, IncidentStatus.TRIAGED) is True

    def test_false_for_new_to_resolved(self) -> None:
        assert can_transition(IncidentStatus.NEW, IncidentStatus.RESOLVED) is False

    def test_false_for_closed_to_anything(self) -> None:
        for target in IncidentStatus:
            assert can_transition(IncidentStatus.CLOSED, target) is False

    def test_evaluating_can_retry_rca(self) -> None:
        assert (
            can_transition(
                IncidentStatus.EVALUATING,
                IncidentStatus.ROOT_CAUSE_IDENTIFIED,
            )
            is True
        )

    def test_evaluating_can_pass(self) -> None:
        assert (
            can_transition(
                IncidentStatus.EVALUATING,
                IncidentStatus.PENDING_APPROVAL,
            )
            is True
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TRANSITION SIDE EFFECTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransitionSideEffects:
    """transition() must update status, updated_at, and append a timeline entry."""

    def test_status_is_updated(self) -> None:
        s = transition(_state(IncidentStatus.NEW), IncidentStatus.TRIAGED)
        assert s.status == IncidentStatus.TRIAGED.value

    def test_updated_at_is_set(self) -> None:
        original = _state(IncidentStatus.NEW)
        updated = transition(original, IncidentStatus.TRIAGED)
        assert updated.updated_at != ""

    def test_timeline_entry_appended(self) -> None:
        s = _state(IncidentStatus.NEW)
        assert len(s.timeline) == 0
        updated = transition(s, IncidentStatus.TRIAGED, agent="TriageAgent")
        assert len(updated.timeline) == 1

    def test_timeline_entry_has_correct_event_type(self) -> None:
        updated = transition(
            _state(IncidentStatus.NEW),
            IncidentStatus.TRIAGED,
        )
        entry = updated.timeline[0]
        assert entry.event_type == EventType.STATUS_CHANGED

    def test_timeline_entry_contains_agent_name(self) -> None:
        updated = transition(
            _state(IncidentStatus.NEW),
            IncidentStatus.TRIAGED,
            agent="TriageAgent",
        )
        entry = updated.timeline[0]
        assert "TriageAgent" in (entry.agent_name or entry.agent)

    def test_timeline_entry_summary_mentions_statuses(self) -> None:
        updated = transition(
            _state(IncidentStatus.NEW),
            IncidentStatus.TRIAGED,
        )
        entry = updated.timeline[0]
        summary = entry.summary or entry.message
        assert "NEW" in summary and "TRIAGED" in summary

    def test_reason_appears_in_timeline(self) -> None:
        updated = transition(
            _state(IncidentStatus.NEW),
            IncidentStatus.TRIAGED,
            reason="Alert confirmed active",
        )
        entry = updated.timeline[0]
        summary = entry.summary or entry.message
        assert "Alert confirmed active" in summary

    def test_original_state_is_not_mutated(self) -> None:
        """transition() returns a new state — original must be unchanged."""
        original = _state(IncidentStatus.NEW)
        transition(original, IncidentStatus.TRIAGED)
        assert original.status == IncidentStatus.NEW.value

    def test_multiple_transitions_accumulate_timeline(self) -> None:
        s = _state(IncidentStatus.NEW)
        s = transition(s, IncidentStatus.TRIAGED)
        s = transition(s, IncidentStatus.INVESTIGATING)
        assert len(s.timeline) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 6. EVALUATOR RETRY PATH
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluatorRetryPath:
    """EVALUATING → ROOT_CAUSE_IDENTIFIED is the evaluator FAIL retry path."""

    def test_evaluating_fail_retry(self) -> None:
        s = _state(IncidentStatus.EVALUATING)
        retried = transition(
            s,
            IncidentStatus.ROOT_CAUSE_IDENTIFIED,
            agent="EvaluatorAgent",
            reason="RCA quality insufficient",
        )
        assert retried.status == IncidentStatus.ROOT_CAUSE_IDENTIFIED.value

    def test_retry_then_pass_path(self) -> None:
        s = _state(IncidentStatus.EVALUATING)
        # First: FAIL — retry RCA
        s = transition(s, IncidentStatus.ROOT_CAUSE_IDENTIFIED)
        # Re-run RCA
        s = transition(s, IncidentStatus.EVALUATING)
        # Second: PASS
        s = transition(s, IncidentStatus.PENDING_APPROVAL)
        assert s.status == IncidentStatus.PENDING_APPROVAL.value


# ═══════════════════════════════════════════════════════════════════════════════
# 7. GET_ALLOWED_TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAllowedTransitions:
    """get_allowed_transitions() must return the correct target list."""

    def test_new_allows_only_triaged(self) -> None:
        allowed = get_allowed_transitions(IncidentStatus.NEW)
        assert allowed == [IncidentStatus.TRIAGED]

    def test_evaluating_allows_two_paths(self) -> None:
        allowed = get_allowed_transitions(IncidentStatus.EVALUATING)
        assert IncidentStatus.PENDING_APPROVAL in allowed
        assert IncidentStatus.ROOT_CAUSE_IDENTIFIED in allowed
        assert len(allowed) == 2

    def test_closed_allows_nothing(self) -> None:
        allowed = get_allowed_transitions(IncidentStatus.CLOSED)
        assert allowed == []

    def test_pending_approval_allows_two_paths(self) -> None:
        allowed = get_allowed_transitions(IncidentStatus.PENDING_APPROVAL)
        assert IncidentStatus.MITIGATING in allowed
        assert IncidentStatus.ESCALATED in allowed
