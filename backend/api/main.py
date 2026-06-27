"""FastAPI Application Gateway entrypoint (Phase 6).

Connects Google ADK Multi-Agent Orchestrator, Event Bus, Session Memory,
and Persistence Layer, providing a secure real-time SRE API gateway.
Provides contract freeze stability, global error formats, request tracing,
and backward compatibility support.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.routes import router as incident_router
from backend.api.websocket import manager
from backend.config import (
    ALLOWED_CORS_ORIGINS,
    ENV,
    LOG_LEVEL,
    MAX_PAYLOAD_SIZE_BYTES,
    PERSISTENCE_DIR,
    WS_HEARTBEAT_INTERVAL,
)
from backend.events.event_bus import IncidentEvent, clear_listeners, subscribe
from backend.memory.lifecycle import InvalidTransitionError
from backend.persistence.base import IncidentNotFoundError, IncidentStore
from backend.persistence.json_store import JsonIncidentStore
from backend.services.orchestrator import ADKWorkflowOrchestrator

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan Management
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise and clean up application resources."""
    logger.info("Starting up FastAPI application Gateway...")

    # 1. Initialize incident persistence store (JSON-based)
    store = JsonIncidentStore(store_dir=PERSISTENCE_DIR)
    app.state.store = store

    # 2. Initialize ADK workflow orchestrator
    orchestrator = ADKWorkflowOrchestrator(incident_store=store)
    app.state.orchestrator = orchestrator

    # 3. Start WebSocket heartbeat check loop
    heartbeat_task = asyncio.create_task(
        manager.start_heartbeat_loop(interval=WS_HEARTBEAT_INTERVAL)
    )

    # 4. Subscribe the WebSocket manager to the Event Bus
    def event_bus_websocket_bridge(event: IncidentEvent) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Standardize WebSocket Event Payload mapping dynamically (Phase 6 Specs)
            internal_type = event.event_type.value
            event_type_lower = internal_type.lower()

            payload = event.payload
            agent = payload.get("agent") or "system"
            status_val = payload.get("status") or "UNKNOWN"
            request_id = payload.get("request_id") or "system"

            # Strict event type dot-notation translation
            if "created" in event_type_lower:
                mapped_type = "incident.created"
            elif "error" in event_type_lower:
                mapped_type = "incident.error"
            elif (
                "agent_started" in event_type_lower
                or "agent.started" in event_type_lower
            ):
                mapped_type = "agent.started"
            elif (
                "agent_completed" in event_type_lower
                or "agent.completed" in event_type_lower
            ):
                mapped_type = "agent.completed"
            elif "root_cause" in event_type_lower or "rootcause" in event_type_lower:
                mapped_type = "root_cause.detected"
            elif "report" in event_type_lower:
                mapped_type = "report.generated"
            elif "evaluation" in event_type_lower:
                mapped_type = "evaluation.completed"
            else:
                mapped_type = "incident.updated"

            # Standardized event contract schema
            ws_payload = {
                "event_id": str(uuid.uuid4()),
                "timestamp": event.timestamp,
                "event_type": mapped_type,
                "incident_id": event.incident_id,
                "request_id": request_id,
                "agent": agent,
                "status": status_val,
                "event_type_original": event.event_type.value,
                "payload": payload,
            }
            loop.create_task(
                manager.broadcast_to_channel(event.incident_id, ws_payload)
            )

    subscribe(event_bus_websocket_bridge)
    logger.info("App Startup complete: Store, Orchestrator, and event bridge running.")

    yield

    # Shutdown:
    # 1. Cancel background heartbeat loop
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass

    # 2. Clear Event Bus subscriptions to prevent leaks
    clear_listeners()
    logger.info("FastAPI Application Gateway shutdown complete.")


# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------


app = FastAPI(
    title="AI SRE Copilot Application Gateway",
    description="Application gateway connecting SRE agents, MCP servers, and persistent case files.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    """Limits the max body size of incoming HTTP requests to prevent DoS."""

    def __init__(self, app: Any, max_size_bytes: int) -> None:
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size_bytes:
            # Format using unified error response format
            request_id = getattr(request.state, "request_id", "system")
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error_code": "PAYLOAD_TOO_LARGE",
                    "message": f"Payload too large. Limit is {self.max_size_bytes} bytes.",
                    "details": {},
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        return await call_next(request)


class LoggingAndSecurityMiddleware(BaseHTTPMiddleware):
    """Generates request IDs, records execution time, and injects secure headers."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # In SRE context, try to identify incident_id in path
        path_parts = request.url.path.strip("/").split("/")
        incident_id = "none"
        if len(path_parts) > 2 and path_parts[2] == "incidents" and len(path_parts) > 3:
            incident_id = path_parts[3]

        start_time = time.time()
        response: Response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Inject Security Headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Log API access
        logger.info(
            "API Request | request_id=%s | incident=%s | method=%s | path=%s | status=%d | duration_ms=%d",
            request_id,
            incident_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response


# Register middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PayloadLimitMiddleware, max_size_bytes=MAX_PAYLOAD_SIZE_BYTES)
app.add_middleware(LoggingAndSecurityMiddleware)


# ---------------------------------------------------------------------------
# Global Standardized Exception Handlers (Phase 6)
# ---------------------------------------------------------------------------


@app.exception_handler(IncidentNotFoundError)
async def handle_incident_not_found(
    request: Request, exc: IncidentNotFoundError
) -> JSONResponse:
    """Unified error handler for missing incident lookups."""
    request_id = getattr(request.state, "request_id", "system")
    msg = str(exc)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error_code": "INCIDENT_NOT_FOUND",
            "message": msg,
            "details": {},
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": msg,
        },
    )


@app.exception_handler(InvalidTransitionError)
async def handle_invalid_transition(
    request: Request, exc: InvalidTransitionError
) -> JSONResponse:
    """Unified error handler for illegal state transitions."""
    request_id = getattr(request.state, "request_id", "system")
    msg = str(exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "INVALID_STATUS_TRANSITION",
            "message": msg,
            "details": {},
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": msg,
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Unified error handler for body/query parameter parsing errors."""
    request_id = getattr(request.state, "request_id", "system")
    msg = "The request body failed schema validation checks."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": msg,
            "details": {"errors": exc.errors()},
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": msg,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Unified error handler for standard HTTP Exceptions."""
    request_id = getattr(request.state, "request_id", "system")
    code_map = {
        404: "NOT_FOUND",
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        405: "METHOD_NOT_ALLOWED",
    }
    err_code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": err_code,
            "message": exc.detail,
            "details": {},
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def handle_general_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unified handler for internal server crashes."""
    request_id = getattr(request.state, "request_id", "system")
    logger.exception(
        "Unhandled gateway crash | request_id=%s | error=%s", request_id, exc
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred inside the gateway.",
            "details": {"exception": str(exc)} if ENV != "production" else {},
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": "An unexpected error occurred inside the gateway.",
        },
    )


# ---------------------------------------------------------------------------
# REST Routes
# ---------------------------------------------------------------------------


# Register both prefixes to support standardized paths and legacy paths concurrently
app.include_router(incident_router, prefix="/api/v1/incidents")
app.include_router(incident_router, prefix="/api/incidents")


# Health/Readiness Endpoints registered under both V1 prefix and root aliases
@app.get("/health", summary="Health check alias")
@app.get("/api/health", summary="Health check alias")
@app.get("/api/v1/health", summary="Standardized health check")
async def health_check() -> dict[str, str]:
    """Basic health check verifying the application gateway is running."""
    return {"status": "healthy", "environment": ENV, "timestamp": str(time.time())}


@app.get("/ready", summary="Readiness check alias")
@app.get("/api/ready", summary="Readiness check alias")
@app.get("/api/v1/ready", summary="Standardized readiness check")
async def readiness_check(request: Request) -> Response:
    """Verify that all upstream systems (like persistence directory) are ready."""
    store: IncidentStore = request.app.state.store
    try:
        store.list_incidents()
        return JSONResponse(content={"status": "ready", "persistence": "healthy"})
    except Exception as exc:
        logger.error("Readiness check failed | error=%s", exc)
        request_id = getattr(request.state, "request_id", "system")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error_code": "SERVICE_UNAVAILABLE",
                "message": f"Readiness check failed: {exc}",
                "details": {},
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                # Keep backward compatibility with test_api.py ready failure
                "status": "not_ready",
                "detail": f"Persistence layer failure: {exc}",
            },
        )


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/incidents/{incident_id}")
async def websocket_incident_stream(websocket: WebSocket, incident_id: str) -> None:
    """Real-time incident execution websocket channel."""
    await manager.connect(websocket, incident_id)
    try:
        while True:
            # Handle incoming ping/pong or control messages from frontend clients
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "pong":
                    logger.debug(
                        "Heartbeat pong received from client | incident=%s", incident_id
                    )
            except Exception:
                pass  # ignore malformed messages
    except WebSocketDisconnect:
        await manager.disconnect(websocket, incident_id)
    except Exception as exc:
        logger.debug(
            "WebSocket connection exception | incident=%s | error=%s",
            incident_id,
            exc,
        )
        await manager.disconnect(websocket, incident_id)
