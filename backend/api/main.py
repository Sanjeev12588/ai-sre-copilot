"""FastAPI Application Gateway entrypoint (Phase 8 — Security Hardened).

Connects Google ADK Multi-Agent Orchestrator, Event Bus, Session Memory,
and Persistence Layer, providing a secure real-time SRE API gateway.

Phase 8 additions:
  - RateLimitMiddleware: per-IP sliding window rate limiting (10 req/sec)
  - RequestTimeoutMiddleware: 30s hard timeout on all HTTP requests
  - Enhanced security headers: CSP, HSTS, Referrer-Policy
  - Trace ID injection: X-Trace-ID propagated through all log entries
  - CORS strict mode: explicit methods/headers (no wildcard)
  - WebSocket hardening: incident_id format validation + connection limits
  - Audit logger initialized on startup
  - Security routes registered
"""

from __future__ import annotations

import asyncio
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
    AUDIT_LOG_DIR,
    ENV,
    LOG_LEVEL,
    MAX_PAYLOAD_SIZE_BYTES,
    PERSISTENCE_DIR,
    RATE_LIMIT_PER_IP_RPS,
    RATE_LIMIT_WINDOW_SECS,
    REQUEST_ID_HEADER,
    REQUEST_TIMEOUT_SECS,
    TRACE_ID_HEADER,
    WS_HEARTBEAT_INTERVAL,
)
from backend.events.event_bus import IncidentEvent, clear_listeners, subscribe
from backend.memory.lifecycle import InvalidTransitionError
from backend.persistence.base import IncidentNotFoundError, IncidentStore
from backend.persistence.json_store import JsonIncidentStore
from backend.security.audit_logger import audit_logger
from backend.security.rate_limiter import rate_limiter
from backend.security.ws_security import (
    check_connection_limit,
    check_ws_rate_limit,
    validate_inbound_message,
    validate_incident_id,
    validate_outbound_event,
)
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
    logger.info(
        "Starting up FastAPI Application Gateway (Phase 8 — Security Hardened)..."
    )

    # 1. Initialize audit logger (hash-chained JSONL)
    audit_logger.initialize(AUDIT_LOG_DIR)
    logger.info("Audit logger initialized | dir=%s", AUDIT_LOG_DIR)

    # 2. Initialize incident persistence store
    store = JsonIncidentStore(store_dir=PERSISTENCE_DIR)
    app.state.store = store

    # 3. Initialize ADK workflow orchestrator
    orchestrator = ADKWorkflowOrchestrator(incident_store=store)
    app.state.orchestrator = orchestrator

    # 4. Start WebSocket heartbeat loop
    heartbeat_task = asyncio.create_task(
        manager.start_heartbeat_loop(interval=WS_HEARTBEAT_INTERVAL)
    )

    # 5. Subscribe WebSocket manager to Event Bus
    def event_bus_websocket_bridge(event: IncidentEvent) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            internal_type = event.event_type.value
            event_type_lower = internal_type.lower()

            payload = event.payload
            agent = payload.get("agent") or "system"
            status_val = payload.get("status") or "UNKNOWN"
            request_id = payload.get("request_id") or "system"
            trace_id = payload.get("trace_id") or "system"

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

            raw_ws_payload = {
                "event_id": str(uuid.uuid4()),
                "timestamp": event.timestamp,
                "event_type": mapped_type,
                "incident_id": event.incident_id,
                "request_id": request_id,
                "trace_id": trace_id,
                "agent": agent,
                "source": agent,
                "severity": "info",
                "status": status_val,
                "event_type_original": event.event_type.value,
                "payload": payload,
            }

            # Phase 8: Validate + sanitize outbound event before broadcast
            ws_result = validate_outbound_event(raw_ws_payload)
            if ws_result.valid and ws_result.sanitized_event:
                # Check WS rate limit for this incident channel
                if check_ws_rate_limit(event.incident_id):
                    loop.create_task(
                        manager.broadcast_to_channel(
                            event.incident_id, ws_result.sanitized_event
                        )
                    )
                    # Log to audit trail
                    audit_logger.log_websocket_event(
                        trace_id=trace_id,
                        incident_id=event.incident_id,
                        event_type=mapped_type,
                        source=agent,
                    )
                else:
                    logger.warning(
                        "WS event rate limit exceeded | incident=%s | type=%s",
                        event.incident_id,
                        mapped_type,
                    )

    subscribe(event_bus_websocket_bridge)
    logger.info(
        "App Startup complete: Store, Orchestrator, Audit Logger, and event bridge running."
    )

    yield

    # Shutdown
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    clear_listeners()
    logger.info("FastAPI Application Gateway shutdown complete.")


# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI SRE Copilot Application Gateway",
    description=(
        "Application gateway connecting SRE agents, MCP servers, and persistent case files. "
        "Phase 8: Security Hardened with 3-layer injection protection, tool firewall, "
        "hash-chained audit trail, and rate limiting."
    ),
    version="0.8.0",
    lifespan=lifespan,
    # Never expose Python exception details in OpenAPI responses
    docs_url="/docs" if ENV != "production" else None,
    redoc_url="/redoc" if ENV != "production" else None,
)


# ---------------------------------------------------------------------------
# Middleware (applied in REVERSE order — last added = outermost)
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding window rate limiter middleware.

    Returns HTTP 429 if the client IP exceeds RATE_LIMIT_PER_IP_RPS req/sec.
    Bypasses rate limiting for health/ready endpoints to prevent blocking
    load balancer checks in production environments.
    Fail-open: if rate limiter itself errors, request is allowed through.
    """

    _BYPASS_PATHS = frozenset(["/health", "/ready", "/api/health", "/api/ready"])

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Bypass rate limiting for health checks
        if request.url.path in self._BYPASS_PATHS:
            return await call_next(request)

        # Extract client IP (handle X-Forwarded-For for proxy deployments)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[
            0
        ].strip() or (request.client.host if request.client else "unknown")

        try:
            allowed = rate_limiter.check_ip(client_ip)
        except Exception as exc:
            logger.warning("Rate limiter error (fail-open): %s", exc)
            allowed = True

        if not allowed:
            request_id = getattr(request.state, "request_id", "unknown")
            trace_id = getattr(request.state, "trace_id", "unknown")
            # Log rate limit violation to audit trail
            try:
                audit_logger.log_rate_limit_violation(
                    request_id=request_id,
                    trace_id=trace_id,
                    key=f"ip:{client_ip}",
                    limit_type="api_requests",
                    client_ip=client_ip,
                )
            except Exception:
                pass

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded: {RATE_LIMIT_PER_IP_RPS} requests per {RATE_LIMIT_WINDOW_SECS}s.",
                    "details": {},
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECS)},
            )

        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Hard timeout on all HTTP requests (default: 30 seconds).

    Returns HTTP 504 if processing exceeds the configured timeout.
    WebSocket upgrades bypass this middleware (handled by the WS endpoint).
    Fail-open: if timeout wrapper itself errors, request continues normally.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Skip timeout for WebSocket upgrade requests
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request), timeout=REQUEST_TIMEOUT_SECS
            )
        except asyncio.TimeoutError:
            request_id = getattr(request.state, "request_id", "unknown")
            trace_id = getattr(request.state, "trace_id", "unknown")
            logger.warning(
                "Request timeout | request_id=%s | trace_id=%s | path=%s",
                request_id,
                trace_id,
                request.url.path,
            )
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error_code": "GATEWAY_TIMEOUT",
                    "message": f"Request exceeded {REQUEST_TIMEOUT_SECS}s timeout.",
                    "details": {},
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.warning("RequestTimeoutMiddleware error (fail-open): %s", exc)
            return await call_next(request)


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    """Limits the max body size of incoming HTTP requests to prevent DoS."""

    def __init__(self, app: Any, max_size_bytes: int) -> None:
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size_bytes:
            request_id = getattr(request.state, "request_id", "system")
            trace_id = getattr(request.state, "trace_id", "system")
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error_code": "PAYLOAD_TOO_LARGE",
                    "message": f"Payload too large. Limit is {self.max_size_bytes} bytes.",
                    "details": {},
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        return await call_next(request)


class TraceAndSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects request IDs, trace IDs, execution time, and security headers.

    Phase 8: Adds global X-Trace-ID for full system correlation:
        API → Agent → Tool → MCP → WebSocket → UI
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Request ID: per-request unique ID
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        # Trace ID: global flow correlation (can be passed by client to correlate UI actions)
        trace_id = request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())

        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # Extract incident_id from path for logging
        path_parts = request.url.path.strip("/").split("/")
        incident_id = "none"
        if len(path_parts) > 2 and path_parts[2] == "incidents" and len(path_parts) > 3:
            incident_id = path_parts[3]

        start_time = time.time()
        response: Response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Inject trace + security headers
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        # CSP: tight policy for API responses (no HTML rendering expected)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none';"
        )
        # HSTS (enable in production with HTTPS)
        if ENV == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        logger.info(
            "API | request_id=%s | trace_id=%s | incident=%s | %s %s | %d | %dms",
            request_id,
            trace_id,
            incident_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response


# Register middleware (applied bottom-up — last added = outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Phase 8: explicit — no wildcard
    allow_headers=[
        "Content-Type",
        "Authorization",
        REQUEST_ID_HEADER,
        TRACE_ID_HEADER,
        "X-Requested-With",
    ],
    expose_headers=[REQUEST_ID_HEADER, TRACE_ID_HEADER],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(PayloadLimitMiddleware, max_size_bytes=MAX_PAYLOAD_SIZE_BYTES)
app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(TraceAndSecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Global Standardized Exception Handlers
# ---------------------------------------------------------------------------


@app.exception_handler(IncidentNotFoundError)
async def handle_incident_not_found(
    request: Request, exc: IncidentNotFoundError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "system")
    trace_id = getattr(request.state, "trace_id", "system")
    msg = str(exc)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error_code": "INCIDENT_NOT_FOUND",
            "message": msg,
            "details": {},
            "request_id": request_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": msg,
        },
    )


@app.exception_handler(InvalidTransitionError)
async def handle_invalid_transition(
    request: Request, exc: InvalidTransitionError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "system")
    trace_id = getattr(request.state, "trace_id", "system")
    msg = str(exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "INVALID_STATUS_TRANSITION",
            "message": msg,
            "details": {},
            "request_id": request_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": msg,
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "system")
    trace_id = getattr(request.state, "trace_id", "system")
    msg = "The request body failed schema validation checks."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": msg,
            "details": {"errors": exc.errors()},
            "request_id": request_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": msg,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "system")
    trace_id = getattr(request.state, "trace_id", "system")
    code_map = {
        404: "NOT_FOUND",
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMIT_EXCEEDED",
        413: "PAYLOAD_TOO_LARGE",
    }
    err_code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": err_code,
            "message": exc.detail,
            "details": {},
            "request_id": request_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def handle_general_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — NEVER exposes stack traces or internal paths."""
    request_id = getattr(request.state, "request_id", "system")
    trace_id = getattr(request.state, "trace_id", "system")
    logger.exception(
        "Unhandled gateway crash | request_id=%s | trace_id=%s | error=%s",
        request_id,
        trace_id,
        type(exc).__name__,
    )
    # Phase 8: Sanitize error details — no exception text in production
    from backend.security.pii_redactor import sanitize_error_response

    details = {}
    if ENV != "production":
        details = {"exception_type": type(exc).__name__}
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=sanitize_error_response(
            {
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred inside the gateway.",
                "details": details,
                "request_id": request_id,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detail": "An unexpected error occurred inside the gateway.",
            }
        ),
    )


# ---------------------------------------------------------------------------
# REST Routes
# ---------------------------------------------------------------------------

app.include_router(incident_router, prefix="/api/v1/incidents")
app.include_router(incident_router, prefix="/api/incidents")

# Phase 8: Security routes (audit, simulation, status)
from backend.api.security_routes import security_router  # noqa: E402

app.include_router(security_router, prefix="/api/v1/security")


# Health/Readiness Endpoints
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
    """Verify that all upstream systems are ready."""
    store: IncidentStore = request.app.state.store
    try:
        store.list_incidents()
        return JSONResponse(content={"status": "ready", "persistence": "healthy"})
    except Exception as exc:
        logger.error("Readiness check failed | error=%s", exc)
        request_id = getattr(request.state, "request_id", "system")
        trace_id = getattr(request.state, "trace_id", "system")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error_code": "SERVICE_UNAVAILABLE",
                "message": f"Readiness check failed: {exc}",
                "details": {},
                "request_id": request_id,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "not_ready",
                "detail": f"Persistence layer failure: {exc}",
            },
        )


# ---------------------------------------------------------------------------
# WebSocket Endpoint (Phase 8 — Hardened)
# ---------------------------------------------------------------------------


@app.websocket("/ws/incidents/{incident_id}")
async def websocket_incident_stream(websocket: WebSocket, incident_id: str) -> None:
    """Real-time incident execution WebSocket channel (Phase 8 hardened).

    Security checks:
    - Incident ID format validation (INC-XXXXXXXX)
    - Max connections per channel (10)
    - Inbound message validation (size, binary, injection)
    - Outbound event sanitization (done in event bus bridge)
    """
    # Phase 8: Validate incident_id format before accepting connection
    if not validate_incident_id(incident_id):
        await websocket.close(code=4000, reason="Invalid incident_id format.")
        logger.warning("WS rejected: invalid incident_id format | id=%s", incident_id)
        return

    # Phase 8: Check connection limit per channel
    current_count = len(manager.active_connections.get(incident_id, []))
    conn_check = check_connection_limit(current_count)
    if not conn_check.valid:
        await websocket.close(code=4001, reason=conn_check.reason)
        logger.warning(
            "WS rejected: max connections | incident=%s | count=%d",
            incident_id,
            current_count,
        )
        return

    await manager.connect(websocket, incident_id)
    try:
        while True:
            # Phase 8: Validate inbound messages (pong, client control msgs)
            try:
                data = await websocket.receive_text()
            except Exception:
                # Handle binary frames — reject them
                try:
                    await websocket.receive_bytes()
                    ws_result = validate_inbound_message(b"", is_bytes=True)
                    logger.warning(
                        "WS inbound binary rejected | incident=%s", incident_id
                    )
                except Exception:
                    pass
                continue

            ws_result = validate_inbound_message(data, is_bytes=False)
            if not ws_result.valid:
                # Do NOT echo the error back — just log and drop silently
                logger.debug(
                    "WS inbound message dropped | incident=%s | code=%s",
                    incident_id,
                    ws_result.error_code,
                )
                continue

            msg = ws_result.sanitized_event or {}
            if msg.get("type") == "pong":
                logger.debug("Heartbeat pong received | incident=%s", incident_id)

    except WebSocketDisconnect:
        await manager.disconnect(websocket, incident_id)
    except Exception as exc:
        logger.debug("WebSocket exception | incident=%s | error=%s", incident_id, exc)
        await manager.disconnect(websocket, incident_id)
