"""REST API routes for incident management (Phase 8 — Security Hardened).

Phase 8 additions:
  - Prompt injection check (all 3 layers) wired into create_incident
  - Audit logging for incident creation and security rejections
  - Incident ID format validation on path parameters
  - trace_id propagated from request state into all operations
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from backend.api.dto import (
    AgentStatusResponse,
    ErrorDetailResponse,
    EvaluationResponse,
    IncidentAgentsResponse,
    IncidentCreateRequest,
    IncidentResponse,
    ReportResponse,
    TimelineEntryResponse,
)
from backend.events.event_bus import IncidentEventType, publish_event
from backend.memory.case_file import IncidentState, IncidentStatus
from backend.persistence.base import IncidentNotFoundError, IncidentStore
from backend.security.audit_logger import audit_logger
from backend.security.input_validator import validate_incident_payload
from backend.services.orchestrator import ADKWorkflowOrchestrator
from backend.utils.incident_utils import (
    generate_incident_id,
    make_timeline_entry,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Incidents"])

# Incident ID format: INC-XXXXXXXX (8 uppercase hex chars)
_INCIDENT_ID_RE = re.compile(r"^INC-[A-F0-9]{8}$")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_store(request: Request) -> IncidentStore:
    """Dependency to retrieve the active IncidentStore from app state."""
    return request.app.state.store


def get_orchestrator(request: Request) -> ADKWorkflowOrchestrator:
    """Dependency to retrieve the ADKWorkflowOrchestrator from app state."""
    return request.app.state.orchestrator


def get_request_ids(request: Request) -> tuple[str, str]:
    """Dependency to extract request_id and trace_id from request state."""
    request_id = getattr(request.state, "request_id", "system")
    trace_id = getattr(request.state, "trace_id", "system")
    return request_id, trace_id


def _validate_incident_id_param(incident_id: str) -> str:
    """Validate incident_id path parameter format."""
    if not _INCIDENT_ID_RE.match(incident_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid incident_id format '{incident_id}'. "
                "Expected format: INC-XXXXXXXX (8 uppercase hex characters)."
            ),
        )
    return incident_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "model": ErrorDetailResponse,
            "description": "Invalid payload / injection blocked",
        },
        422: {"model": ErrorDetailResponse, "description": "Validation error"},
        429: {"model": ErrorDetailResponse, "description": "Rate limit exceeded"},
    },
    summary="Create a new incident and trigger investigation",
    description=(
        "Intakes a raw SRE alert, passes it through the 3-layer security filter "
        "(rule-based + structural + LLM classifier), then initializes a new incident "
        "case file and schedules the multi-agent investigation workflow in the background."
    ),
)
async def create_incident(
    payload: IncidentCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    store: IncidentStore = Depends(get_store),
    orchestrator: ADKWorkflowOrchestrator = Depends(get_orchestrator),
) -> Any:
    """Create a new incident. Runs full 3-layer injection check before orchestrator."""
    request_id, trace_id = get_request_ids(request)
    incident_id = generate_incident_id()

    # ── Phase 8: 3-Layer Prompt Injection Check ───────────────────────────────
    try:
        injection_result = await validate_incident_payload(payload)
    except Exception as exc:
        # Fail-open: if validator itself errors, log warning and proceed
        logger.warning(
            "Injection validator error (fail-open) | request_id=%s | error=%s",
            request_id,
            exc,
        )
        injection_result = None

    if injection_result and injection_result.blocked:
        # Log security rejection to audit trail
        audit_logger.log_security_rejection(
            request_id=request_id,
            trace_id=trace_id,
            incident_id=incident_id,
            error_code=injection_result.error_code,
            field=injection_result.field,
            layer=injection_result.layer,
            actor="user",
            metadata={
                "endpoint": "create_incident",
                "message": injection_result.message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": injection_result.error_code,
                "message": injection_result.message,
                "incident_id": incident_id,
                "request_id": request_id,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # ── Build Incident State ──────────────────────────────────────────────────
    now = utc_now_iso()
    title = payload.title or f"Alert: {payload.raw_alert.get('name', 'Unknown Alert')}"
    desc = (
        payload.description
        or f"Triggered on service: {payload.raw_alert.get('service', 'unknown')}"
    )
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
        metadata={"request_id": request_id, "trace_id": trace_id},
    )

    entry = make_timeline_entry(
        agent_name="system",
        event_type="INCIDENT_CREATED",
        action="incident_created",
        summary=f"Incident registered via API. Severity: {payload.raw_alert.get('severity', 'P1')}",
    )
    state.timeline.append(entry)

    store.save(state)
    logger.info(
        "Incident created | incident=%s | request_id=%s | trace_id=%s",
        incident_id,
        request_id,
        trace_id,
    )

    # ── Phase 8: Audit Log — incident creation ────────────────────────────────
    audit_logger.log_incident_created(
        request_id=request_id,
        trace_id=trace_id,
        incident_id=incident_id,
        actor="user",
        metadata={
            "severity": severity,
            "environment": payload.environment,
            "alert_name": payload.raw_alert.get("name", ""),
        },
    )

    # ── Publish Event Bus ─────────────────────────────────────────────────────
    publish_event(
        IncidentEventType.INCIDENT_CREATED,
        incident_id=incident_id,
        payload={
            "request_id": request_id,
            "trace_id": trace_id,
            "agent": "system",
            "status": state.status,
            "environment": state.environment,
        },
    )

    # ── Queue Background ADK Workflow ─────────────────────────────────────────
    background_tasks.add_task(
        orchestrator.execute_workflow,
        incident_id=incident_id,
        raw_alert=payload.raw_alert,
        request_id=request_id,
    )

    return _to_incident_response(state)


@router.get(
    "",
    response_model=list[IncidentResponse],
    responses={
        500: {"model": ErrorDetailResponse, "description": "Internal server error"},
    },
    summary="List all incidents",
    description="Returns a list of all active (non-archived) SRE incident case files.",
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
    responses={
        400: {
            "model": ErrorDetailResponse,
            "description": "Invalid incident_id format",
        },
        404: {"model": ErrorDetailResponse, "description": "Incident not found"},
    },
    summary="Retrieve incident details",
    description="Loads a specific incident case file by its ID.",
)
async def get_incident(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    # Phase 8: Validate ID format
    _validate_incident_id_param(incident_id)
    state = store.load(incident_id)
    return _to_incident_response(state)


@router.get(
    "/{incident_id}/timeline",
    response_model=list[TimelineEntryResponse],
    responses={
        400: {
            "model": ErrorDetailResponse,
            "description": "Invalid incident_id format",
        },
        404: {"model": ErrorDetailResponse, "description": "Incident not found"},
    },
    summary="Retrieve incident timeline audit log",
    description="Returns the full chronological timeline of events for the incident.",
)
async def get_incident_timeline(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    _validate_incident_id_param(incident_id)
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


@router.get(
    "/{incident_id}/report",
    response_model=ReportResponse,
    responses={
        400: {"model": ErrorDetailResponse, "description": "Report not yet generated"},
        404: {"model": ErrorDetailResponse, "description": "Incident not found"},
    },
    summary="Retrieve post-mortem report and stakeholder update",
    description="Loads the markdown report compiled by the Report Generator Agent.",
)
async def get_incident_report(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    _validate_incident_id_param(incident_id)
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


@router.get(
    "/{incident_id}/agents",
    response_model=IncidentAgentsResponse,
    responses={
        400: {
            "model": ErrorDetailResponse,
            "description": "Invalid incident_id format",
        },
        404: {"model": ErrorDetailResponse, "description": "Incident not found"},
    },
    summary="Retrieve participating SRE agents status",
    description="Compiles execution metrics and statuses for all agents involved.",
)
async def get_incident_agents(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    _validate_incident_id_param(incident_id)
    try:
        state = store.load(incident_id)
        agents_map = {}
        for entry in state.timeline:
            agent_name = entry.agent_name or entry.agent
            if not agent_name or agent_name == "system":
                continue

            event_type_str = (
                str(entry.event_type.value)
                if hasattr(entry.event_type, "value")
                else str(entry.event_type)
            )

            if "started" in event_type_str.lower() or "run" in entry.action.lower():
                status_val = "RUNNING"
            elif "failed" in event_type_str.lower() or entry.entry_status == "FAILURE":
                status_val = "FAILED"
            else:
                status_val = "COMPLETED"

            agents_map[agent_name] = AgentStatusResponse(
                agent_name=agent_name,
                status=status_val,
                last_active_at=entry.timestamp or utc_now_iso(),
                duration_ms=entry.duration_ms,
                tools_used=entry.tools_used,
            )

        return IncidentAgentsResponse(
            incident_id=incident_id,
            agents=list(agents_map.values()),
        )
    except IncidentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )


@router.get(
    "/{incident_id}/evaluation",
    response_model=EvaluationResponse,
    responses={
        400: {
            "model": ErrorDetailResponse,
            "description": "Invalid incident_id format",
        },
        404: {"model": ErrorDetailResponse, "description": "Incident not found"},
    },
    summary="Retrieve evaluator results",
    description="Loads the evaluation validation status produced by the Evaluator Agent.",
)
async def get_incident_evaluation(
    incident_id: str,
    store: IncidentStore = Depends(get_store),
) -> Any:
    _validate_incident_id_param(incident_id)
    try:
        state = store.load(incident_id)
        return EvaluationResponse(
            incident_id=incident_id,
            verdict=state.diagnostics.evaluator_verdict or "NOT_STARTED",
            notes=state.diagnostics.evaluation_notes or "Evaluation not yet performed.",
            confidence_score=state.diagnostics.confidence_score,
            evaluated_at=state.updated_at,
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
    """Map internal IncidentState to IncidentResponse DTO."""
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
