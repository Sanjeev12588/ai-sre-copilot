"""Incident Case File — ADK Session State Schema (Phase 4).

Defines the shared Pydantic state schema used by all SRE agents
throughout the incident lifecycle.  All agents read from and write
to this structure via ``ctx.state``.

Phase 4 additions
-----------------
- ``schema_version`` on ``IncidentState`` for forward-compatible JSON storage.
- ``EventType`` enum for structured timeline classification.
- Extended ``TimelineEntry`` with ``agent_name``, ``event_type``, ``action``,
  ``summary``, ``confidence``, ``tools_used``, ``duration_ms``, ``entry_status``.
- New ``IncidentState`` fields: ``title``, ``description``, ``environment``,
  ``created_at``, ``updated_at``, ``assigned_team``, ``recovery_status``,
  ``verification_status``, ``report_status``, ``escalation_status``, ``metadata``.
- Confidence values are clamped to [0, 100] via field validators.
- Timestamps are auto-populated by a ``model_validator``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Schema versioning — increment when backward-incompatible changes are made.
# ---------------------------------------------------------------------------
SCHEMA_VERSION: int = 1


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IncidentStatus(str, Enum):
    """Lifecycle status of an active incident."""

    NEW = "NEW"
    TRIAGED = "TRIAGED"
    INVESTIGATING = "INVESTIGATING"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    EVALUATING = "EVALUATING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    MITIGATING = "MITIGATING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SeverityLevel(str, Enum):
    """Incident severity classification."""

    P0 = "P0"  # Complete outage — immediate all-hands
    P1 = "P1"  # Critical degradation — on-call page
    P2 = "P2"  # Significant degradation — Slack alert
    P3 = "P3"  # Minor degradation — ticket created
    P4 = "P4"  # Informational — monitoring only


class EventType(str, Enum):
    """Structured classification for timeline events.

    Using an Enum (not a raw string) makes it trivial to filter timeline
    entries by type in the persistence layer, UI, and event bus.
    """

    INCIDENT_CREATED = "INCIDENT_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    TRIAGE_COMPLETED = "TRIAGE_COMPLETED"
    LOG_ANALYSIS_COMPLETED = "LOG_ANALYSIS_COMPLETED"
    ROOT_CAUSE_FOUND = "ROOT_CAUSE_FOUND"
    EVALUATION_PASSED = "EVALUATION_PASSED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    RECOVERY_PLANNED = "RECOVERY_PLANNED"
    ESCALATION_SENT = "ESCALATION_SENT"
    REPORT_GENERATED = "REPORT_GENERATED"
    TOOL_CALL = "TOOL_CALL"
    ERROR = "ERROR"
    NOTE = "NOTE"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class TimelineEntry(BaseModel):
    """A single entry in the incident timeline audit log.

    Both the legacy fields (``agent``, ``message``) and the new Phase 4
    fields (``agent_name``, ``event_type``, ``summary``, …) are kept so
    that existing agent prompt instructions that write plain strings remain
    compatible.
    """

    # ---- Legacy fields (Phase 1–3, kept for backward compatibility) --------
    timestamp: str = ""
    agent: str = ""
    message: str = ""

    # ---- Phase 4 structured fields -----------------------------------------
    agent_name: str = ""
    """Explicit agent identifier (e.g. 'RootCauseAgent')."""

    event_type: EventType = EventType.NOTE
    """Enum-typed event classification for filtering and WebSocket streaming."""

    action: str = ""
    """Short verb describing what the agent did (e.g. 'triage_started')."""

    summary: str = ""
    """Human-readable summary of the event."""

    confidence: int = 0
    """Agent confidence score at this point in the pipeline (0–100)."""

    tools_used: list[str] = Field(default_factory=list)
    """Names of MCP tools invoked during this event."""

    duration_ms: int = 0
    """Wall-clock duration of the agent step in milliseconds."""

    entry_status: str = ""
    """Outcome of the agent step: SUCCESS | FAILURE | SKIPPED."""

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: int) -> int:
        """Clamp confidence to [0, 100] to prevent future range bugs."""
        return max(0, min(100, v))


class DiagnosticsSection(BaseModel):
    """Evidence and root cause diagnostics produced by investigative agents."""

    alert_ids: list[str] = Field(default_factory=list)
    severity: str = ""
    affected_services: list[str] = Field(default_factory=list)
    scope_description: str = ""
    log_findings: list[str] = Field(default_factory=list)
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    root_cause: str = ""
    confidence_score: int = 0
    evidence: list[str] = Field(default_factory=list)
    blast_radius: str = ""
    evaluator_verdict: str = ""
    evaluation_notes: str = ""

    @field_validator("confidence_score")
    @classmethod
    def clamp_confidence(cls, v: int) -> int:
        """Clamp confidence_score to [0, 100]."""
        return max(0, min(100, v))


class RecommendationsSection(BaseModel):
    """Recovery recommendation produced by the Recovery Planner Agent."""

    runbook_id: str = ""
    title: str = ""
    risk_level: str = ""
    requires_human_approval: bool = True
    simulated_output: list[dict[str, Any]] = Field(default_factory=list)
    approved: bool = False


class EscalationSection(BaseModel):
    """Escalation payload produced by the Escalation Agent."""

    escalation_id: str = ""
    target_team: str = ""
    channels: list[str] = Field(default_factory=list)
    message: str = ""
    escalated_at: str = ""


# ---------------------------------------------------------------------------
# Root state model
# ---------------------------------------------------------------------------


class IncidentState(BaseModel):
    """Full ADK session state schema for the AI SRE Copilot (Phase 4).

    Shared across all agents in the workflow.  Each agent reads the
    current state and writes its specialist output under the
    corresponding section before yielding control back.

    Phase 4 additions
    -----------------
    - ``schema_version``: integer bumped when the schema changes.
    - ``title`` / ``description`` / ``environment``: richer incident context.
    - ``created_at`` / ``updated_at``: auto-populated ISO-8601 timestamps.
    - ``assigned_team``, ``recovery_status``, ``verification_status``,
      ``report_status``, ``escalation_status``: per-phase progress tracking.
    - ``metadata``: free-form dict for extensibility without schema changes.
    """

    # ---- Schema versioning (Phase 4) ----------------------------------------
    schema_version: int = SCHEMA_VERSION

    # ---- Incident identity ---------------------------------------------------
    incident_id: str = ""
    title: str = ""
    description: str = ""
    status: str = IncidentStatus.NEW.value
    summary: str = ""

    # ---- Environment ---------------------------------------------------------
    environment: str = "production"

    # ---- Severity (convenience top-level mirror of diagnostics.severity) ----
    severity: str = ""

    # ---- Timestamps (auto-populated by model_validator) ---------------------
    created_at: str = ""
    updated_at: str = ""

    # ---- Populated by Intake Agent ------------------------------------------
    raw_alert: dict[str, Any] = Field(default_factory=dict)

    # ---- Populated by specialist agents -------------------------------------
    diagnostics: DiagnosticsSection = Field(default_factory=DiagnosticsSection)
    recommendations: RecommendationsSection = Field(
        default_factory=RecommendationsSection
    )
    escalation: EscalationSection = Field(default_factory=EscalationSection)

    # ---- Phase 4 lifecycle tracking fields ----------------------------------
    assigned_team: str = ""
    recovery_status: str = ""
    verification_status: str = ""
    report_status: str = ""
    escalation_status: str = ""

    # ---- Populated by Report Generator --------------------------------------
    report: str = ""
    stakeholder_update: str = ""

    # ---- Timeline audit log (appended by every agent) -----------------------
    timeline: list[TimelineEntry] = Field(default_factory=list)

    # ---- Routing flag used by Coordinator -----------------------------------
    next_action: str = "triage"

    # ---- Free-form metadata (extensible without schema changes) -------------
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _auto_timestamps(cls, values: Any) -> Any:
        """Auto-populate created_at and updated_at if not provided."""
        if not isinstance(values, dict):
            return values
        now = datetime.now(timezone.utc).isoformat()
        if not values.get("created_at"):
            values["created_at"] = now
        if not values.get("updated_at"):
            values["updated_at"] = now
        return values
