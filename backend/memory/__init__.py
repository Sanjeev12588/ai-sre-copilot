"""Memory package — Incident Case File schema, lifecycle, and session memory."""

from backend.memory.case_file import (
    SCHEMA_VERSION,
    DiagnosticsSection,
    EscalationSection,
    EventType,
    IncidentState,
    IncidentStatus,
    RecommendationsSection,
    SeverityLevel,
    TimelineEntry,
)
from backend.memory.lifecycle import (
    InvalidTransitionError,
    can_transition,
    get_allowed_transitions,
    is_terminal,
    transition,
)
from backend.memory.session import InMemoryStore, MemoryStore, SessionContext

__all__ = [
    # case_file
    "SCHEMA_VERSION",
    "IncidentState",
    "IncidentStatus",
    "SeverityLevel",
    "EventType",
    "TimelineEntry",
    "DiagnosticsSection",
    "RecommendationsSection",
    "EscalationSection",
    # lifecycle
    "transition",
    "can_transition",
    "get_allowed_transitions",
    "is_terminal",
    "InvalidTransitionError",
    # session
    "MemoryStore",
    "InMemoryStore",
    "SessionContext",
]
