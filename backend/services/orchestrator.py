"""ADK Workflow Orchestrator service (Phase 6).

Manages background execution of ADK multi-agent workflows, updates
the persistence store, and publishes lifecycle events to the Event Bus.
Provides request tracing propagation across background worker tasks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import Content, Part

from backend.config import GEMINI_API_KEY
from backend.events.event_bus import IncidentEventType, publish_event
from backend.memory.case_file import IncidentState, IncidentStatus
from backend.persistence.base import IncidentStore

logger = logging.getLogger(__name__)


class ADKWorkflowOrchestrator:
    """Orchestrates ADK multi-agent runs in the background.

    Responsible for:
    - Initializing the ADK session and runner
    - Executing the workflow asynchronously
    - Synchronizing the internal ADK state to the JSON store
    - Publishing progress and lifecycle transitions to the Event Bus
    """

    def __init__(self, incident_store: IncidentStore) -> None:
        self.incident_store = incident_store

    async def execute_workflow(
        self, incident_id: str, raw_alert: dict[str, Any], request_id: str = "system"
    ) -> None:
        """Run the multi-agent incident response pipeline.

        Executed as a background task. Does not block the API gateway request.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(
            "ADK workflow started | incident=%s | request_id=%s",
            incident_id,
            request_id,
        )

        # Import coordinator inside method to prevent circular imports
        from backend.agents.coordinator import coordinator

        # 1. Initialize ADK session service and runner
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="ai_sre_copilot",
            agent=coordinator,
            session_service=session_service,
            auto_create_session=True,
        )

        # 2. Build initial state
        initial_state = self.incident_store.load(incident_id)
        if not initial_state.metadata:
            initial_state.metadata = {}
        initial_state.metadata["request_id"] = request_id
        state_delta = initial_state.model_dump()

        # Construct the trigger message
        new_message = Content(
            role="user",
            parts=[
                Part.from_text(
                    text=f"Process alert: {raw_alert.get('name', 'Unknown')}"
                )
            ],
        )

        participating_agents = set()
        mcp_tools_invoked = []
        final_status = "UNKNOWN"
        final_confidence = 0

        # State tracking for dynamic event publishing
        previous_state = initial_state
        current_agent = None
        agent_start_time = None

        # Set up API key in environment if present in config
        if GEMINI_API_KEY:
            import os

            os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

        try:
            # 3. Stream agent execution
            async for event in runner.run_async(
                user_id="sre_user",
                session_id=incident_id,
                new_message=new_message,
                state_delta=state_delta,
            ):
                # Trace participating agent and publish agent.started / agent.completed
                if event.node_info and event.node_info.name:
                    agent_name = event.node_info.name
                    participating_agents.add(agent_name)

                    if current_agent != agent_name:
                        now_ts = datetime.now(timezone.utc)
                        if current_agent is not None:
                            # Complete the previous agent
                            dur = (
                                int((now_ts - agent_start_time).total_seconds() * 1000)
                                if agent_start_time
                                else 0
                            )
                            publish_event(
                                IncidentEventType.AGENT_COMPLETED,
                                incident_id=incident_id,
                                payload={
                                    "request_id": request_id,
                                    "agent": current_agent,
                                    "status": "COMPLETED",
                                    "duration_ms": dur,
                                },
                            )
                        # Start the new agent
                        current_agent = agent_name
                        agent_start_time = now_ts
                        publish_event(
                            IncidentEventType.AGENT_STARTED,
                            incident_id=incident_id,
                            payload={
                                "request_id": request_id,
                                "agent": current_agent,
                                "status": "RUNNING",
                            },
                        )

                # Trace tool calls
                func_calls = event.get_function_calls()
                if func_calls:
                    for tc in func_calls:
                        mcp_tools_invoked.append(tc.name)
                        # We map tool calls to general incident update events
                        publish_event(
                            IncidentEventType.INCIDENT_UPDATED,
                            incident_id=incident_id,
                            payload={
                                "request_id": request_id,
                                "agent": current_agent or "system",
                                "status": previous_state.status,
                                "action": "tool_call",
                                "tool": tc.name,
                            },
                        )

                # Fetch intermediate ADK state, diff and synchronize
                session = await runner.session_service.get_session(
                    app_name="ai_sre_copilot",
                    user_id="sre_user",
                    session_id=incident_id,
                )
                if session and session.state:
                    current_state = IncidentState.model_validate(session.state)
                    # Propagate request_id to metadata
                    if not current_state.metadata:
                        current_state.metadata = {}
                    current_state.metadata["request_id"] = request_id

                    self.incident_store.update(current_state)

                    # Check for status changes
                    if current_state.status != previous_state.status:
                        publish_event(
                            IncidentEventType.INCIDENT_UPDATED,
                            incident_id=incident_id,
                            payload={
                                "request_id": request_id,
                                "agent": current_agent or "system",
                                "status": current_state.status,
                                "previous_status": previous_state.status,
                                "new_status": current_state.status,
                            },
                        )

                    # Check for root cause detected
                    if (
                        current_state.diagnostics.root_cause
                        and not previous_state.diagnostics.root_cause
                    ):
                        publish_event(
                            IncidentEventType.ROOT_CAUSE_DETECTED,
                            incident_id=incident_id,
                            payload={
                                "request_id": request_id,
                                "agent": "RootCauseAgent",
                                "status": current_state.status,
                                "root_cause": current_state.diagnostics.root_cause,
                            },
                        )

                    # Check for evaluation verdict
                    if (
                        current_state.diagnostics.evaluator_verdict
                        and not previous_state.diagnostics.evaluator_verdict
                    ):
                        publish_event(
                            IncidentEventType.EVALUATION_COMPLETED,
                            incident_id=incident_id,
                            payload={
                                "request_id": request_id,
                                "agent": "EvaluatorAgent",
                                "status": current_state.status,
                                "verdict": current_state.diagnostics.evaluator_verdict,
                                "notes": current_state.diagnostics.evaluation_notes,
                                "confidence_score": current_state.diagnostics.confidence_score,
                            },
                        )

                    # Check for report generated
                    if current_state.report and not previous_state.report:
                        publish_event(
                            IncidentEventType.REPORT_GENERATED,
                            incident_id=incident_id,
                            payload={
                                "request_id": request_id,
                                "agent": "ReportGeneratorAgent",
                                "status": current_state.status,
                            },
                        )

                    previous_state = current_state

            # Complete the final running agent
            if current_agent is not None:
                dur = (
                    int(
                        (datetime.now(timezone.utc) - agent_start_time).total_seconds()
                        * 1000
                    )
                    if agent_start_time
                    else 0
                )
                publish_event(
                    IncidentEventType.AGENT_COMPLETED,
                    incident_id=incident_id,
                    payload={
                        "request_id": request_id,
                        "agent": current_agent,
                        "status": "COMPLETED",
                        "duration_ms": dur,
                    },
                )

            # 4. Save final state
            final_session = await runner.session_service.get_session(
                app_name="ai_sre_copilot",
                user_id="sre_user",
                session_id=incident_id,
            )
            if final_session and final_session.state:
                final_state_obj = IncidentState.model_validate(final_session.state)
                final_status = final_state_obj.status
                final_confidence = final_state_obj.diagnostics.confidence_score
                if not final_state_obj.metadata:
                    final_state_obj.metadata = {}
                final_state_obj.metadata["request_id"] = request_id
                self.incident_store.update(final_state_obj)
            else:
                final_status = previous_state.status  # Fallback to last seen status

            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            logger.info(
                "ADK workflow finished | incident=%s | request_id=%s | duration_ms=%d | agents=%s | tools=%s | confidence=%d | status=%s",
                incident_id,
                request_id,
                duration_ms,
                list(participating_agents),
                mcp_tools_invoked,
                final_confidence,
                final_status,
            )

        except Exception as exc:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            logger.error(
                "ADK workflow failed | incident=%s | request_id=%s | error=%s",
                incident_id,
                request_id,
                exc,
                exc_info=True,
            )

            # Escalate the incident on hard failure
            try:
                state = self.incident_store.load(incident_id)
                state.status = IncidentStatus.ESCALATED.value
                state.updated_at = datetime.now(timezone.utc).isoformat()
                if not state.metadata:
                    state.metadata = {}
                state.metadata["request_id"] = request_id

                # Append crash timeline entry
                from backend.utils.incident_utils import make_timeline_entry

                crash_entry = make_timeline_entry(
                    agent_name="system",
                    event_type="ERROR",
                    action="workflow_failed",
                    summary=f"ADK runner workflow exception: {exc}",
                    status="FAILURE",
                )
                state.timeline.append(crash_entry)
                self.incident_store.update(state)
            except Exception as transition_exc:
                logger.error(
                    "Failed to transition state to ESCALATED | incident=%s | error=%s",
                    incident_id,
                    transition_exc,
                )

            publish_event(
                IncidentEventType.ERROR,
                incident_id=incident_id,
                payload={
                    "request_id": request_id,
                    "error": str(exc),
                    "duration_ms": duration_ms,
                },
            )
        finally:
            await runner.close()
