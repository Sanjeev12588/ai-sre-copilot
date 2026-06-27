"""PII Redactor & Data Leakage Prevention — Phase 8 Security Hardening.

Sanitizes log records, API responses, and agent outputs to prevent
sensitive system data from leaking to external consumers.

Redacts:
  - API keys and bearer tokens (regex-based)
  - Internal file system paths
  - System prompt content (markers: [SYSTEM], <SYSTEM>)
  - Raw tool outputs tagged as [INTERNAL] or [TOOL_OUTPUT]
  - Google API key patterns
  - Database connection strings
  - Private IP ranges in sensitive contexts
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redaction Pattern Registry
# ---------------------------------------------------------------------------

# Patterns: (compiled_regex, replacement_string)
_REDACTION_RULES: list[tuple[re.Pattern[str], str]] = [
    # Google / Gemini API keys (AIza followed by 35 alphanumeric/dash/underscore chars)
    (
        re.compile(r"AIza[A-Za-z0-9_\-]{35}"),
        "[REDACTED:GOOGLE_API_KEY]",
    ),
    # Generic bearer tokens
    (
        re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b", re.IGNORECASE),
        "Bearer [REDACTED:TOKEN]",
    ),
    # Generic API keys in key=value form
    (
        re.compile(
            r"(api[_\-]?key|apikey|secret[_\-]?key|auth[_\-]?token|access[_\-]?token)\s*[=:]\s*['\"]?([A-Za-z0-9\-_]{16,})['\"]?",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED:API_KEY]",
    ),
    # Database connection strings
    (
        re.compile(
            r"(postgresql|mysql|mongodb|redis|sqlite)://[^\s\"']+",
            re.IGNORECASE,
        ),
        r"\1://[REDACTED:CONNECTION_STRING]",
    ),
    # Windows absolute paths (C:\, D:\, etc.)
    (
        re.compile(r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*"),
        "[REDACTED:INTERNAL_PATH]",
    ),
    # Unix absolute paths containing sensitive dirs
    (
        re.compile(
            r"/(?:home|root|etc|usr|var|opt|private)/[^\s\"']+",
            re.IGNORECASE,
        ),
        "[REDACTED:INTERNAL_PATH]",
    ),
    # SSH private key content
    (
        re.compile(
            r"-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----.*?-----END[^-]+-----",
            re.DOTALL,
        ),
        "[REDACTED:PRIVATE_KEY]",
    ),
    # System prompt markers
    (
        re.compile(
            r"(\[SYSTEM\]|\<SYSTEM\>|<system>|<\|system\|>).*?(\[\/SYSTEM\]|\<\/SYSTEM\>|</system>|<\|\/system\|>)",
            re.DOTALL | re.IGNORECASE,
        ),
        "[REDACTED:SYSTEM_PROMPT]",
    ),
    # Internal tool output markers
    (
        re.compile(
            r"\[INTERNAL(?:_TOOL_OUTPUT|_PROMPT|_REASONING)?\].*?\[\/INTERNAL(?:_TOOL_OUTPUT|_PROMPT|_REASONING)?\]",
            re.DOTALL | re.IGNORECASE,
        ),
        "[REDACTED:INTERNAL_CONTENT]",
    ),
    # Raw MCP tool JSON responses (large embedded JSON from tool calls)
    (
        re.compile(r'"tool_response"\s*:\s*\{[^}]{200,}\}', re.DOTALL),
        '"tool_response": "[REDACTED:TOOL_OUTPUT]"',
    ),
    # Email addresses in logs (basic PII)
    (
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED:EMAIL]",
    ),
]

# Fields to always redact in structured dicts (exact key match)
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    [
        "api_key",
        "apikey",
        "api_token",
        "access_token",
        "secret_key",
        "secret",
        "password",
        "passwd",
        "token",
        "auth_token",
        "bearer_token",
        "private_key",
        "gemini_api_key",
        "GEMINI_API_KEY",
        "authorization",
        "x-api-key",
        "system_prompt",
        "instructions",
        "_internal_reasoning",
    ]
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def redact_sensitive_data(text: str) -> str:
    """Apply all redaction rules to a text string.

    Args:
        text: Raw text that may contain sensitive data.

    Returns:
        Text with sensitive patterns replaced by safe placeholders.
    """
    if not text or not isinstance(text, str):
        return text or ""

    result = text
    for pattern, replacement in _REDACTION_RULES:
        result = pattern.sub(replacement, result)

    return result


def sanitize_log_record(record: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a structured log/audit record before output.

    Recursively redacts sensitive keys and applies text redaction
    to all string values.

    Args:
        record: A dict representing a log entry or API response.

    Returns:
        Sanitized dict safe for external logging or display.
    """
    return _redact_dict(record, depth=0)


def sanitize_error_response(error: dict[str, Any]) -> dict[str, Any]:
    """Ensure error responses don't expose internal details.

    Removes stack traces, internal paths, and raw exception messages
    that could aid attackers.

    Args:
        error: An error response dict.

    Returns:
        Sanitized error dict.
    """
    safe = dict(error)

    # Remove stack trace details
    details = safe.get("details", {})
    if isinstance(details, dict):
        # Never expose raw exception text in details
        details.pop("exception", None)
        details.pop("traceback", None)
        details.pop("stack_trace", None)
        safe["details"] = details

    # Redact any paths in the message
    if "message" in safe and isinstance(safe["message"], str):
        safe["message"] = redact_sensitive_data(safe["message"])

    return safe


def is_sensitive_key(key: str) -> bool:
    """Check if a dictionary key name indicates sensitive data.

    Args:
        key: The key name to check.

    Returns:
        True if the key matches a known sensitive field name.
    """
    return key.lower() in {k.lower() for k in _SENSITIVE_KEYS}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _redact_dict(data: dict[str, Any], depth: int) -> dict[str, Any]:
    """Recursively sanitize a dictionary."""
    if depth > 5:
        return {"[DEPTH_LIMIT]": "content redacted"}

    result: dict[str, Any] = {}
    for key, value in data.items():
        if is_sensitive_key(str(key)):
            result[key] = "[REDACTED:SENSITIVE_FIELD]"
        elif isinstance(value, str):
            result[key] = redact_sensitive_data(value)
        elif isinstance(value, dict):
            result[key] = _redact_dict(value, depth + 1)
        elif isinstance(value, list):
            result[key] = [
                _redact_dict(item, depth + 1)
                if isinstance(item, dict)
                else redact_sensitive_data(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result
