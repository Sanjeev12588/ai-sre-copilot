"""REST API routes for incident management (Phase 5).

Provides endpoints to create, list, and inspect incidents, including
retrieving their timeline audit logs and final post-mortem reports.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from backend.api.dto import (
    IncidentCreateRequest,
    IncidentResponse,
    ReportResponse,
    TimelineEntryResponse,
)
from backend.events.event_bus import IncidentEventType, publish_event
from backend.memory.case_file import IncidentState, IncidentStatus
from backend.persistence.base import IncidentNotFoundError, IncidentStore
from backend.services.orchestrator import ADKWorkflowOrchestrator
from backend.utils.incident_utils import (
    generate_incident_id,
    make_timeline_entry,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_store(request: Request) -> IncidentStore:
    """Dependency to retrieve the active IncidentStore from app state."""
    return request.app.state.store


def get_orchestrator(request: Request) -> ADKWorkflowOrchestrator:
    """Dependency to retrieve the ADKWorkflowOrchestrator from app state."""
    return request.app.state.orchestrator


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new incident and trigger investigation",
)
async def create_incident(
    payload: IncidentCreateRequest,
    background_tasks: BackgroundTasks,
    store: IncidentStore = Depends(get_store),
    orchestrator: ADKWorkflowOrchestrator = Depends(get_orchestrator),
) -> Any:
    """Create a new incident record and launch the investigation workflow.

    Runs the ADK multi-agent workflow in the background.
    """
    incident_id = generate_incident_id()
    now = utc_now_iso()

    # Pre-populate title/description if not provided
    title = payload.title or f"Alert: {payload.raw_alert.get('name', 'Unknown Alert')}"
    desc = (
        payload.description
        or f"Triggered on service: {payload.raw_alert.get('service', 'unknown')}"
    )

    # Build the initial incident state
    severity = payload.raw_alert.get("severity", "P1")
    state = IncidentState(
        incident_id=incident_id,
        title=title,
        description=desc,
        status=IncidentStatus.NEW.value,
        severity=severity,
        environment=payload.environment,
        raw_alert=payload.raw_alert,
        created_at=now,
        updated_at=now,
    )

    # Append first timeline entry
    entry = make_timeline_entry(
        agent_name="system",
        event_type="INCIDENT_CREATED",
        action="incident_created",
        summary=f"Incident registered via API. Severity: {payload.raw_alert.get('severity', 'P1')}",
    )
    state.timeline.append(entry)

    # Save to persistence
    store.save(state)
    logger.info("Incident created | incident=%s", incident_id)

    # Publish lifecycle event
    publish_event(
        IncidentEventType.INCIDENT_CREATED,
        incident_id=incident_id,
        payload={"status": state.status, "environment": state.environment},
    )

    # Queue the long-running ADK multi-agent workflow as a background task
    background_tasks.add_task(
        orchestrator.execute_workflow,
        incident_id=incident_id,
        raw_alert=payload.raw_alert,
    )

    return _to_incident_response(state)


@router.get(
    "",
    response_model=list[IncidentResponse],
    summary="List all incidents",
)
async def list_incidents(store: IncidentStore = Depends(get_store)) -> Any:
    """Return all active (non-archived) incidents."""
    incident_ids = store.list_incidents()
    results = []
    for inc_id in incident_ids:
        try:
            state = store.load(inc_id)
            results.append(_to_incident_response(state))
        except Exception as exc:
            logger.error("Failed to load incident %s | error=%s", inc_id, exc)
            continue
    return results


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Retrieve incident details",
)
async def get_incident(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    """Retrieve details for a specific incident."""
    try:
        state = store.load(incident_id)
        return _to_incident_response(state)
    except IncidentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )


@router.get(
    "/{incident_id}/timeline",
    response_model=list[TimelineEntryResponse],
    summary="Retrieve incident timeline audit log",
)
async def get_incident_timeline(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    """Retrieve the event timeline for a specific incident."""
    try:
        state = store.load(incident_id)
        return [
            TimelineEntryResponse(
                timestamp=entry.timestamp,
                agent_name=entry.agent_name or entry.agent,
                event_type=str(entry.event_type.value)
                if hasattr(entry.event_type, "value")
                else str(entry.event_type),
                action=entry.action,
                summary=entry.summary or entry.message,
                confidence=entry.confidence,
                tools_used=entry.tools_used,
                duration_ms=entry.duration_ms,
                entry_status=entry.entry_status,
            )
            for entry in state.timeline
        ]
    except IncidentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )


@router.get(
    "/{incident_id}/report",
    response_model=ReportResponse,
    summary="Retrieve post-mortem report and stakeholder update",
)
async def get_incident_report(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    """Retrieve the generated post-mortem report and non-technical summary."""
    try:
        state = store.load(incident_id)
        if not state.report:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report has not yet been generated for incident {incident_id}.",
            )
        return ReportResponse(
            incident_id=incident_id,
            report=state.report,
            stakeholder_update=state.stakeholder_update,
            generated_at=state.updated_at,
        )
    except IncidentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _to_incident_response(state: IncidentState) -> IncidentResponse:
    """Map internal IncidentState model to IncidentResponse DTO."""
    return IncidentResponse(
        incident_id=state.incident_id,
        title=state.title,
        description=state.description,
        status=state.status,
        severity=state.diagnostics.severity or state.severity,
        environment=state.environment,
        assigned_team=state.assigned_team,
        recovery_status=state.recovery_status,
        verification_status=state.verification_status,
        report_status=state.report_status,
        escalation_status=state.escalation_status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        summary=state.summary,
        confidence=state.diagnostics.confidence_score,
        timeline=[
            TimelineEntryResponse(
                timestamp=entry.timestamp,
                agent_name=entry.agent_name or entry.agent,
                event_type=str(entry.event_type.value)
                if hasattr(entry.event_type, "value")
                else str(entry.event_type),
                action=entry.action,
                summary=entry.summary or entry.message,
                confidence=entry.confidence,
                tools_used=entry.tools_used,
                duration_ms=entry.duration_ms,
                entry_status=entry.entry_status,
            )
            for entry in state.timeline
        ],
    )
