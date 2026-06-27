"""Session Memory — Abstract interface + in-memory implementation (Phase 4).

Design: Dependency Inversion
-----------------------------
Agents depend on the abstract ``MemoryStore`` interface, not a concrete
implementation.  Swapping ``InMemoryStore`` for a Redis or Firestore backend
later is a single-line change in the DI wiring, not an agent rewrite.

Classes
-------
MemoryStore     — Abstract base class (the interface agents reference).
SessionContext  — Per-session metadata: agent outputs, tool calls, decisions.
InMemoryStore   — Thread-safe dict-backed implementation for development.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from backend.memory.case_file import IncidentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class MemoryStore(ABC):
    """Abstract session memory interface.

    All public methods operate on *session_id* strings, which map 1-to-1
    with ADK sessions (and therefore with active incidents).
    """

    @abstractmethod
    def create_session(self, session_id: str, state: IncidentState) -> None:
        """Create a new session with an initial incident state."""
        ...

    @abstractmethod
    def get(self, session_id: str) -> IncidentState | None:
        """Return the current ``IncidentState`` for *session_id*, or ``None``."""
        ...

    @abstractmethod
    def update(self, session_id: str, state: IncidentState) -> None:
        """Replace the state stored for *session_id*."""
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Remove *session_id* and its associated state."""
        ...

    @abstractmethod
    def list_sessions(self) -> list[str]:
        """Return all active session IDs."""
        ...

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Return ``True`` if *session_id* currently exists in the store."""
        ...


# ---------------------------------------------------------------------------
# Per-session context (conversation history, tool calls, decisions)
# ---------------------------------------------------------------------------


class SessionContext:
    """Stores rich per-session metadata alongside the ``IncidentState``.

    Maintained internally by ``InMemoryStore``; exposed via
    ``InMemoryStore.get_context()``.
    """

    def __init__(self, session_id: str, state: IncidentState) -> None:
        self.session_id = session_id
        self.state = state
        now = datetime.now(timezone.utc).isoformat()
        self.created_at: str = now
        self.updated_at: str = now

        # Agent output history: {agent_name: output_value}
        self.agent_outputs: dict[str, Any] = {}

        # Ordered list of every MCP tool call made during this session
        self.tool_call_history: list[dict[str, Any]] = []

        # Human-readable log of key agent decisions
        self.decision_log: list[str] = []

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def record_agent_output(self, agent_name: str, output: Any) -> None:
        """Store the output produced by *agent_name* and refresh timestamp."""
        self.agent_outputs[agent_name] = output
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_tool_call(
        self,
        agent: str,
        tool: str,
        args: dict[str, Any],
        result: Any,
    ) -> None:
        """Append a tool-call record to the session history."""
        self.tool_call_history.append(
            {
                "agent": agent,
                "tool": tool,
                "args": args,
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def record_decision(self, decision: str) -> None:
        """Append a timestamped decision string to the decision log."""
        ts = datetime.now(timezone.utc).isoformat()
        self.decision_log.append(f"[{ts}] {decision}")

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary dict (useful for debugging)."""
        return {
            "session_id": self.session_id,
            "incident_id": self.state.incident_id,
            "status": self.state.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "agents_run": list(self.agent_outputs.keys()),
            "tool_calls": len(self.tool_call_history),
            "decisions": len(self.decision_log),
        }


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------


class InMemoryStore(MemoryStore):
    """Thread-safe in-memory session store.

    Suitable for:
    - Local development and ADK ``adk web`` sessions.
    - Unit and integration testing (each test gets a fresh instance).
    - Single-process deployments where persistence restarts are acceptable.

    Replace with a ``RedisStore`` or ``FirestoreStore`` for multi-process
    or Cloud Run deployments — the ``MemoryStore`` interface stays the same.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # MemoryStore interface
    # ------------------------------------------------------------------

    def create_session(self, session_id: str, state: IncidentState) -> None:
        """Create a new session.  Raises ``KeyError`` if it already exists."""
        with self._lock:
            if session_id in self._sessions:
                raise KeyError(
                    f"Session {session_id!r} already exists. "
                    "Use update() to modify an existing session."
                )
            ctx = SessionContext(session_id=session_id, state=state)
            self._sessions[session_id] = ctx
        logger.info(
            "Session created | session_id=%s | incident=%s",
            session_id,
            state.incident_id,
        )

    def get(self, session_id: str) -> IncidentState | None:
        """Return the ``IncidentState`` for *session_id*, or ``None``."""
        with self._lock:
            ctx = self._sessions.get(session_id)
            return ctx.state if ctx else None

    def get_context(self, session_id: str) -> SessionContext | None:
        """Return the full ``SessionContext`` (includes history), or ``None``."""
        with self._lock:
            return self._sessions.get(session_id)

    def update(self, session_id: str, state: IncidentState) -> None:
        """Replace state.  Raises ``KeyError`` if session does not exist."""
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(f"Session {session_id!r} not found.")
            self._sessions[session_id].state = state
            self._sessions[session_id].updated_at = datetime.now(
                timezone.utc
            ).isoformat()
        logger.debug(
            "Session updated | session_id=%s | status=%s",
            session_id,
            state.status,
        )

    def delete(self, session_id: str) -> None:
        """Remove a session.  Silent no-op if it does not exist."""
        with self._lock:
            self._sessions.pop(session_id, None)
        logger.info("Session deleted | session_id=%s", session_id)

    def list_sessions(self) -> list[str]:
        """Return all active session IDs (snapshot under lock)."""
        with self._lock:
            return list(self._sessions.keys())

    def exists(self, session_id: str) -> bool:
        """Return ``True`` if *session_id* is currently stored."""
        with self._lock:
            return session_id in self._sessions

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def record_agent_output(
        self, session_id: str, agent_name: str, output: Any
    ) -> None:
        """Convenience wrapper: record an agent output in the session context."""
        with self._lock:
            ctx = self._sessions.get(session_id)
            if ctx:
                ctx.record_agent_output(agent_name, output)

    def record_tool_call(
        self,
        session_id: str,
        agent: str,
        tool: str,
        args: dict[str, Any],
        result: Any,
    ) -> None:
        """Convenience wrapper: record a tool call in the session context."""
        with self._lock:
            ctx = self._sessions.get(session_id)
            if ctx:
                ctx.record_tool_call(agent=agent, tool=tool, args=args, result=result)

    def session_count(self) -> int:
        """Return the number of currently active sessions."""
        with self._lock:
            return len(self._sessions)
