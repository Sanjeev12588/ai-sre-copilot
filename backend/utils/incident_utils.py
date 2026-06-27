"""Utility functions for incident lifecycle management (Phase 4).

All functions are pure (no side effects, no I/O) and are independently
testable without mocking.

Functions
---------
generate_incident_id()      — INC-<8 uppercase hex chars>
utc_now_iso()               — current UTC ISO-8601 timestamp
elapsed_ms(start)           — milliseconds since *start*
aggregate_confidence(scores)— clamped weighted average confidence
format_timeline(entries)    — human-readable ordered timeline string
validate_status(value)      — parse string → IncidentStatus enum
make_timeline_entry(...)    — construct a fully-populated TimelineEntry
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.memory.case_file import EventType, IncidentStatus, TimelineEntry

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Incident ID generation
# ---------------------------------------------------------------------------


def generate_incident_id() -> str:
    """Generate a unique incident ID in the format ``INC-<8 uppercase hex>``.

    Uses ``secrets.token_hex`` (cryptographically strong) to guarantee
    uniqueness across concurrent requests.

    Examples
    --------
    >>> generate_incident_id()
    'INC-A4F3B2C1'
    """
    return f"INC-{secrets.token_hex(4).upper()}"


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string.

    Example: ``'2025-06-27T09:30:00.123456+00:00'``
    """
    return datetime.now(timezone.utc).isoformat()


def elapsed_ms(start: datetime) -> int:
    """Return the number of milliseconds elapsed since *start*.

    Parameters
    ----------
    start:
        A timezone-aware ``datetime`` (use ``datetime.now(timezone.utc)``).

    Returns
    -------
    int
        Non-negative milliseconds elapsed.
    """
    delta = datetime.now(timezone.utc) - start
    return max(0, int(delta.total_seconds() * 1000))


# ---------------------------------------------------------------------------
# Confidence aggregation
# ---------------------------------------------------------------------------


def aggregate_confidence(scores: list[int]) -> int:
    """Return the average of non-zero scores, clamped to [0, 100].

    Zero-valued scores are excluded from the average to avoid penalising
    agents that did not produce a confidence measurement (e.g. Intake Agent).

    Parameters
    ----------
    scores:
        List of confidence integers.  Values outside [0, 100] are clamped
        before averaging.

    Returns
    -------
    int
        Aggregated confidence in [0, 100].  Returns 0 if all scores are zero
        or the list is empty.

    Examples
    --------
    >>> aggregate_confidence([80, 90, 0])
    85
    >>> aggregate_confidence([])
    0
    >>> aggregate_confidence([150, -10])
    50
    """
    clamped = [max(0, min(100, s)) for s in scores]
    non_zero = [s for s in clamped if s > 0]
    if not non_zero:
        return 0
    avg = sum(non_zero) / len(non_zero)
    return max(0, min(100, int(round(avg))))


# ---------------------------------------------------------------------------
# Timeline formatting
# ---------------------------------------------------------------------------


def format_timeline(entries: list[TimelineEntry]) -> str:
    """Format a list of ``TimelineEntry`` objects as a human-readable log.

    Each line includes: index, timestamp, agent name, event type, summary,
    and optional confidence / tools / duration fields.

    Returns ``'(no timeline entries)'`` for an empty list.

    Example output
    --------------
    [01] 2025-06-27T09:00:00+00:00 | IntakeAgent | INCIDENT_CREATED
         Alert received and incident INC-A4F3B2C1 created.
    [02] 2025-06-27T09:00:05+00:00 | TriageAgent | TRIAGE_COMPLETED | confidence=80%
         Severity confirmed P1. Blast radius: High.
    """
    if not entries:
        return "(no timeline entries)"

    lines: list[str] = []
    for i, entry in enumerate(entries, 1):
        ts = entry.timestamp or "unknown"
        agent = entry.agent_name or entry.agent or "unknown"
        # Handle both enum and raw string values for event_type
        if hasattr(entry.event_type, "value"):
            event = entry.event_type.value
        else:
            event = str(entry.event_type)

        extras: list[str] = []
        if entry.confidence:
            extras.append(f"confidence={entry.confidence}%")
        if entry.tools_used:
            extras.append(f"tools={entry.tools_used}")
        if entry.duration_ms:
            extras.append(f"duration={entry.duration_ms}ms")
        extras_str = " | " + " | ".join(extras) if extras else ""

        summary = entry.summary or entry.message or ""
        lines.append(f"[{i:02d}] {ts} | {agent} | {event}{extras_str}\n     {summary}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Status validation
# ---------------------------------------------------------------------------


def validate_status(value: str) -> IncidentStatus:
    """Parse *value* into an ``IncidentStatus`` enum.

    Raises
    ------
    ValueError
        If *value* is not a valid ``IncidentStatus``, with a helpful message
        listing all valid values.

    Examples
    --------
    >>> validate_status("TRIAGED")
    <IncidentStatus.TRIAGED: 'TRIAGED'>
    >>> validate_status("BANANA")
    ValueError: Unknown status 'BANANA'. Valid: ['NEW', 'TRIAGED', ...]
    """
    try:
        return IncidentStatus(value)
    except ValueError:
        valid = [s.value for s in IncidentStatus]
        raise ValueError(f"Unknown status {value!r}. Valid values: {valid}") from None


# ---------------------------------------------------------------------------
# Timeline entry factory
# ---------------------------------------------------------------------------


def make_timeline_entry(
    agent_name: str,
    event_type: EventType | str,
    action: str,
    summary: str,
    *,
    confidence: int = 0,
    tools_used: list[str] | None = None,
    duration_ms: int = 0,
    status: str = "SUCCESS",
) -> TimelineEntry:
    """Build a fully-populated ``TimelineEntry``.

    Parameters
    ----------
    agent_name:
        Name of the agent producing this entry (e.g. ``'RootCauseAgent'``).
    event_type:
        An ``EventType`` enum value or its string equivalent.
    action:
        Short verb describing what happened (e.g. ``'rca_completed'``).
    summary:
        Human-readable description of the event.
    confidence:
        Agent confidence score (0–100).  Clamped automatically.
    tools_used:
        List of MCP tool names called during this step.
    duration_ms:
        Wall-clock duration of the agent step in milliseconds.
    status:
        Outcome: ``'SUCCESS'``, ``'FAILURE'``, or ``'SKIPPED'``.

    Returns
    -------
    TimelineEntry
        A ``TimelineEntry`` with all legacy fields populated for backward
        compatibility with agents that still read ``agent`` and ``message``.
    """
    resolved_event = (
        event_type if isinstance(event_type, EventType) else EventType(event_type)
    )
    clamped_confidence = max(0, min(100, confidence))

    return TimelineEntry(
        timestamp=utc_now_iso(),
        # Legacy fields (backward compat)
        agent=agent_name,
        message=summary,
        # Phase 4 structured fields
        agent_name=agent_name,
        event_type=resolved_event,
        action=action,
        summary=summary,
        confidence=clamped_confidence,
        tools_used=tools_used or [],
        duration_ms=duration_ms,
        entry_status=status,
    )
