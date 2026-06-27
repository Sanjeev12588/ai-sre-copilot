"""Security guardrails package — Phase 8.

Exports all public security APIs for use across the backend.
All components are designed with fail-open defaults so that
a security component failure never crashes the demo pipeline.
"""

from backend.security.audit_logger import audit_logger
from backend.security.input_validator import (
    InjectionDetectionResult,
    PayloadValidationResult,
    detect_injection,
    detect_injection_sync,
    sanitize_text,
    validate_incident_payload,
    validate_incident_payload_sync,
    validate_tool_arguments,
)
from backend.security.pii_redactor import (
    is_sensitive_key,
    redact_sensitive_data,
    sanitize_error_response,
    sanitize_log_record,
)
from backend.security.rate_limiter import rate_limiter
from backend.security.tool_firewall import (
    ALLOWED_TOOLS,
    FirewallResult,
    ToolFirewallError,
    tool_firewall,
)
from backend.security.ws_security import (
    check_connection_limit,
    check_ws_rate_limit,
    sanitize_outbound_event,
    validate_inbound_message,
    validate_incident_id,
    validate_outbound_event,
)

__all__ = [
    # Input validation
    "detect_injection",
    "detect_injection_sync",
    "validate_incident_payload",
    "validate_incident_payload_sync",
    "validate_tool_arguments",
    "sanitize_text",
    "InjectionDetectionResult",
    "PayloadValidationResult",
    # PII redaction
    "redact_sensitive_data",
    "sanitize_log_record",
    "sanitize_error_response",
    "is_sensitive_key",
    # Rate limiter
    "rate_limiter",
    # Tool firewall
    "tool_firewall",
    "ALLOWED_TOOLS",
    "FirewallResult",
    "ToolFirewallError",
    # WebSocket security
    "validate_inbound_message",
    "validate_outbound_event",
    "sanitize_outbound_event",
    "check_connection_limit",
    "check_ws_rate_limit",
    "validate_incident_id",
    # Audit logger
    "audit_logger",
]
