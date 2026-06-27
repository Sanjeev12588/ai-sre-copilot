"""Centralised configuration for the AI SRE Copilot Gateway (Phase 5).

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
)  # 5 mins max
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

# Security and Rate Limiting
ALLOWED_CORS_ORIGINS: list[str] = [
    org.strip()
    for org in os.getenv("ALLOWED_CORS_ORIGINS", "*").split(",")
    if org.strip()
]
MAX_PAYLOAD_SIZE_BYTES: int = int(
    os.getenv("MAX_PAYLOAD_SIZE_BYTES", "10485760")
)  # Default 10MB
RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW_SECS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECS", "60"))
