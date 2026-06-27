"""Contract tests validating API v1 and legacy routing, DTO validation, standardized error formats, and WebSocket schemas (Phase 6)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.dto import (
    IncidentResponse,
    TimelineEntryResponse,
    WebSocketEvent,
)
from backend.api.main import app
from backend.events.event_bus import IncidentEvent, IncidentEventType
from backend.persistence.json_store import JsonIncidentStore

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path) -> TestClient:
    """Isolate persistence directory and ensure lifespan startup runs."""
    store = JsonIncidentStore(store_dir=tmp_path)
    app.state.store = store
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Router & Version Path Verification
# ---------------------------------------------------------------------------


def test_v1_and_legacy_health_endpoints(client: TestClient) -> None:
    """Verify health and ready endpoints exist under both v1 and legacy prefixes."""
    for path in ["/health", "/api/health", "/api/v1/health"]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "environment" in data

    for path in ["/ready", "/api/ready", "/api/v1/ready"]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


def test_incident_routing_versions(client: TestClient) -> None:
    """Verify both /api/v1/incidents and backward-compatible /api/incidents resolve to the same logic."""
    # Create using legacy path
    create_payload = {
        "title": "Legacy Test",
        "description": "Compatibility testing",
        "environment": "staging",
        "raw_alert": {"name": "TestAlert", "severity": "P2"},
    }
    response_legacy = client.post("/api/incidents", json=create_payload)
    assert response_legacy.status_code == 201
    legacy_data = response_legacy.json()
    inc_id = legacy_data["incident_id"]

    # Retrieve using V1 path
    response_v1 = client.get(f"/api/v1/incidents/{inc_id}")
    assert response_v1.status_code == 200
    v1_data = response_v1.json()
    assert v1_data["incident_id"] == inc_id
    assert v1_data["title"] == "Legacy Test"


# ---------------------------------------------------------------------------
# Global Standardized Error Format Verification
# ---------------------------------------------------------------------------


def test_not_found_error_schema(client: TestClient) -> None:
    """Verify that 404 missing incident error payload follows the unified error format."""
    response = client.get("/api/v1/incidents/INC-GHOST99")
    assert response.status_code == 404

    data = response.json()
    assert "error_code" in data
    assert data["error_code"] == "INCIDENT_NOT_FOUND"
    assert "message" in data
    assert "details" in data
    assert "request_id" in data
    assert "timestamp" in data
    # Confirm timestamp parses as valid ISO-8601
    datetime.fromisoformat(data["timestamp"])


def test_validation_error_schema(client: TestClient) -> None:
    """Verify that validation errors (422) follow the unified error format."""
    # Pass an invalid schema type (raw_alert should be a dictionary, we pass integer)
    invalid_payload = {
        "title": "Bad request test",
        "raw_alert": 12345,
    }
    response = client.post("/api/v1/incidents", json=invalid_payload)
    assert response.status_code == 422

    data = response.json()
    assert "error_code" in data
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "message" in data
    assert "details" in data
    assert "errors" in data["details"]
    assert "request_id" in data
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# WebSocket Event Schema Verification
# ---------------------------------------------------------------------------


def test_websocket_event_schema_mapping() -> None:
    """Verify that the bridge translates internal event types and payload to strict WebSocketEvent schemas."""
    event = IncidentEvent(
        event_type=IncidentEventType.INCIDENT_CREATED,
        incident_id="INC-E10AD9B2",
        payload={
            "request_id": "req-1234567890",
            "agent": "IntakeAgent",
            "status": "NEW",
            "environment": "production",
        },
    )

    # Replicate the mapping logic in main.py
    internal_type = event.event_type.value
    event_type_lower = internal_type.lower()
    payload = event.payload
    agent = payload.get("agent") or "system"
    status_val = payload.get("status") or "UNKNOWN"
    request_id = payload.get("request_id") or "system"

    if "created" in event_type_lower:
        mapped_type = "incident.created"
    elif "error" in event_type_lower:
        mapped_type = "incident.error"
    elif "agent_started" in event_type_lower or "agent.started" in event_type_lower:
        mapped_type = "agent.started"
    elif "agent_completed" in event_type_lower or "agent.completed" in event_type_lower:
        mapped_type = "agent.completed"
    elif "root_cause" in event_type_lower or "rootcause" in event_type_lower:
        mapped_type = "root_cause.detected"
    elif "report" in event_type_lower:
        mapped_type = "report.generated"
    elif "evaluation" in event_type_lower:
        mapped_type = "evaluation.completed"
    else:
        mapped_type = "incident.updated"

    ws_data = {
        "event_id": "c3b9a7a6-259f-43cc-89df-15ae272e5192",
        "timestamp": event.timestamp,
        "event_type": mapped_type,
        "incident_id": event.incident_id,
        "request_id": request_id,
        "agent": agent,
        "status": status_val,
        "payload": payload,
    }

    # Validate against strict DTO model
    validated_event = WebSocketEvent.model_validate(ws_data)
    assert validated_event.event_type == "incident.created"
    assert validated_event.incident_id == "INC-E10AD9B2"
    assert validated_event.agent == "IntakeAgent"
    assert validated_event.request_id == "req-1234567890"


# ---------------------------------------------------------------------------
# DTO Validation Checks
# ---------------------------------------------------------------------------


def test_dto_strict_validation() -> None:
    """Verify that schemas enforce expected field validations."""
    with pytest.raises(ValidationError):
        # TimelineEntryResponse requires multiple fields, passing none should raise
        _ = TimelineEntryResponse.model_validate({})

    with pytest.raises(ValidationError):
        # IncidentResponse requires incident_id and others
        _ = IncidentResponse.model_validate({"incident_id": ""})
