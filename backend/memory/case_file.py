"""Incident Case File — ADK Session State Schema.

Defines the shared Pydantic state schema used by all SRE agents
throughout the incident lifecycle. All agents read from and write
to this structure via ``ctx.state``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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


class TimelineEntry(BaseModel):
    """A single entry in the incident timeline audit log."""

    timestamp: str = ""
    agent: str = ""
    message: str = ""


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


class IncidentState(BaseModel):
    """Full ADK session state schema for the AI SRE Copilot.

    Shared across all agents in the workflow. Each agent reads the
    current state and writes its specialist output under the
    corresponding section before yielding control back.
    """

    # ---- Incident identity ----
    incident_id: str = ""
    status: str = IncidentStatus.NEW.value
    summary: str = ""

    # ---- Populated by Intake Agent ----
    raw_alert: dict[str, Any] = Field(default_factory=dict)

    # ---- Populated by Triage, Log, RCA, Evaluator, Recovery, Escalation ----
    diagnostics: DiagnosticsSection = Field(default_factory=DiagnosticsSection)
    recommendations: RecommendationsSection = Field(
        default_factory=RecommendationsSection
    )
    escalation: EscalationSection = Field(default_factory=EscalationSection)

    # ---- Populated by Report Generator ----
    report: str = ""
    stakeholder_update: str = ""

    # ---- Timeline audit log (appended by every agent) ----
    timeline: list[TimelineEntry] = Field(default_factory=list)

    # ---- Routing flag used by Coordinator ----
    next_action: str = "triage"
