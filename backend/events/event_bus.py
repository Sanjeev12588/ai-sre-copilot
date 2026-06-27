"""Lightweight in-process event bus for incident state changes (Phase 4).

Purpose
-------
Agents call ``publish_event(...)`` after every meaningful state change.
Listeners register with ``subscribe(...)``.

Today: No real listeners — the bus is a no-op at runtime.
Phase 5: FastAPI WebSocket handler subscribes to stream events to React UI.
Future: Notification services, audit systems, and Cloud Pub/Sub bridges
        can register listeners without modifying any agent code.

Design: Observer Pattern
------------------------
publish_event() is a pure side-effect function.  Agents don't need to
know about subscribers.  If a listener crashes, the error is logged and
other listeners still receive the event.

Usage
-----
  # Agent code
  from backend.events.event_bus import publish_event, IncidentEventType

  publish_event(
      IncidentEventType.STATUS_CHANGED,
      incident_id=state.incident_id,
      payload={"previous": "TRIAGED", "new": "INVESTIGATING"},
  )

  # FastAPI WebSocket handler (Phase 5)
  from backend.events.event_bus import subscribe

  async def ws_listener(event: IncidentEvent) -> None:
      await websocket.send_json(event.__dict__)

  subscribe(ws_listener)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class IncidentEventType(str, Enum):
    """Event categories emitted by the incident lifecycle system."""

    INCIDENT_CREATED = "INCIDENT_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    TIMELINE_UPDATED = "TIMELINE_UPDATED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    PERSISTENCE_SAVED = "PERSISTENCE_SAVED"
    PERSISTENCE_LOADED = "PERSISTENCE_LOADED"
    PERSISTENCE_ARCHIVED = "PERSISTENCE_ARCHIVED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_UPDATED = "SESSION_UPDATED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Event data class
# ---------------------------------------------------------------------------


@dataclass
class IncidentEvent:
    """A single lifecycle event published to the event bus."""

    event_type: IncidentEventType
    incident_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Listener registry
# ---------------------------------------------------------------------------

# Module-level list of registered listener callables.
# Phase 5 FastAPI WebSocket handler will append itself here.
_listeners: list[Callable[[IncidentEvent], None]] = []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def subscribe(listener: Callable[[IncidentEvent], None]) -> None:
    """Register *listener* to receive all future ``IncidentEvent`` objects.

    Phase 5 FastAPI integration::

        from backend.events.event_bus import subscribe

        @app.on_event("startup")
        async def _register_ws_listener() -> None:
            subscribe(websocket_broadcast_handler)
    """
    _listeners.append(listener)
    logger.debug(
        "EventBus: listener registered | total_listeners=%d",
        len(_listeners),
    )


def unsubscribe(listener: Callable[[IncidentEvent], None]) -> None:
    """Remove *listener* from the registry.  Silent if not registered."""
    if listener in _listeners:
        _listeners.remove(listener)
        logger.debug(
            "EventBus: listener removed | total_listeners=%d",
            len(_listeners),
        )


def publish_event(
    event_type: IncidentEventType,
    incident_id: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Publish an ``IncidentEvent`` to all registered listeners.

    Non-blocking and synchronous.  Listener exceptions are caught and
    logged so that one bad listener cannot break the pipeline.

    Parameters
    ----------
    event_type:
        The ``IncidentEventType`` enum value.
    incident_id:
        The incident ID this event relates to.
    payload:
        Optional dict with event-specific data (e.g. previous/new status).
    """
    event = IncidentEvent(
        event_type=event_type,
        incident_id=incident_id,
        payload=payload or {},
    )
    logger.debug(
        "EventBus: publish | type=%s | incident=%s | listeners=%d",
        event_type.value,
        incident_id,
        len(_listeners),
    )
    for listener in list(_listeners):  # copy to avoid mutation during iteration
        try:
            listener(event)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "EventBus: listener error | type=%s | incident=%s | error=%s",
                event_type.value,
                incident_id,
                exc,
            )


def clear_listeners() -> None:
    """Remove all registered listeners.

    Primarily used in tests to prevent listener bleed between test cases.
    """
    _listeners.clear()
    logger.debug("EventBus: all listeners cleared")


def listener_count() -> int:
    """Return the current number of registered listeners (for testing)."""
    return len(_listeners)
