"""ADK Workflow Orchestrator service (Phase 5).

Manages background execution of ADK multi-agent workflows, updates
the persistence store, and publishes lifecycle events to the Event Bus.
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
        self, incident_id: str, raw_alert: dict[str, Any]
    ) -> None:
        """Run the multi-agent incident response pipeline.

        Executed as a background task. Does not block the API gateway request.
        """
        start_time = datetime.now(timezone.utc)
        logger.info("ADK workflow started | incident=%s", incident_id)

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
                # Trace participating agent
                if event.node_info and event.node_info.name:
                    participating_agents.add(event.node_info.name)

                # Trace tool calls
                if event.actions and event.actions.tool_calls:
                    for tc in event.actions.tool_calls:
                        mcp_tools_invoked.append(tc.function_name)
                        publish_event(
                            IncidentEventType.TIMELINE_UPDATED,
                            incident_id=incident_id,
                            payload={
                                "event": "tool_call",
                                "agent": event.node_info.name,
                                "tool": tc.function_name,
                            },
                        )

                # Fetch intermediate ADK state and save it
                session = await runner.session_service.get_session(
                    app_name="ai_sre_copilot",
                    user_id="sre_user",
                    session_id=incident_id,
                )
                if session and session.state:
                    current_state = IncidentState.model_validate(session.state)
                    self.incident_store.update(current_state)
                    publish_event(
                        IncidentEventType.TIMELINE_UPDATED,
                        incident_id=incident_id,
                        payload={
                            "event": "state_sync",
                            "status": current_state.status,
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
                self.incident_store.update(final_state_obj)
            else:
                final_status = "RESOLVED"  # Fallback to resolved when complete

            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            logger.info(
                "ADK workflow finished | incident=%s | duration_ms=%d | agents=%s | tools=%s | confidence=%d | status=%s",
                incident_id,
                duration_ms,
                list(participating_agents),
                mcp_tools_invoked,
                final_confidence,
                final_status,
            )

            # Publish completion event
            publish_event(
                IncidentEventType.AGENT_COMPLETED,
                incident_id=incident_id,
                payload={
                    "status": final_status,
                    "confidence": final_confidence,
                    "duration_ms": duration_ms,
                    "agents": list(participating_agents),
                },
            )

        except Exception as exc:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            logger.error(
                "ADK workflow failed | incident=%s | error=%s",
                incident_id,
                exc,
                exc_info=True,
            )

            # Escalate the incident on hard failure
            try:
                state = self.incident_store.load(incident_id)
                state.status = IncidentStatus.ESCALATED.value
                state.updated_at = datetime.now(timezone.utc).isoformat()

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
                    "error": str(exc),
                    "duration_ms": duration_ms,
                },
            )
        finally:
            await runner.close()
