"""Persistence package — abstract incident storage interface and implementations."""

from backend.persistence.base import IncidentNotFoundError, IncidentStore
from backend.persistence.json_store import JsonIncidentStore

__all__ = [
    "IncidentStore",
    "IncidentNotFoundError",
    "JsonIncidentStore",
]
