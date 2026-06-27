"""WebSocket Connection Manager and handlers (Phase 5).

Handles real-time WebSocket communication, heartbeats, reconnection,
incident-specific channels, and event bus streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for incident channels.

    Supports:
    - Multiple clients per incident
    - Heartbeat/ping checking
    - Broadast to specific channels
    - Graceful cleanup
    """

    def __init__(self) -> None:
        # Maps incident_id -> list of active WebSockets
        self.active_connections: dict[str, list[WebSocket]] = {}
        # Mutex lock for thread-safe websocket state changes
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, incident_id: str) -> None:
        """Register a new WebSocket client on the incident channel."""
        await websocket.accept()
        async with self._lock:
            if incident_id not in self.active_connections:
                self.active_connections[incident_id] = []
            self.active_connections[incident_id].append(websocket)
        logger.info(
            "WebSocket connected | incident=%s | clients=%d",
            incident_id,
            len(self.active_connections[incident_id]),
        )

    async def disconnect(self, websocket: WebSocket, incident_id: str) -> None:
        """Unregister a client and clean up channel keys if empty."""
        async with self._lock:
            if incident_id in self.active_connections:
                if websocket in self.active_connections[incident_id]:
                    self.active_connections[incident_id].remove(websocket)
                if not self.active_connections[incident_id]:
                    del self.active_connections[incident_id]
        logger.info("WebSocket disconnected | incident=%s", incident_id)

    async def broadcast_to_channel(
        self, incident_id: str, message: dict[str, Any]
    ) -> None:
        """Broadcast JSON payload to all active clients on a specific incident channel."""
        async with self._lock:
            connections = list(self.active_connections.get(incident_id, []))

        if not connections:
            return

        payload = json.dumps(message, default=str)
        tasks = []
        for ws in connections:
            tasks.append(self._safe_send(ws, incident_id, payload))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(
        self, websocket: WebSocket, incident_id: str, payload: str
    ) -> None:
        """Send message safely, handling disconnections gracefully."""
        try:
            await websocket.send_text(payload)
        except Exception as exc:
            logger.debug(
                "WebSocket send error on channel %s | error=%s",
                incident_id,
                exc,
            )
            # Cleanup will be handled by the endpoint's disconnect block
            await self.disconnect(websocket, incident_id)

    async def start_heartbeat_loop(self, interval: float = 10.0) -> None:
        """Periodically ping clients to maintain connection and prune dead ones."""
        while True:
            await asyncio.sleep(interval)
            async with self._lock:
                channels = list(self.active_connections.keys())

            for channel in channels:
                async with self._lock:
                    connections = list(self.active_connections.get(channel, []))

                for ws in connections:
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        await self.disconnect(ws, channel)


# Global instance of WebSocket connection manager
manager = ConnectionManager()
