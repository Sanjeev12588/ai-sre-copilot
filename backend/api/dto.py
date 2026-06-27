"""API Data Transfer Objects (DTOs) for the FastAPI Gateway (Phase 8).

Separates the internal database/Pydantic state schemas (IncidentState)
from the client-facing REST API interface.

Phase 8 additions:
  - Strict field constraints (max_length, enum validation)
  - RawAlertPayload sub-model with extra='forbid' (no unknown fields)
  - Environment and severity validated against allowed enum values
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Phase 8: Strict sub-model for raw_alert payload
# ---------------------------------------------------------------------------


class RawAlertPayload(BaseModel):
    """Strict schema for the raw alert payload from monitoring systems.

    Uses extra='ignore' to silently drop unknown vendor-specific fields
    while still enforcing the required core fields.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Alert name from the monitoring system.",
    )
    severity: Literal["P0", "P1", "P2", "P3", "P4"] = Field(
        default="P1",
        description="Alert severity level (P0=critical, P4=informational).",
    )
    service: str = Field(
        default="",
        max_length=200,
        description="Affected service name.",
    )
    status: str = Field(
        default="firing",
        max_length=50,
        description="Alert status (firing, resolved, pending).",
    )
    alert_id: str = Field(
        default="",
        max_length=100,
        description="Unique alert identifier from the monitoring system.",
    )
    started_at: str = Field(
        default="",
        max_length=50,
        description="ISO-8601 timestamp when the alert fired.",
    )
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Additional alert annotations (summary, description, runbook_url).",
    )

    model_config = ConfigDict(
        # Accept but silently ignore unknown vendor-specific alert fields
        extra="ignore",
    )

    @field_validator("annotations")
    @classmethod
    def validate_annotations(cls, v: dict[str, str]) -> dict[str, str]:
        """Ensure annotation values are strings and not excessively long."""
        for key, value in v.items():
            if not isinstance(value, str):
                v[key] = str(value)
            if len(v[key]) > 2000:
                v[key] = v[key][:2000] + "...[truncated]"
        return v


class IncidentCreateRequest(BaseModel):
    """Payload to create and trigger a new incident investigation workflow.

    Phase 8: Strict field constraints enforce maximum lengths and valid enum
    values. Unknown top-level fields are forbidden to prevent silent injection
    via unvalidated parameters.
    """

    title: str = Field(
        default="",
        max_length=200,
        description="Optional human-readable title of the incident.",
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="Optional detailed description of the incident.",
    )
    environment: Literal["production", "staging", "development", "testing"] = Field(
        default="production",
        description="Target deployment environment.",
    )
    raw_alert: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw alert payload. Must contain 'name' and 'severity' keys.",
    )

    model_config = ConfigDict(
        # Phase 8: Reject unknown fields to prevent silent acceptance of
        # unexpected parameters that could be used for injection or spoofing
        extra="forbid",
        json_schema_extra={
            "example": {
                "title": "Database degradation alert",
                "description": "Checkout database connection pool usage is at 95%",
                "environment": "production",
                "raw_alert": {
                    "alert_id": "AL-12345",
                    "name": "DatabaseDegradation",
                    "service": "checkout-db",
                    "severity": "P1",
                    "status": "firing",
                    "started_at": "2026-06-27T10:00:00Z",
                    "annotations": {
                        "summary": "Checkout DB Connection Pool Full",
                        "description": "Database pool connections exhausted.",
                        "runbook_url": "https://wiki.company.internal/runbooks/db-pool",
                    },
                },
            }
        },
    )


class TimelineEntryResponse(BaseModel):
    """Client-facing representation of a timeline event."""

    timestamp: str = Field(
        ..., description="ISO-8601 UTC timestamp when the event occurred."
    )
    agent_name: str = Field(
        ..., description="Name of the agent or system that created this entry."
    )
    event_type: str = Field(
        ..., description="Structured type of the event (e.g. ROOT_CAUSE_FOUND)."
    )
    action: str = Field(..., description="Short verb describing what was executed.")
    summary: str = Field(..., description="Human-readable description of the event.")
    confidence: int = Field(
        ..., description="Agent confidence score at this point (0-100)."
    )
    tools_used: list[str] = Field(
        default_factory=list, description="List of MCP tools invoked during this step."
    )
    duration_ms: int = Field(
        ..., description="Execution duration of this agent step in milliseconds."
    )
    entry_status: str = Field(
        ..., description="Outcome status of the step (SUCCESS, FAILURE, etc.)."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-06-27T10:02:15Z",
                "agent_name": "RootCauseAgent",
                "event_type": "ROOT_CAUSE_FOUND",
                "action": "rca_completed",
                "summary": "Database connection pool exhaustion detected due to slow transactional queries.",
                "confidence": 90,
                "tools_used": ["query_logs", "get_metrics"],
                "duration_ms": 1250,
                "entry_status": "SUCCESS",
            }
        }
    )


class IncidentResponse(BaseModel):
    """Client-facing detail representation of an incident."""

    incident_id: str = Field(
        ..., description="Unique incident ID (INC-<8 uppercase hex characters>)."
    )
    title: str = Field(..., description="Human-readable title of the incident.")
    description: str = Field(..., description="Detailed description of the incident.")
    status: str = Field(
        ..., description="Current status in the lifecycle (e.g. INVESTIGATING)."
    )
    severity: str = Field(..., description="Severity level of the incident (P0-P4).")
    environment: str = Field(..., description="Deployment environment.")
    assigned_team: str = Field(
        ..., description="On-call team assigned to the incident."
    )
    recovery_status: str = Field(
        ..., description="Status of recovery actions (e.g. PENDING_APPROVAL)."
    )
    verification_status: str = Field(
        ..., description="Status of recovery verification tests."
    )
    report_status: str = Field(..., description="Status of final report generation.")
    escalation_status: str = Field(..., description="Status of team notifications.")
    created_at: str = Field(..., description="ISO-8601 UTC timestamp of creation.")
    updated_at: str = Field(..., description="ISO-8601 UTC timestamp of last update.")
    summary: str = Field(
        ..., description="One-line summary of the current incident status."
    )
    confidence: int = Field(0, description="Overall pipeline confidence score (0-100).")
    timeline: list[TimelineEntryResponse] = Field(
        default_factory=list, description="Audit log timeline entries."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-A4F3B2C1",
                "title": "Alert: DatabaseDegradation",
                "description": "Triggered on service: checkout-db",
                "status": "INVESTIGATING",
                "severity": "P1",
                "environment": "production",
                "assigned_team": "Database-SRE",
                "recovery_status": "NOT_STARTED",
                "verification_status": "NOT_STARTED",
                "report_status": "NOT_STARTED",
                "escalation_status": "SENT",
                "created_at": "2026-06-27T10:00:00Z",
                "updated_at": "2026-06-27T10:01:30Z",
                "summary": "Triage complete. High latency confirmed on checkout service database.",
                "confidence": 85,
                "timeline": [],
            }
        }
    )


class ReportResponse(BaseModel):
    """Incident report and stakeholder summary."""

    incident_id: str = Field(..., description="Target incident ID.")
    report: str = Field(
        ..., description="Full post-mortem incident report in Markdown format."
    )
    stakeholder_update: str = Field(
        ..., description="Concise, jargon-free summary for stakeholders."
    )
    generated_at: str = Field(
        ..., description="ISO-8601 UTC timestamp of report generation."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-A4F3B2C1",
                "report": "# Incident Post-Mortem Report\n## Summary\nCheckout DB pool full...",
                "stakeholder_update": "The checkout database was temporarily unavailable but has been resolved.",
                "generated_at": "2026-06-27T10:05:00Z",
            }
        }
    )


class AgentStatusResponse(BaseModel):
    """Activity state of an individual agent in the incident pipeline."""

    agent_name: str = Field(
        ..., description="Unique name of the agent (e.g. LogAnalyzerAgent)."
    )
    status: str = Field(
        ..., description="Current execution state (IDLE, RUNNING, COMPLETED, FAILED)."
    )
    last_active_at: str = Field(
        ..., description="ISO-8601 UTC timestamp of the last agent activity."
    )
    duration_ms: int = Field(
        ..., description="Total wall-clock execution duration in milliseconds."
    )
    tools_used: list[str] = Field(
        default_factory=list, description="List of tools called by this agent."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "LogAnalyzerAgent",
                "status": "COMPLETED",
                "last_active_at": "2026-06-27T10:01:25Z",
                "duration_ms": 3200,
                "tools_used": ["query_logs"],
            }
        }
    )


class IncidentAgentsResponse(BaseModel):
    """List of SRE agents involved in analyzing the incident."""

    incident_id: str = Field(..., description="Target incident ID.")
    agents: list[AgentStatusResponse] = Field(
        ..., description="Participating agent statuses."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-A4F3B2C1",
                "agents": [
                    {
                        "agent_name": "IntakeAgent",
                        "status": "COMPLETED",
                        "last_active_at": "2026-06-27T10:00:05Z",
                        "duration_ms": 150,
                        "tools_used": [],
                    }
                ],
            }
        }
    )


class EvaluationResponse(BaseModel):
    """Evaluator validation checks and verdict."""

    incident_id: str = Field(..., description="Target incident ID.")
    verdict: str = Field(..., description="Evaluation verdict (e.g. PASS, FAIL).")
    notes: str = Field(..., description="Evaluation explanation and rationale notes.")
    confidence_score: int = Field(
        ..., description="Evaluator's confidence score (0-100)."
    )
    evaluated_at: str = Field(
        ..., description="ISO-8601 UTC timestamp of the evaluation."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-A4F3B2C1",
                "verdict": "PASS",
                "notes": "Root cause matches the log pattern, and the recovery runbook matches the database type.",
                "confidence_score": 95,
                "evaluated_at": "2026-06-27T10:03:45Z",
            }
        }
    )


class ErrorDetailResponse(BaseModel):
    """Global standardized SRE API error response schema."""

    error_code: str = Field(
        ...,
        description="Structured machine-readable error token (e.g. INCIDENT_NOT_FOUND).",
    )
    message: str = Field(
        ..., description="Detailed human-readable explanation of what went wrong."
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Contextual metadata or sub-errors."
    )
    request_id: str = Field(..., description="Trace identifier of the failed request.")
    timestamp: str = Field(
        ..., description="ISO-8601 UTC timestamp when the error was caught."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "INCIDENT_NOT_FOUND",
                "message": "Incident INC-GHOST was not found in persistence.",
                "details": {"incident_id": "INC-GHOST"},
                "request_id": "4f17c982-8de3-4697-8267-eb3ec27fadcd",
                "timestamp": "2026-06-27T10:12:15.123456+00:00",
            }
        }
    )


class WebSocketEvent(BaseModel):
    """Strict, standardized event schema streamed to all connected clients."""

    event_id: str = Field(..., description="Unique event identifier UUID.")
    timestamp: str = Field(
        ..., description="ISO-8601 UTC timestamp when the event was generated."
    )
    event_type: str = Field(
        ..., description="Standardized event dot-notation type (e.g. agent.started)."
    )
    incident_id: str = Field(..., description="Target incident ID.")
    request_id: str = Field(
        ..., description="Trace request ID that triggered the flow."
    )
    agent: str = Field(
        ...,
        description="Name of the agent generating the event (e.g. IntakeAgent or system).",
    )
    status: str = Field(
        ..., description="Lifecycle status at event time (e.g. INVESTIGATING)."
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Contextual payload payload details."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "e838f712-8e3b-4c22-b5e1-8898b965f32a",
                "timestamp": "2026-06-27T10:02:15.123456+00:00",
                "event_type": "agent.started",
                "incident_id": "INC-A4F3B2C1",
                "request_id": "4f17c982-8de3-4697-8267-eb3ec27fadcd",
                "agent": "RootCauseAgent",
                "status": "INVESTIGATING",
                "payload": {
                    "previous_status": "TRIAGED",
                    "current_status": "INVESTIGATING",
                },
            }
        }
    )
