"""Incident Lifecycle State Machine (Phase 4).

Enforces valid ``IncidentStatus`` transitions.  All states are represented
as ``IncidentStatus`` enum values — never raw strings.

Usage
-----
>>> from backend.memory.lifecycle import transition, can_transition
>>> from backend.memory.case_file import IncidentStatus
>>> updated_state = transition(state, IncidentStatus.TRIAGED, agent="TriageAgent")

Transition graph
----------------
  NEW → TRIAGED
  TRIAGED → INVESTIGATING
  INVESTIGATING → ROOT_CAUSE_IDENTIFIED
  ROOT_CAUSE_IDENTIFIED → EVALUATING
  EVALUATING → PENDING_APPROVAL  (PASS)
              → ROOT_CAUSE_IDENTIFIED  (FAIL retry)
  PENDING_APPROVAL → MITIGATING | ESCALATED
  MITIGATING → ESCALATED | RESOLVED
  ESCALATED → RESOLVED
  RESOLVED → CLOSED
  CLOSED → (terminal — no further transitions)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.memory.case_file import EventType, IncidentStatus, TimelineEntry

if TYPE_CHECKING:
    from backend.memory.case_file import IncidentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid transition graph — keys are current states, values are allowed targets.
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[IncidentStatus, list[IncidentStatus]] = {
    IncidentStatus.NEW: [
        IncidentStatus.TRIAGED,
    ],
    IncidentStatus.TRIAGED: [
        IncidentStatus.INVESTIGATING,
    ],
    IncidentStatus.INVESTIGATING: [
        IncidentStatus.ROOT_CAUSE_IDENTIFIED,
    ],
    IncidentStatus.ROOT_CAUSE_IDENTIFIED: [
        IncidentStatus.EVALUATING,
    ],
    IncidentStatus.EVALUATING: [
        IncidentStatus.PENDING_APPROVAL,  # Evaluator PASS
        IncidentStatus.ROOT_CAUSE_IDENTIFIED,  # Evaluator FAIL → retry RCA
    ],
    IncidentStatus.PENDING_APPROVAL: [
        IncidentStatus.MITIGATING,
        IncidentStatus.ESCALATED,
    ],
    IncidentStatus.MITIGATING: [
        IncidentStatus.ESCALATED,
        IncidentStatus.RESOLVED,
    ],
    IncidentStatus.ESCALATED: [
        IncidentStatus.RESOLVED,
    ],
    IncidentStatus.RESOLVED: [
        IncidentStatus.CLOSED,
    ],
    IncidentStatus.CLOSED: [],  # terminal
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTransitionError(Exception):
    """Raised when an invalid lifecycle transition is attempted."""

    def __init__(self, current: IncidentStatus, target: IncidentStatus) -> None:
        allowed = [s.value for s in VALID_TRANSITIONS.get(current, [])]
        super().__init__(
            f"Cannot transition from {current.value!r} to {target.value!r}. "
            f"Allowed next states: {allowed or ['(none — terminal state)']}"
        )
        self.current = current
        self.target = target


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def can_transition(current: IncidentStatus, target: IncidentStatus) -> bool:
    """Return ``True`` if transitioning from *current* to *target* is valid."""
    return target in VALID_TRANSITIONS.get(current, [])


def transition(
    state: IncidentState,
    new_status: IncidentStatus,
    *,
    agent: str = "system",
    reason: str = "",
) -> IncidentState:
    """Validate and apply a lifecycle transition to *state*.

    Parameters
    ----------
    state:
        The current ``IncidentState`` object.
    new_status:
        The target ``IncidentStatus`` enum value.
    agent:
        Name of the agent (or system component) requesting the transition.
        Used for logging and the auto-appended timeline entry.
    reason:
        Optional human-readable reason for the transition (logged and added
        to the timeline summary).

    Returns
    -------
    IncidentState
        A new ``IncidentState`` with the updated status, ``updated_at``
        timestamp, and an auto-appended timeline entry.

    Raises
    ------
    InvalidTransitionError
        If the transition is not permitted by the state machine.
    """
    current = IncidentStatus(state.status)

    if not can_transition(current, new_status):
        raise InvalidTransitionError(current, new_status)

    now = datetime.now(timezone.utc).isoformat()

    # Structured log: incident_id | agent | previous → new | reason
    logger.info(
        "Lifecycle transition | incident=%s | agent=%s | %s → %s%s",
        state.incident_id,
        agent,
        current.value,
        new_status.value,
        f" | reason={reason}" if reason else "",
    )

    summary = f"Status changed from {current.value} to {new_status.value}" + (
        f". Reason: {reason}" if reason else ""
    )

    timeline_entry = TimelineEntry(
        timestamp=now,
        agent=agent,
        agent_name=agent,
        event_type=EventType.STATUS_CHANGED,
        action="status_transition",
        message=summary,
        summary=summary,
        entry_status="SUCCESS",
    )

    updated_timeline = list(state.timeline) + [timeline_entry]

    return state.model_copy(
        update={
            "status": new_status.value,
            "updated_at": now,
            "timeline": updated_timeline,
        }
    )


def get_allowed_transitions(status: IncidentStatus) -> list[IncidentStatus]:
    """Return the list of valid next states from *status*."""
    return list(VALID_TRANSITIONS.get(status, []))


def is_terminal(status: IncidentStatus) -> bool:
    """Return ``True`` if *status* has no valid outbound transitions."""
    return len(VALID_TRANSITIONS.get(status, [])) == 0
