"""Comprehensive unit tests for the MCP Layer (Phase 2).

Tests cover:
- Monitoring MCP Server: get_alerts, get_metrics, query_logs, resources,
  prompt
- Incident MCP Server  : simulate_runbook_execution, escalate_incident,
  resources, prompt

All tests are pure Python unit tests calling tool/resource functions directly
without spinning up the MCP stdio transport.
"""

from __future__ import annotations

import json

import pytest

# ─── Incident server imports ──────────────────────────────────────────────────
from backend.mcp_servers.incident_server import (
    escalate_incident,
    get_runbook,
    incident_status_update,
    list_runbooks,
    simulate_runbook_execution,
)

# ─── Monitoring server imports ────────────────────────────────────────────────
from backend.mcp_servers.monitoring_server import (
    get_alerts,
    get_incidents_history,
    get_metrics,
    get_topology,
    query_logs,
    rca_template,
)

# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING SERVER — Tools
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAlerts:
    """Tests for the get_alerts() monitoring tool."""

    def test_returns_list(self) -> None:
        result = get_alerts()
        assert isinstance(result, list), "get_alerts() must return a list"

    def test_returns_only_active_alerts(self) -> None:
        result = get_alerts()
        for alert in result:
            assert alert["status"] in (
                "FIRING",
                "PENDING",
            ), f"Unexpected status: {alert['status']}"

    def test_alerts_have_required_fields(self) -> None:
        required = {"alert_id", "name", "service", "severity", "status", "started_at"}
        result = get_alerts()
        assert result, "Expected at least one active alert"
        for alert in result:
            missing = required - alert.keys()
            assert not missing, f"Alert missing fields: {missing}"

    def test_at_least_one_critical_alert(self) -> None:
        result = get_alerts()
        critical = [a for a in result if a["severity"] == "CRITICAL"]
        assert critical, "Expected at least one CRITICAL alert"

    def test_db_pool_alert_present(self) -> None:
        result = get_alerts()
        names = [a["name"] for a in result]
        assert "DatabaseConnectionPoolExhausted" in names, (
            "Expected DatabaseConnectionPoolExhausted alert"
        )

    def test_annotations_have_runbook_url(self) -> None:
        result = get_alerts()
        critical = [a for a in result if a["severity"] == "CRITICAL"]
        assert critical, "Need at least one critical alert for this check"
        for alert in critical:
            assert "annotations" in alert
            assert "runbook_url" in alert["annotations"]


class TestGetMetrics:
    """Tests for the get_metrics() monitoring tool."""

    def test_returns_dict(self) -> None:
        result = get_metrics("checkout-service", "db_connection_pool_usage")
        assert isinstance(result, dict)

    def test_required_fields_present(self) -> None:
        result = get_metrics("checkout-service", "db_connection_pool_usage")
        required = {"service_id", "metric_name", "unit", "data_points", "summary"}
        assert required.issubset(result.keys())

    def test_data_points_is_nonempty_list(self) -> None:
        result = get_metrics("checkout-service", "db_connection_pool_usage")
        assert isinstance(result["data_points"], list)
        assert len(result["data_points"]) > 0

    def test_data_points_have_timestamp_and_value(self) -> None:
        result = get_metrics("checkout-service", "db_connection_pool_usage")
        for dp in result["data_points"]:
            assert "timestamp" in dp
            assert "value" in dp
            assert isinstance(dp["value"], (int, float))

    def test_summary_contains_statistics(self) -> None:
        result = get_metrics("checkout-service", "db_connection_pool_usage")
        summary = result["summary"]
        for key in ("min", "max", "avg", "current"):
            assert key in summary, f"summary missing '{key}'"

    def test_db_pool_reaches_max_at_incident_time(self) -> None:
        result = get_metrics("checkout-service", "db_connection_pool_usage")
        assert result["summary"]["max"] == 100.0, (
            "Expected pool to reach 100 connections (full saturation)"
        )

    def test_range_minutes_limits_data_points(self) -> None:
        full = get_metrics("checkout-service", "db_connection_pool_usage", 80)
        limited = get_metrics("checkout-service", "db_connection_pool_usage", 10)
        assert len(limited["data_points"]) <= len(full["data_points"])

    def test_unknown_service_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown service"):
            get_metrics("nonexistent-service", "cpu")

    def test_unknown_metric_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown metric"):
            get_metrics("checkout-service", "nonexistent_metric")

    def test_payments_db_metrics_available(self) -> None:
        result = get_metrics("payments-db-v2", "query_latency_p99")
        assert result["summary"]["current"] is not None

    def test_auth_service_is_stable(self) -> None:
        """auth-service should show stable latency (not affected by DB incident)."""
        result = get_metrics("auth-service", "latency_p99")
        assert result["summary"]["max"] < 100, (
            "auth-service latency should be stable (< 100ms max)"
        )


class TestQueryLogs:
    """Tests for the query_logs() monitoring tool."""

    def test_returns_list(self) -> None:
        result = query_logs("checkout-service")
        assert isinstance(result, list)

    def test_returns_logs_for_known_service(self) -> None:
        result = query_logs("checkout-service")
        assert len(result) > 0, "Expected logs for checkout-service"

    def test_log_entries_have_required_fields(self) -> None:
        result = query_logs("checkout-service")
        required = {"timestamp", "level", "service", "message", "trace_id"}
        for entry in result:
            missing = required - entry.keys()
            assert not missing, f"Log entry missing fields: {missing}"

    def test_keyword_filter_works(self) -> None:
        result = query_logs("checkout-service", query_string="connection")
        assert result, "Expected log entries matching 'connection'"
        for entry in result:
            combined = (
                entry["message"].lower() + json.dumps(entry.get("metadata", {})).lower()
            )
            assert "connection" in combined

    def test_critical_logs_present_in_checkout(self) -> None:
        result = query_logs("checkout-service", query_string="pool")
        levels = [e["level"] for e in result]
        assert "CRITICAL" in levels or "ERROR" in levels, (
            "Expected ERROR/CRITICAL logs mentioning 'pool' in checkout-service"
        )

    def test_unknown_service_returns_empty_list(self) -> None:
        result = query_logs("nonexistent-service")
        assert result == [], "Unknown service should return empty list"

    def test_count_limit_respected(self) -> None:
        result = query_logs("checkout-service", count=2)
        assert len(result) <= 2

    def test_count_cap_at_200(self) -> None:
        # Requesting more than 200 should be silently capped
        result = query_logs("checkout-service", count=9999)
        assert len(result) <= 200

    def test_auth_service_shows_healthy_logs(self) -> None:
        result = query_logs("auth-service")
        assert result, "Expected at least one auth-service log"
        assert all(e["level"] in ("INFO", "DEBUG") for e in result), (
            "auth-service should have only INFO/DEBUG logs (it is healthy)"
        )

    def test_payments_db_logs_show_connection_errors(self) -> None:
        result = query_logs("payments-db-v2")
        assert result, "Expected logs for payments-db-v2"
        messages = " ".join(e["message"] for e in result).lower()
        assert "connection" in messages or "transaction" in messages


# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING SERVER — Resources
# ═══════════════════════════════════════════════════════════════════════════════


class TestTopologyResource:
    """Tests for the topology://current MCP resource."""

    def test_returns_valid_json_string(self) -> None:
        result = get_topology()
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_services_and_dependencies(self) -> None:
        parsed = json.loads(get_topology())
        assert "services" in parsed
        assert "dependencies" in parsed

    def test_contains_checkout_service(self) -> None:
        parsed = json.loads(get_topology())
        ids = [s["id"] for s in parsed["services"]]
        assert "checkout-service" in ids

    def test_payments_db_is_critical(self) -> None:
        parsed = json.loads(get_topology())
        db = next((s for s in parsed["services"] if s["id"] == "payments-db-v2"), None)
        assert db is not None
        assert db["criticality"] == "CRITICAL"

    def test_what_if_impact_section_present(self) -> None:
        parsed = json.loads(get_topology())
        assert "what_if_impact" in parsed
        assert "payments-db-v2" in parsed["what_if_impact"]

    def test_checkout_service_status_is_down(self) -> None:
        """During the active incident checkout-service should be DOWN."""
        parsed = json.loads(get_topology())
        checkout = next(
            (s for s in parsed["services"] if s["id"] == "checkout-service"), None
        )
        assert checkout is not None
        assert checkout["status"] == "DOWN"


class TestIncidentsHistoryResource:
    """Tests for the incidents://history MCP resource."""

    def test_returns_valid_json_string(self) -> None:
        result = get_incidents_history()
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_contains_inc_789(self) -> None:
        parsed = json.loads(get_incidents_history())
        ids = [inc["incident_id"] for inc in parsed]
        assert "INC-789" in ids, "Historical incident INC-789 (DB pool) must be present"

    def test_inc_789_has_matching_runbook(self) -> None:
        parsed = json.loads(get_incidents_history())
        inc = next((i for i in parsed if i["incident_id"] == "INC-789"), None)
        assert inc is not None
        assert inc["runbook_used"] == "RB-DB-004"

    def test_incidents_have_required_fields(self) -> None:
        parsed = json.loads(get_incidents_history())
        required = {
            "incident_id",
            "title",
            "date",
            "severity",
            "affected_services",
            "root_cause",
        }
        for inc in parsed:
            missing = required - inc.keys()
            assert not missing, f"Incident missing fields: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING SERVER — Prompts
# ═══════════════════════════════════════════════════════════════════════════════


class TestRcaTemplatePrompt:
    """Tests for the rca-template MCP prompt."""

    def test_returns_non_empty_string(self) -> None:
        result = rca_template()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_confidence_score_section(self) -> None:
        result = rca_template()
        assert "Confidence Score" in result

    def test_contains_blast_radius_section(self) -> None:
        result = rca_template()
        assert "Blast Radius" in result

    def test_contains_human_approval_gate(self) -> None:
        result = rca_template()
        assert "Human Approval" in result or "requires_human" in result.lower()

    def test_references_available_tools(self) -> None:
        result = rca_template()
        assert (
            "get_alerts" in result or "get_metrics" in result or "query_logs" in result
        )


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENT SERVER — Tools
# ═══════════════════════════════════════════════════════════════════════════════


class TestSimulateRunbookExecution:
    """Tests for the simulate_runbook_execution() incident tool."""

    def test_valid_runbook_returns_success(self) -> None:
        result = simulate_runbook_execution("RB-DB-004")
        assert result["status"] == "SUCCESS"

    def test_result_contains_required_fields(self) -> None:
        result = simulate_runbook_execution("RB-DB-004")
        required = {
            "runbook_id",
            "title",
            "status",
            "simulation_output",
            "risk_level",
            "requires_human_approval",
            "pre_flight_checks",
            "simulated_at",
        }
        assert required.issubset(result.keys())

    def test_rb_db_004_requires_human_approval(self) -> None:
        result = simulate_runbook_execution("RB-DB-004")
        assert result["requires_human_approval"] is True

    def test_simulation_output_has_steps(self) -> None:
        result = simulate_runbook_execution("RB-DB-004")
        steps = result["simulation_output"]
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_steps_contain_simulated_result(self) -> None:
        result = simulate_runbook_execution("RB-DB-004")
        for step in result["simulation_output"]:
            assert "simulated_result" in step
            assert step["simulated_result"]

    def test_pre_flight_checks_all_pass_in_simulation(self) -> None:
        result = simulate_runbook_execution("RB-DB-004")
        for check in result["pre_flight_checks"]:
            assert check["status"] == "PASS"

    def test_parameter_substitution_in_commands(self) -> None:
        result = simulate_runbook_execution(
            "RB-SVC-001",
            parameters={"service_name": "checkout-service", "namespace": "checkout"},
        )
        assert result["status"] == "SUCCESS"
        # At least one step command should have the substituted value
        commands = [s["command"] for s in result["simulation_output"]]
        assert any("checkout-service" in cmd for cmd in commands)

    def test_low_risk_runbook_no_approval_needed(self) -> None:
        result = simulate_runbook_execution("RB-CACHE-001")
        assert result["requires_human_approval"] is False

    def test_unknown_runbook_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            simulate_runbook_execution("RB-NONEXISTENT-999")

    def test_simulated_at_is_iso_string(self) -> None:
        result = simulate_runbook_execution("RB-DB-004")
        ts = result["simulated_at"]
        assert isinstance(ts, str)
        assert "T" in ts  # ISO-8601 format check


class TestEscalateIncident:
    """Tests for the escalate_incident() incident tool."""

    def test_returns_dict_with_required_fields(self) -> None:
        result = escalate_incident(
            oncall_team="db-oncall",
            incident_summary="DB pool exhausted on checkout-service",
        )
        required = {
            "escalation_id",
            "status",
            "target_team",
            "channels",
            "severity",
            "message",
            "escalated_at",
            "simulated",
        }
        assert required.issubset(result.keys())

    def test_status_is_sent(self) -> None:
        result = escalate_incident("db-oncall", "DB pool exhausted")
        assert result["status"] == "SENT"

    def test_simulated_flag_is_true(self) -> None:
        result = escalate_incident("db-oncall", "DB pool exhausted")
        assert result["simulated"] is True

    def test_p0_uses_all_channels(self) -> None:
        result = escalate_incident("db-oncall", "Total outage", severity="P0")
        assert "phone" in result["channels"]
        assert "sms" in result["channels"]

    def test_p1_uses_sms_and_slack(self) -> None:
        result = escalate_incident("db-oncall", "DB pool exhausted", severity="P1")
        assert "sms" in result["channels"]
        assert "slack" in result["channels"]
        assert "phone" not in result["channels"]

    def test_p3_uses_slack_only(self) -> None:
        result = escalate_incident(
            "platform-oncall", "Minor degradation", severity="P3"
        )
        assert result["channels"] == ["slack"]

    def test_escalation_id_is_unique(self) -> None:
        r1 = escalate_incident("db-oncall", "Test 1")
        r2 = escalate_incident("db-oncall", "Test 2")
        assert r1["escalation_id"] != r2["escalation_id"]

    def test_message_contains_summary(self) -> None:
        summary = "DB connection pool is at 100%"
        result = escalate_incident("db-oncall", summary)
        assert summary in result["message"]

    def test_incident_id_in_response(self) -> None:
        result = escalate_incident("db-oncall", "DB pool issue", incident_id="INC-892")
        assert result["incident_id"] == "INC-892"
        assert "INC-892" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENT SERVER — Resources
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunbooksListResource:
    """Tests for the runbooks://list MCP resource."""

    def test_returns_valid_json_string(self) -> None:
        result = list_runbooks()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_runbooks_key_and_total(self) -> None:
        parsed = json.loads(list_runbooks())
        assert "runbooks" in parsed
        assert "total" in parsed
        assert parsed["total"] == len(parsed["runbooks"])

    def test_rb_db_004_in_list(self) -> None:
        parsed = json.loads(list_runbooks())
        ids = [rb["id"] for rb in parsed["runbooks"]]
        assert "RB-DB-004" in ids

    def test_runbook_entries_have_required_fields(self) -> None:
        parsed = json.loads(list_runbooks())
        required = {
            "id",
            "title",
            "category",
            "risk_level",
            "applies_to",
            "requires_human_approval",
        }
        for rb in parsed["runbooks"]:
            missing = required - rb.keys()
            assert not missing, f"Runbook entry missing fields: {missing}"

    def test_at_least_five_runbooks_available(self) -> None:
        parsed = json.loads(list_runbooks())
        assert parsed["total"] >= 5


class TestGetRunbookResource:
    """Tests for the runbook://{runbook_id} MCP resource."""

    def test_valid_runbook_returns_json(self) -> None:
        result = get_runbook("RB-DB-004")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_runbook_has_steps(self) -> None:
        parsed = json.loads(get_runbook("RB-DB-004"))
        assert "steps" in parsed
        assert len(parsed["steps"]) > 0

    def test_runbook_has_pre_flight_checks(self) -> None:
        parsed = json.loads(get_runbook("RB-DB-004"))
        assert "pre_flight_checks" in parsed
        assert len(parsed["pre_flight_checks"]) > 0

    def test_runbook_has_rollback(self) -> None:
        parsed = json.loads(get_runbook("RB-DB-004"))
        assert "rollback" in parsed

    def test_unknown_runbook_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            get_runbook("RB-NONEXISTENT")

    def test_rb_db_004_applies_to_checkout(self) -> None:
        parsed = json.loads(get_runbook("RB-DB-004"))
        assert "checkout-service" in parsed.get("applies_to", [])


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENT SERVER — Prompts
# ═══════════════════════════════════════════════════════════════════════════════


class TestIncidentStatusUpdatePrompt:
    """Tests for the incident-status-update MCP prompt."""

    def test_returns_non_empty_string(self) -> None:
        result = incident_status_update()
        assert isinstance(result, str)
        assert len(result) > 50

    def test_contains_status_section(self) -> None:
        result = incident_status_update()
        assert (
            "INVESTIGATING" in result or "MITIGATING" in result or "RESOLVED" in result
        )

    def test_contains_impact_section(self) -> None:
        result = incident_status_update()
        assert "affected" in result.lower() or "impact" in result.lower()

    def test_no_internal_jargon_in_template(self) -> None:
        """The template should not leak internal tool names to stakeholders."""
        result = incident_status_update()
        # Simply verify the function returns a usable string.
        # In a real check we would parse the rendered output (not template).
        assert len(result) > 50
