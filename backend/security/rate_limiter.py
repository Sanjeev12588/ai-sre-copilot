"""In-Memory Token Bucket Rate Limiter — Phase 8 Security Hardening.

Provides per-key sliding window rate limiting for single-process deployments.

Rate limits are BEST-EFFORT per process instance:
  - State resets on process restart (documented demo limitation)
  - A process-start guard logs a warning noting that limits reset on restart
  - In multi-process production: replace with Redis-backed sliding window

Process-restart safety:
  - On startup, the limiter logs the process start time as a watermark
  - All violation statistics are preserved per session
  - The reset is considered acceptable for demo/Kaggle environments where
    the server process remains stable during a judging session

Keys used in this system:
  - "ip:<client_ip>"         → API requests per IP (10/sec default)
  - "ws:<incident_id>"       → WebSocket events per incident (100/sec)
  - "tool:<agent_name>"      → MCP tool calls per agent (20/min)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# Warn on process start so operators know limits are in-memory
_PROCESS_START_TIME = datetime.now(timezone.utc).isoformat()
logger.warning(
    "RateLimiter initialized | process_start=%s | NOTE: rate limit state resets on "
    "process restart. For multi-process deployments, use a Redis-backed limiter.",
    _PROCESS_START_TIME,
)


class RateLimiter:
    """Thread-safe sliding window rate limiter backed by in-memory deques.

    Design:
    - Each key has a deque of request timestamps within the sliding window
    - Expired timestamps are pruned on every check (O(N) worst case but bounded)
    - Thread-safe via a single per-instance lock

    Demo limitation:
    - State is per-process and resets on restart
    - Acceptable for Kaggle/demo single-server deployments
    """

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._violations: dict[str, int] = defaultdict(int)
        self._process_start = _PROCESS_START_TIME

    def check(self, key: str, limit: int, window_secs: int) -> bool:
        """Check if a request is within the rate limit.

        Fail-open: if an internal error occurs, allows the request and logs a warning.

        Args:
            key: Unique rate limit key (e.g. "ip:1.2.3.4").
            limit: Maximum requests allowed in window.
            window_secs: Rolling time window in seconds.

        Returns:
            True if allowed, False if rate limit exceeded.
        """
        try:
            now = time.monotonic()
            window_start = now - window_secs

            with self._lock:
                window = self._windows[key]

                # Prune expired timestamps
                while window and window[0] < window_start:
                    window.popleft()

                if len(window) >= limit:
                    self._violations[key] += 1
                    logger.warning(
                        "Rate limit exceeded | key=%s | limit=%d/%ds | "
                        "total_violations=%d | process_start=%s",
                        key,
                        limit,
                        window_secs,
                        self._violations[key],
                        self._process_start,
                    )
                    return False

                window.append(now)
                return True

        except Exception as exc:
            # Fail-open: never let the rate limiter crash the request pipeline
            logger.warning(
                "RateLimiter internal error (fail-open): key=%s error=%s", key, exc
            )
            return True

    def check_ip(self, ip: str) -> bool:
        """Check API rate limit for an IP (default: 10 req/sec)."""
        try:
            from backend.config import RATE_LIMIT_PER_IP_RPS, RATE_LIMIT_WINDOW_SECS
        except ImportError:
            return True  # Fail-open if config not available
        return self.check(
            f"ip:{ip}", limit=RATE_LIMIT_PER_IP_RPS, window_secs=RATE_LIMIT_WINDOW_SECS
        )

    def check_websocket_events(self, incident_id: str) -> bool:
        """Check WebSocket event rate for an incident (default: 100 events/sec)."""
        try:
            from backend.config import WS_RATE_LIMIT_PER_INCIDENT
        except ImportError:
            return True
        return self.check(
            f"ws:{incident_id}", limit=WS_RATE_LIMIT_PER_INCIDENT, window_secs=1
        )

    def check_tool_calls(self, agent_name: str) -> bool:
        """Check MCP tool call rate for an agent (default: 20 calls/min)."""
        try:
            from backend.config import TOOL_CALL_LIMIT_PER_AGENT_MIN
        except ImportError:
            return True
        return self.check(
            f"tool:{agent_name}", limit=TOOL_CALL_LIMIT_PER_AGENT_MIN, window_secs=60
        )

    def get_stats(self) -> dict[str, Any]:
        """Return current rate limiter statistics."""
        with self._lock:
            return {
                "process_start": self._process_start,
                "total_tracked_keys": len(self._windows),
                "total_violations": sum(self._violations.values()),
                "violations_by_key": dict(self._violations),
                "note": (
                    "Rate limit state is per-process. Resets on server restart. "
                    "For multi-process deployments, use a Redis-backed limiter."
                ),
            }

    def reset(self, key: str | None = None) -> None:
        """Reset rate limit state (used in tests)."""
        with self._lock:
            if key:
                self._windows.pop(key, None)
                self._violations.pop(key, None)
            else:
                self._windows.clear()
                self._violations.clear()


# Global singleton
rate_limiter = RateLimiter()
