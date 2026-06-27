"""WebSocket Security Layer — Phase 8 Security Hardening.

Secures real-time event streaming with:

  - Strict outbound event schema validation (all required fields present)
  - Inbound message size limit (16KB max) to prevent memory exhaustion
  - Binary payload rejection (all WS messages must be valid UTF-8 JSON)
  - Unknown event type handling (drop silently — never echo errors back)
  - Rate limiting via RateLimiter per incident channel
  - PII/sensitive data scrubbing on outbound events before broadcast
  - Max connections per incident channel enforcement

Event Contract Schema (all outbound events must conform):
    {
        "event_id": "<uuid>",
        "timestamp": "<ISO-8601>",
        "incident_id": "<string>",
        "event_type": "<dot.notation>",
        "source": "<agent_name|system>",
        "severity": "info|warning|critical",
        "payload": {}
    }
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum inbound WebSocket message size (16KB)
WS_MAX_MESSAGE_BYTES = 16 * 1024

# Maximum concurrent connections per incident channel
WS_MAX_CONNECTIONS_PER_CHANNEL = 10

# Valid event type patterns (dot-notation: word.word or word.word.word)
_EVENT_TYPE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*){1,2}$")

# Known severity levels
_VALID_SEVERITIES = frozenset(["info", "warning", "critical", "debug"])

# Required fields in every outbound WebSocket event
_REQUIRED_EVENT_FIELDS = frozenset(
    [
        "event_id",
        "timestamp",
        "incident_id",
        "event_type",
    ]
)

# Fields that MUST NOT appear in outbound events (internal-only)
_FORBIDDEN_OUTBOUND_FIELDS = frozenset(
    [
        "system_prompt",
        "internal_reasoning",
        "_raw_tool_output",
        "_agent_instructions",
        "gemini_api_key",
        "api_key",
        "secret",
    ]
)

# Known valid outbound event types
_KNOWN_EVENT_TYPES = frozenset(
    [
        "incident.created",
        "incident.updated",
        "incident.error",
        "incident.resolved",
        "agent.started",
        "agent.completed",
        "agent.failed",
        "root_cause.detected",
        "report.generated",
        "evaluation.completed",
        "tool.executed",
        "tool.blocked",
        "security.rejection",
        "system.ping",
        "system.heartbeat",
    ]
)


# ---------------------------------------------------------------------------
# Result Types
# ---------------------------------------------------------------------------


@dataclass
class WSValidationResult:
    """Result of WebSocket event/message validation."""

    valid: bool
    reason: str = ""
    error_code: str = ""
    sanitized_event: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Inbound Message Validation
# ---------------------------------------------------------------------------


def validate_inbound_message(
    raw_data: Any, is_bytes: bool = False
) -> WSValidationResult:
    """Validate an inbound WebSocket message from a client.

    Rules:
    - Binary payloads are rejected (must be text JSON)
    - Message size must be ≤ 16KB
    - Must be valid JSON
    - If JSON, run injection check on string values
    - Unknown fields are silently dropped

    Args:
        raw_data: The raw message data (str or bytes).
        is_bytes: True if the message was received as binary.

    Returns:
        WSValidationResult.
    """
    # Rule 1: Reject binary payloads
    if is_bytes:
        logger.warning("WS inbound: Binary payload rejected (must be text/JSON).")
        return WSValidationResult(
            valid=False,
            reason="Binary WebSocket payloads are not accepted.",
            error_code="WS_BINARY_REJECTED",
        )

    # Rule 2: Size limit (before parsing)
    if (
        isinstance(raw_data, str)
        and len(raw_data.encode("utf-8")) > WS_MAX_MESSAGE_BYTES
    ):
        logger.warning(
            "WS inbound: Message too large (%d bytes > %d limit).",
            len(raw_data.encode("utf-8")),
            WS_MAX_MESSAGE_BYTES,
        )
        return WSValidationResult(
            valid=False,
            reason=f"WebSocket message exceeds {WS_MAX_MESSAGE_BYTES // 1024}KB limit.",
            error_code="WS_MESSAGE_TOO_LARGE",
        )

    # Rule 3: Must be valid JSON
    import json

    try:
        if isinstance(raw_data, str):
            parsed = json.loads(raw_data)
        else:
            parsed = json.loads(raw_data.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.debug("WS inbound: Invalid JSON — silently dropped.")
        return WSValidationResult(
            valid=False,
            reason="Invalid JSON.",
            error_code="WS_INVALID_JSON",
        )

    # Rule 4: Check for injection in inbound message values (pong payloads etc.)
    from backend.security.input_validator import detect_injection_sync

    for key, value in parsed.items() if isinstance(parsed, dict) else []:
        if isinstance(value, str):
            result = detect_injection_sync(value)
            if result.blocked:
                logger.warning(
                    "WS inbound injection detected | key=%s | patterns=%s",
                    key,
                    result.detected_patterns,
                )
                return WSValidationResult(
                    valid=False,
                    reason="Injection detected in inbound message.",
                    error_code="WS_INJECTION_BLOCKED",
                )

    return WSValidationResult(
        valid=True, sanitized_event=parsed if isinstance(parsed, dict) else {}
    )


# ---------------------------------------------------------------------------
# Outbound Event Validation & Sanitization
# ---------------------------------------------------------------------------


def validate_outbound_event(event: dict[str, Any]) -> WSValidationResult:
    """Validate an outbound WebSocket event before broadcasting.

    Enforces the event schema contract and silently drops unknown event types.

    Args:
        event: Event dict to validate.

    Returns:
        WSValidationResult with sanitized_event if valid.
    """
    # Check required fields
    missing = _REQUIRED_EVENT_FIELDS - set(event.keys())
    if missing:
        logger.debug(
            "WS outbound event missing required fields: %s — dropped silently.", missing
        )
        return WSValidationResult(
            valid=False,
            reason=f"Missing required fields: {missing}",
            error_code="WS_SCHEMA_VIOLATION",
        )

    # Validate event_type format (dot notation)
    event_type = event.get("event_type", "")
    if not _EVENT_TYPE_PATTERN.match(event_type):
        # Drop unknown event types silently (do NOT echo error back to client)
        logger.debug(
            "WS outbound: unknown event_type '%s' — dropped silently.", event_type
        )
        return WSValidationResult(
            valid=False,
            reason="Unknown event type.",
            error_code="WS_UNKNOWN_EVENT_TYPE",
        )

    # Sanitize and return cleaned event
    sanitized = sanitize_outbound_event(event)
    return WSValidationResult(valid=True, sanitized_event=sanitized)


def sanitize_outbound_event(event: dict[str, Any]) -> dict[str, Any]:
    """Strip forbidden/sensitive fields from an outbound event payload.

    Also ensures all required fields are present with safe defaults,
    and adds a severity field if missing.

    Args:
        event: Raw event dict.

    Returns:
        Sanitized event safe for frontend broadcast.
    """
    from backend.security.pii_redactor import redact_sensitive_data

    # Build clean base event with required fields
    safe_event: dict[str, Any] = {
        "event_id": event.get("event_id") or str(uuid.uuid4()),
        "timestamp": event.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "incident_id": str(event.get("incident_id", "UNKNOWN")),
        "event_type": event.get("event_type", "incident.updated"),
        "source": event.get("agent") or event.get("source") or "system",
        "severity": _normalize_severity(
            event.get("severity") or event.get("status", "info")
        ),
        "request_id": event.get("request_id", "system"),
    }

    # Include payload, removing forbidden keys
    raw_payload = event.get("payload", {})
    if isinstance(raw_payload, dict):
        clean_payload = {
            k: v for k, v in raw_payload.items() if k not in _FORBIDDEN_OUTBOUND_FIELDS
        }
        # Apply PII redaction to string values in payload
        for key, value in clean_payload.items():
            if isinstance(value, str):
                clean_payload[key] = redact_sensitive_data(value)
        safe_event["payload"] = clean_payload
    else:
        safe_event["payload"] = {}

    return safe_event


def _normalize_severity(value: str) -> str:
    """Normalize a severity/status value to one of: info, warning, critical."""
    v = str(value).lower()
    if v in ("critical", "error", "p0", "p1", "failed", "failure"):
        return "critical"
    if v in ("warning", "warn", "p2", "p3", "degraded", "investigating"):
        return "warning"
    return "info"


# ---------------------------------------------------------------------------
# Connection Limit Check
# ---------------------------------------------------------------------------


def check_connection_limit(current_count: int) -> WSValidationResult:
    """Check if a new WebSocket connection can be accepted.

    Args:
        current_count: Current number of active connections for the incident channel.

    Returns:
        WSValidationResult.
    """
    if current_count >= WS_MAX_CONNECTIONS_PER_CHANNEL:
        logger.warning(
            "WS connection rejected: channel at max capacity (%d/%d).",
            current_count,
            WS_MAX_CONNECTIONS_PER_CHANNEL,
        )
        return WSValidationResult(
            valid=False,
            reason=f"Channel at maximum capacity ({WS_MAX_CONNECTIONS_PER_CHANNEL} connections).",
            error_code="WS_MAX_CONNECTIONS_EXCEEDED",
        )
    return WSValidationResult(valid=True)


def check_ws_rate_limit(incident_id: str) -> bool:
    """Check WebSocket event rate limit for an incident channel.

    Fail-open: returns True if rate limiter is unavailable.

    Args:
        incident_id: The incident channel ID.

    Returns:
        True if within rate limit, False if exceeded.
    """
    try:
        from backend.security.rate_limiter import rate_limiter

        return rate_limiter.check_websocket_events(incident_id)
    except Exception as exc:
        logger.warning("WS rate limiter error (fail-open): %s", exc)
        return True


# ---------------------------------------------------------------------------
# Incident ID Format Validation
# ---------------------------------------------------------------------------

_INCIDENT_ID_PATTERN = re.compile(r"^INC-[A-F0-9]{8}$")


def validate_incident_id(incident_id: str) -> bool:
    """Validate incident ID format (INC-XXXXXXXX where X is uppercase hex).

    Args:
        incident_id: The incident ID string from the URL path.

    Returns:
        True if valid format, False otherwise.
    """
    return bool(_INCIDENT_ID_PATTERN.match(incident_id))
