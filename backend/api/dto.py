"""API Data Transfer Objects (DTOs) for the FastAPI Gateway (Phase 5).

Separates the internal database/Pydantic state schemas (IncidentState)
from the client-facing REST API interface.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncidentCreateRequest(BaseModel):
    """Payload to create and trigger a new incident investigation workflow."""

    title: str = Field(
        default="",
        description="Optional human-readable title of the incident.",
    )
    description: str = Field(
        default="",
        description="Optional detailed description of the incident.",
    )
    environment: str = Field(
        default="production",
        description="Target deployment environment (e.g. production, staging).",
    )
    raw_alert: dict[str, Any] = Field(
        default_factory=dict,
        description="The raw alert payload from Prometheus, Alertmanager, etc.",
    )


class TimelineEntryResponse(BaseModel):
    """Client-facing representation of a timeline event."""

    timestamp: str
    agent_name: str
    event_type: str
    action: str
    summary: str
    confidence: int
    tools_used: list[str]
    duration_ms: int
    entry_status: str


class IncidentResponse(BaseModel):
    """Client-facing detail representation of an incident."""

    incident_id: str
    title: str
    description: str
    status: str
    severity: str
    environment: str
    assigned_team: str
    recovery_status: str
    verification_status: str
    report_status: str
    escalation_status: str
    created_at: str
    updated_at: str
    summary: str
    confidence: int = 0
    timeline: list[TimelineEntryResponse] = Field(default_factory=list)


class ReportResponse(BaseModel):
    """Incident report and stakeholder summary."""

    incident_id: str
    report: str
    stakeholder_update: str
    generated_at: str
