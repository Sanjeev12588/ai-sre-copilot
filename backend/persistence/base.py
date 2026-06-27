"""Abstract persistence interface for incident storage (Phase 4).

Design: Open/Closed Principle
------------------------------
The ``IncidentStore`` ABC defines the contract.  Agent code and service
layer code import and type-hint against this interface only — never
against a concrete class.

To swap backends later (PostgreSQL, Firestore, DynamoDB):
  1. Implement a new class inheriting from ``IncidentStore``.
  2. Update the DI wiring (one line in the app factory).
  3. Zero agent code changes required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.memory.case_file import IncidentState

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class IncidentNotFoundError(Exception):
    """Raised when an incident cannot be found in the persistence store."""

    def __init__(self, incident_id: str) -> None:
        super().__init__(f"Incident {incident_id!r} not found in store.")
        self.incident_id = incident_id


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class IncidentStore(ABC):
    """Abstract base class for incident persistence backends.

    All methods accept and return ``IncidentState`` Pydantic models.
    Implementations handle serialization internally.
    """

    @abstractmethod
    def save(self, incident: IncidentState) -> None:
        """Persist *incident* for the first time.

        Raises ``ValueError`` if an incident with the same ID already exists.
        (Use ``update()`` for subsequent writes.)
        """
        ...

    @abstractmethod
    def load(self, incident_id: str) -> IncidentState:
        """Load and return the ``IncidentState`` for *incident_id*.

        Raises ``IncidentNotFoundError`` if not found.
        Raises the underlying decode/validation error if the stored data is
        malformed.
        """
        ...

    @abstractmethod
    def list_incidents(self) -> list[str]:
        """Return a list of all stored incident IDs (non-archived)."""
        ...

    @abstractmethod
    def update(self, incident: IncidentState) -> None:
        """Overwrite an existing incident record.

        Raises ``IncidentNotFoundError`` if *incident_id* has not been saved.
        """
        ...

    @abstractmethod
    def archive(self, incident_id: str) -> None:
        """Move *incident_id* to the archive tier (removed from active list).

        Raises ``IncidentNotFoundError`` if not found.
        """
        ...

    @abstractmethod
    def delete(self, incident_id: str) -> None:
        """Permanently delete *incident_id* from the store.

        Silent no-op if the incident does not exist.
        """
        ...

    @abstractmethod
    def exists(self, incident_id: str) -> bool:
        """Return ``True`` if *incident_id* currently exists in the active store.

        This is a cheap check (e.g. HEAD request or file existence probe)
        that does not deserialize the full record.
        """
        ...
