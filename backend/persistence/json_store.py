"""JSON file-based incident persistence (Phase 4).

Stores each incident as a single JSON file under a configurable directory.

Directory layout
----------------
  <store_dir>/
    INC-AABBCCDD.json          ← active incidents
    archived/
      INC-XXYYZZ.json          ← archived incidents

Atomic writes
-------------
Every write goes to ``<file>.tmp`` first, then ``os.replace()`` renames it
to the target path.  This prevents partial-write corruption on crash.

Logging
-------
Every save / load / update / archive / delete operation is logged with:
  incident_id | status | path | duration_ms
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.memory.case_file import IncidentState
from backend.persistence.base import IncidentNotFoundError, IncidentStore

logger = logging.getLogger(__name__)

# Default storage directory: <project_root>/data/incidents/
_DEFAULT_STORE_DIR = Path(__file__).resolve().parents[2] / "data" / "incidents"


class JsonIncidentStore(IncidentStore):
    """Stores incidents as UTF-8 JSON files, one per ``incident_id``.

    Compatible with the ``IncidentStore`` abstract interface.
    Replace with a database-backed implementation later by pointing the
    DI wiring at a different ``IncidentStore`` subclass — no agent changes.
    """

    def __init__(self, store_dir: Path | str | None = None) -> None:
        self._dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._archive_dir = self._dir / "archived"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "JsonIncidentStore initialised | active=%s | archive=%s",
            self._dir,
            self._archive_dir,
        )

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _active_path(self, incident_id: str) -> Path:
        return self._dir / f"{incident_id}.json"

    def _archive_path(self, incident_id: str) -> Path:
        return self._archive_dir / f"{incident_id}.json"

    # ------------------------------------------------------------------
    # Atomic write
    # ------------------------------------------------------------------

    def _write_atomic(self, path: Path, data: dict[str, Any]) -> None:
        """Write *data* to *path* atomically via a .tmp rename."""
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    # ------------------------------------------------------------------
    # IncidentStore interface
    # ------------------------------------------------------------------

    def save(self, incident: IncidentState) -> None:
        """Save a new incident.  Raises ``ValueError`` if ID already exists."""
        if self.exists(incident.incident_id):
            raise ValueError(
                f"Incident {incident.incident_id!r} already exists. "
                "Use update() to overwrite."
            )
        start = datetime.now(timezone.utc)
        path = self._active_path(incident.incident_id)
        # Include schema_version at the top level for human readability
        data = incident.model_dump()
        self._write_atomic(path, data)
        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.info(
            "Incident saved | incident=%s | status=%s | schema_version=%d"
            " | path=%s | duration_ms=%d",
            incident.incident_id,
            incident.status,
            incident.schema_version,
            path,
            duration_ms,
        )

    def load(self, incident_id: str) -> IncidentState:
        """Load and deserialise an incident.

        Raises
        ------
        IncidentNotFoundError
            If no active file exists for *incident_id*.
        json.JSONDecodeError / pydantic.ValidationError
            If the file is malformed or incompatible with the current schema.
        """
        path = self._active_path(incident_id)
        if not path.exists():
            raise IncidentNotFoundError(incident_id)

        start = datetime.now(timezone.utc)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            state = IncidentState.model_validate(raw)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error(
                "Malformed incident file | incident=%s | error=%s",
                incident_id,
                exc,
            )
            raise

        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.info(
            "Incident loaded | incident=%s | status=%s | duration_ms=%d",
            incident_id,
            state.status,
            duration_ms,
        )
        return state

    def list_incidents(self) -> list[str]:
        """Return all active (non-archived) incident IDs."""
        return sorted(p.stem for p in self._dir.glob("*.json") if p.is_file())

    def update(self, incident: IncidentState) -> None:
        """Overwrite an existing incident.

        Raises ``IncidentNotFoundError`` if the incident has not been saved.
        Logs: incident_id | previous status → new status | duration_ms.
        """
        if not self.exists(incident.incident_id):
            raise IncidentNotFoundError(incident.incident_id)
        start = datetime.now(timezone.utc)
        path = self._active_path(incident.incident_id)
        data = incident.model_dump()
        self._write_atomic(path, data)
        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.info(
            "Incident updated | incident=%s | status=%s | duration_ms=%d",
            incident.incident_id,
            incident.status,
            duration_ms,
        )

    def archive(self, incident_id: str) -> None:
        """Move active incident to the archive subdirectory.

        Raises ``IncidentNotFoundError`` if no active file exists.
        """
        src = self._active_path(incident_id)
        if not src.exists():
            raise IncidentNotFoundError(incident_id)
        dst = self._archive_path(incident_id)
        src.replace(dst)
        logger.info(
            "Incident archived | incident=%s | dst=%s",
            incident_id,
            dst,
        )

    def delete(self, incident_id: str) -> None:
        """Permanently delete an active incident.  Silent no-op if not found."""
        path = self._active_path(incident_id)
        if path.exists():
            path.unlink()
            logger.info("Incident deleted | incident=%s", incident_id)

    def exists(self, incident_id: str) -> bool:
        """Cheap existence check — no deserialisation."""
        return self._active_path(incident_id).exists()
