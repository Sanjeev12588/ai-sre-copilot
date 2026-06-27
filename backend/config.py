"""Centralised configuration for the AI SRE Copilot Gateway (Phase 8).

Reads environment variables with sensible defaults for local development
and SRE production-grade deployments.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Base project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "incidents"

# Server configuration
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
ENV: str = os.getenv("ENV", "development")
DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# Persistence settings
PERSISTENCE_DIR: Path = Path(os.getenv("PERSISTENCE_DIR", str(DEFAULT_DATA_DIR)))

# Logging settings
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# WebSocket settings
WS_HEARTBEAT_INTERVAL: float = float(os.getenv("WS_HEARTBEAT_INTERVAL", "10.0"))
WS_TIMEOUT: float = float(os.getenv("WS_TIMEOUT", "30.0"))

# ADK & Workflow settings
ADK_WORKFLOW_TIMEOUT: float = float(
    os.getenv("ADK_WORKFLOW_TIMEOUT", "300.0")
)  # 5 mins
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------------------------
# Phase 8: Security & Rate Limiting Configuration
# ---------------------------------------------------------------------------

# CORS — in production, restrict to your exact frontend origin
ALLOWED_CORS_ORIGINS: list[str] = [
    org.strip()
    for org in os.getenv(
        "ALLOWED_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")
    if org.strip()
]

# Request payload size limit (default 1MB — reduced from 10MB for security)
MAX_PAYLOAD_SIZE_BYTES: int = int(
    os.getenv("MAX_PAYLOAD_SIZE_BYTES", str(1 * 1024 * 1024))
)

# API rate limiting (per IP, sliding window)
RATE_LIMIT_PER_IP_RPS: int = int(os.getenv("RATE_LIMIT_PER_IP_RPS", "10"))
RATE_LIMIT_REQUESTS: int = RATE_LIMIT_PER_IP_RPS  # backward compat alias
RATE_LIMIT_WINDOW_SECS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECS", "1"))

# WebSocket event rate limit (per incident channel, events/sec)
WS_RATE_LIMIT_PER_INCIDENT: int = int(os.getenv("WS_RATE_LIMIT_PER_INCIDENT", "100"))

# MCP tool call rate limit (per agent, calls/min)
TOOL_CALL_LIMIT_PER_AGENT_MIN: int = int(
    os.getenv("TOOL_CALL_LIMIT_PER_AGENT_MIN", "20")
)

# Maximum concurrent WebSocket connections per incident channel
MAX_WS_CONNECTIONS_PER_INCIDENT: int = int(
    os.getenv("MAX_WS_CONNECTIONS_PER_INCIDENT", "10")
)

# Request timeout (all non-WS endpoints, seconds)
REQUEST_TIMEOUT_SECS: float = float(os.getenv("REQUEST_TIMEOUT_SECS", "30.0"))

# Audit log directory (hash-chained JSONL audit trail)
AUDIT_LOG_DIR: Path = Path(
    os.getenv("AUDIT_LOG_DIR", str(PROJECT_ROOT / "data" / "audit"))
)

# Prompt injection LLM classifier (Layer 3) — enable only if GEMINI_API_KEY is set
PROMPT_INJECTION_LLM_CLASSIFIER_ENABLED: bool = os.getenv(
    "PROMPT_INJECTION_LLM_CLASSIFIER_ENABLED", "true"
).lower() in ("true", "1", "yes") and bool(GEMINI_API_KEY)

# Threat simulation mode — ONLY available in non-production environments
# Requires a hardcoded dev token (see security_routes.py)
ENABLE_THREAT_SIMULATION: bool = ENV != "production" and os.getenv(
    "ENABLE_THREAT_SIMULATION", "true"
).lower() in ("true", "1", "yes")

# Threat simulation admin token (must be set in .env for simulation access)
THREAT_SIMULATION_TOKEN: str = os.getenv(
    "THREAT_SIMULATION_TOKEN", "dev-simulation-token-changeme"
)

# Global trace ID header name
TRACE_ID_HEADER: str = "X-Trace-ID"
REQUEST_ID_HEADER: str = "X-Request-ID"
