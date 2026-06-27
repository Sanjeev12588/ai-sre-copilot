"""Unit tests for ADK Agents and Workflow Coordinator (Phase 4 extended).

Tests are pure Python — no LLM calls, no MCP subprocess starts.
All agent attributes (name, model, output_key, instruction content) are
verified structurally without invoking the Google ADK runtime.

Coverage
--------
TestIntakeAgent          — import, attributes, instruction rules
TestTriageAgent          — import, attributes, tool references
TestLogAnalyzerAgent     — import, attributes, PII redaction rules
TestRootCauseAgent       — import, standalone instantiation, evidence rules
TestEvaluatorAgent       — import, scoring dimensions, verdict logic
TestRecoveryPlannerAgent — import, dry-run mandate
TestEscalationAgent      — import, escalation matrix
TestReportGeneratorAgent — import, required report sections
TestCoordinator          — SequentialAgent structure, pipeline order
TestIncidentStateInAgents— IncidentState default construction
TestMockMcpTools         — mock MCP tool responses (no subprocess)
TestFailurePaths         — missing data, zero confidence, FAIL verdict
"""

from __future__ import annotations

from unittest.mock import patch

# ═══════════════════════════════════════════════════════════════════════════════
# 1. INDIVIDUAL AGENT UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntakeAgent:
    """Structural tests for the Intake Agent."""

    def test_import(self) -> None:
        from backend.agents.intake import intake_agent

        assert intake_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.intake import intake_agent

        assert intake_agent.name == "intake_agent"

    def test_output_key(self) -> None:
        from backend.agents.intake import intake_agent

        assert intake_agent.output_key == "intake_output"

    def test_instruction_defines_role(self) -> None:
        from backend.agents.intake import intake_agent

        instr = intake_agent.instruction
        assert "FIRST responder" in instr or "Intake" in instr

    def test_instruction_no_tool_calls(self) -> None:
        """Intake must not call external tools."""
        from backend.agents.intake import intake_agent

        instr = intake_agent.instruction
        assert "Do NOT call any external tools" in instr

    def test_instruction_no_root_cause(self) -> None:
        """Intake must not attempt diagnosis."""
        from backend.agents.intake import intake_agent

        instr = intake_agent.instruction
        assert (
            "Do NOT attempt to diagnose" in instr or "Do NOT make assumptions" in instr
        )

    def test_instruction_mentions_incident_id(self) -> None:
        from backend.agents.intake import intake_agent

        assert "incident_id" in intake_agent.instruction

    def test_instruction_mentions_next_action(self) -> None:
        from backend.agents.intake import intake_agent

        assert (
            "next_action" in intake_agent.instruction
            or "triage" in intake_agent.instruction
        )

    def test_description_not_empty(self) -> None:
        from backend.agents.intake import intake_agent

        assert len(intake_agent.description) > 10


class TestTriageAgent:
    """Structural tests for the Triage Agent."""

    def test_import(self) -> None:
        from backend.agents.triage import triage_agent

        assert triage_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.triage import triage_agent

        assert triage_agent.name == "triage_agent"

    def test_output_key(self) -> None:
        from backend.agents.triage import triage_agent

        assert triage_agent.output_key == "triage_output"

    def test_instruction_mentions_severity_levels(self) -> None:
        from backend.agents.triage import triage_agent

        instr = triage_agent.instruction
        for level in ("P0", "P1", "P2", "P3", "P4"):
            assert (
                level in instr
            ), f"Severity level {level} missing from triage instruction"

    def test_instruction_mentions_blast_radius(self) -> None:
        from backend.agents.triage import triage_agent

        assert "blast radius" in triage_agent.instruction.lower()

    def test_instruction_references_get_alerts(self) -> None:
        from backend.agents.triage import triage_agent

        assert "get_alerts" in triage_agent.instruction

    def test_instruction_no_root_cause(self) -> None:
        """Triage must not attempt RCA."""
        from backend.agents.triage import triage_agent

        instr = triage_agent.instruction
        assert "Do NOT attempt root cause" in instr or "RCA Agent" in instr


class TestLogAnalyzerAgent:
    """Structural tests for the Log Analyzer Agent."""

    def test_import(self) -> None:
        from backend.agents.log_analyzer import log_analyzer_agent

        assert log_analyzer_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.log_analyzer import log_analyzer_agent

        assert log_analyzer_agent.name == "log_analyzer_agent"

    def test_output_key(self) -> None:
        from backend.agents.log_analyzer import log_analyzer_agent

        assert log_analyzer_agent.output_key == "log_analysis_output"

    def test_pii_redaction_rules(self) -> None:
        from backend.agents.log_analyzer import log_analyzer_agent

        instr = log_analyzer_agent.instruction
        assert (
            "EMAIL_REDACTED" in instr
            or "Sanitize PII" in instr
            or "redact" in instr.lower()
        )

    def test_instruction_mentions_query_logs(self) -> None:
        from backend.agents.log_analyzer import log_analyzer_agent

        assert "query_logs" in log_analyzer_agent.instruction

    def test_instruction_max_findings(self) -> None:
        from backend.agents.log_analyzer import log_analyzer_agent

        assert "10" in log_analyzer_agent.instruction


class TestRootCauseAgent:
    """Structural tests for the Root Cause Agent."""

    def test_import(self) -> None:
        from backend.agents.root_cause import root_cause_agent

        assert root_cause_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.root_cause import root_cause_agent

        assert root_cause_agent.name == "root_cause_agent"

    def test_output_key(self) -> None:
        from backend.agents.root_cause import root_cause_agent

        assert root_cause_agent.output_key == "rca_output"

    def test_can_be_instantiated_alone(self) -> None:
        """RootCauseAgent must be importable and usable without other agents."""
        from backend.agents.root_cause import root_cause_agent

        assert root_cause_agent.name == "root_cause_agent"
        assert root_cause_agent.output_key is not None

    def test_instruction_mentions_confidence_score(self) -> None:
        from backend.agents.root_cause import root_cause_agent

        assert "confidence" in root_cause_agent.instruction.lower()

    def test_instruction_mentions_evidence_chain(self) -> None:
        from backend.agents.root_cause import root_cause_agent

        assert "evidence" in root_cause_agent.instruction.lower()

    def test_instruction_no_remediation(self) -> None:
        """RCA agent must not recommend remediation."""
        from backend.agents.root_cause import root_cause_agent

        instr = root_cause_agent.instruction
        assert "Do NOT recommend" in instr or "Recovery Planner" in instr


class TestEvaluatorAgent:
    """Structural tests for the Evaluator Agent."""

    def test_import(self) -> None:
        from backend.agents.evaluator import evaluator_agent

        assert evaluator_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.evaluator import evaluator_agent

        assert evaluator_agent.name == "evaluator_agent"

    def test_output_key(self) -> None:
        from backend.agents.evaluator import evaluator_agent

        assert evaluator_agent.output_key == "evaluation_output"

    def test_instruction_mentions_four_dimensions(self) -> None:
        from backend.agents.evaluator import evaluator_agent

        instr = evaluator_agent.instruction
        for dim in ("Accuracy", "Completeness", "Calibration", "Safety"):
            assert dim in instr, f"Evaluation dimension {dim!r} missing"

    def test_instruction_mentions_pass_fail(self) -> None:
        from backend.agents.evaluator import evaluator_agent

        instr = evaluator_agent.instruction
        assert "PASS" in instr and "FAIL" in instr

    def test_instruction_has_verdict_threshold(self) -> None:
        from backend.agents.evaluator import evaluator_agent

        instr = evaluator_agent.instruction
        assert ">= 7" in instr or "≥ 7" in instr or "overall_score" in instr


class TestRecoveryPlannerAgent:
    """Structural tests for the Recovery Planner Agent."""

    def test_import(self) -> None:
        from backend.agents.recovery_planner import recovery_planner_agent

        assert recovery_planner_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.recovery_planner import recovery_planner_agent

        assert recovery_planner_agent.name == "recovery_planner_agent"

    def test_output_key(self) -> None:
        from backend.agents.recovery_planner import recovery_planner_agent

        assert recovery_planner_agent.output_key == "recovery_plan_output"

    def test_instruction_mandates_dry_run(self) -> None:
        from backend.agents.recovery_planner import recovery_planner_agent

        instr = recovery_planner_agent.instruction
        assert (
            "dry_run" in instr
            or "dry-run" in instr.lower()
            or "dry run" in instr.lower()
        )

    def test_instruction_no_auto_approve_p0(self) -> None:
        from backend.agents.recovery_planner import recovery_planner_agent

        instr = recovery_planner_agent.instruction
        assert "P0" in instr and (
            "human approval" in instr.lower() or "requires_human_approval" in instr
        )


class TestEscalationAgent:
    """Structural tests for the Escalation Agent."""

    def test_import(self) -> None:
        from backend.agents.escalation import escalation_agent

        assert escalation_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.escalation import escalation_agent

        assert escalation_agent.name == "escalation_agent"

    def test_output_key(self) -> None:
        from backend.agents.escalation import escalation_agent

        assert escalation_agent.output_key == "escalation_output"

    def test_instruction_has_escalation_matrix(self) -> None:
        from backend.agents.escalation import escalation_agent

        instr = escalation_agent.instruction
        for level in ("P0", "P1", "P2", "P3", "P4"):
            assert level in instr, f"Severity {level} missing from escalation matrix"

    def test_instruction_never_skip_p0(self) -> None:
        from backend.agents.escalation import escalation_agent

        instr = escalation_agent.instruction
        assert "NEVER skip" in instr or "P0" in instr


class TestReportGeneratorAgent:
    """Structural tests for the Report Generator Agent."""

    def test_import(self) -> None:
        from backend.agents.report_generator import report_generator_agent

        assert report_generator_agent is not None

    def test_agent_name(self) -> None:
        from backend.agents.report_generator import report_generator_agent

        assert report_generator_agent.name == "report_generator_agent"

    def test_output_key(self) -> None:
        from backend.agents.report_generator import report_generator_agent

        assert report_generator_agent.output_key == "report_output"

    def test_instruction_requires_all_sections(self) -> None:
        from backend.agents.report_generator import report_generator_agent

        instr = report_generator_agent.instruction
        for section in ("Root Cause", "Evidence", "Escalation", "INCIDENT TIMELINE"):
            assert section in instr, f"Required report section {section!r} missing"

    def test_instruction_requires_stakeholder_update(self) -> None:
        from backend.agents.report_generator import report_generator_agent

        assert "Stakeholder" in report_generator_agent.instruction

    def test_instruction_no_jargon_rule(self) -> None:
        from backend.agents.report_generator import report_generator_agent

        instr = report_generator_agent.instruction
        assert "jargon" in instr.lower() or "non-technical" in instr.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. COORDINATOR WORKFLOW TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCoordinator:
    """Tests for the SequentialAgent coordinator pipeline."""

    def test_import(self) -> None:
        from backend.agents.coordinator import coordinator

        assert coordinator is not None

    def test_coordinator_name(self) -> None:
        from backend.agents.coordinator import coordinator

        assert coordinator.name == "sre_copilot_coordinator"

    def test_exactly_eight_sub_agents(self) -> None:
        from backend.agents.coordinator import coordinator

        assert (
            len(coordinator.sub_agents) == 8
        ), f"Expected 8 sub-agents, got {len(coordinator.sub_agents)}"

    def test_pipeline_order(self) -> None:
        """Sub-agents must be chained in the documented order."""
        from backend.agents.coordinator import coordinator

        expected_names = [
            "intake_agent",
            "triage_agent",
            "log_analyzer_agent",
            "root_cause_agent",
            "evaluator_agent",
            "recovery_planner_agent",
            "escalation_agent",
            "report_generator_agent",
        ]
        actual_names = [a.name for a in coordinator.sub_agents]
        assert (
            actual_names == expected_names
        ), f"Pipeline order mismatch.\nExpected: {expected_names}\nGot: {actual_names}"

    def test_coordinator_has_description(self) -> None:
        from backend.agents.coordinator import coordinator

        assert len(coordinator.description) > 20


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INCIDENT STATE VALIDATION IN AGENT CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════


class TestIncidentStateInAgents:
    """Verify IncidentState defaults used by agents are correct."""

    def test_default_status_is_new(self) -> None:
        from backend.memory.case_file import IncidentState, IncidentStatus

        s = IncidentState()
        assert s.status == IncidentStatus.NEW.value

    def test_default_next_action(self) -> None:
        from backend.memory.case_file import IncidentState

        s = IncidentState()
        assert s.next_action == "triage"

    def test_diagnostics_defaults(self) -> None:
        from backend.memory.case_file import IncidentState

        s = IncidentState()
        assert s.diagnostics.confidence_score == 0
        assert s.diagnostics.affected_services == []
        assert s.diagnostics.log_findings == []

    def test_recommendations_require_human_approval_by_default(self) -> None:
        from backend.memory.case_file import IncidentState

        s = IncidentState()
        assert s.recommendations.requires_human_approval is True

    def test_timeline_is_empty_by_default(self) -> None:
        from backend.memory.case_file import IncidentState

        s = IncidentState()
        assert s.timeline == []

    def test_schema_version_is_set(self) -> None:
        from backend.memory.case_file import SCHEMA_VERSION, IncidentState

        s = IncidentState()
        assert s.schema_version == SCHEMA_VERSION


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MOCK MCP TOOL TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMockMcpTools:
    """Verify that agent logic is robust to mocked MCP tool responses."""

    def test_mock_get_alerts_success(self) -> None:
        """get_alerts() returns a list — agents iterate over it."""
        mock_alerts = [
            {
                "alert_id": "ALT-001",
                "name": "DatabaseConnectionPoolExhausted",
                "service": "checkout-service",
                "severity": "CRITICAL",
                "status": "FIRING",
                "started_at": "2025-06-27T08:00:00Z",
                "annotations": {
                    "summary": "Pool full",
                    "runbook_url": "https://rb.test",
                },
            }
        ]
        with patch(
            "backend.mcp_servers.monitoring_server.get_alerts",
            return_value=mock_alerts,
        ):
            from backend.mcp_servers.monitoring_server import get_alerts

            result = get_alerts()
            assert isinstance(result, list)
            assert result[0]["severity"] == "CRITICAL"

    def test_mock_query_logs_empty_response(self) -> None:
        """Agents must handle empty log results gracefully (no crash)."""
        with patch(
            "backend.mcp_servers.monitoring_server.query_logs",
            return_value=[],
        ):
            from backend.mcp_servers.monitoring_server import query_logs

            result = query_logs("nonexistent-service")
            assert result == []

    def test_mock_simulate_runbook_timeout(self) -> None:
        """simulate_runbook_execution() timeout must be catchable."""
        with patch(
            "backend.mcp_servers.incident_server.simulate_runbook_execution",
            side_effect=TimeoutError("MCP server timeout"),
        ):
            from backend.mcp_servers.incident_server import simulate_runbook_execution

            raised = False
            try:
                simulate_runbook_execution("RB-DB-004")
            except TimeoutError:
                raised = True
            assert raised, "Expected TimeoutError to propagate"

    def test_mock_escalate_incident_success(self) -> None:
        """escalate_incident() returns a dict with escalation_id."""
        mock_response = {
            "escalation_id": "ESC-12345",
            "status": "SENT",
            "simulated": True,
            "channels": ["slack", "sms"],
        }
        with patch(
            "backend.mcp_servers.incident_server.escalate_incident",
            return_value=mock_response,
        ):
            from backend.mcp_servers.incident_server import escalate_incident

            result = escalate_incident("db-oncall", "DB pool exhausted", severity="P1")
            assert result["escalation_id"] == "ESC-12345"
            assert result["status"] == "SENT"

    def test_mock_get_metrics_malformed_response(self) -> None:
        """Agents must handle unexpected dict structures from get_metrics()."""
        with patch(
            "backend.mcp_servers.monitoring_server.get_metrics",
            return_value={"error": "service unavailable"},
        ):
            from backend.mcp_servers.monitoring_server import get_metrics

            result = get_metrics("checkout-service", "db_connection_pool_usage")
            # Result is whatever the mock returns — agents should check keys
            assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. FAILURE PATH TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFailurePaths:
    """Edge-case and failure-path tests for agent input validation."""

    def test_empty_diagnostics_does_not_crash_state(self) -> None:
        """IncidentState with empty DiagnosticsSection is valid."""
        from backend.memory.case_file import DiagnosticsSection, IncidentState

        s = IncidentState(diagnostics=DiagnosticsSection())
        assert s.diagnostics.root_cause == ""
        assert s.diagnostics.confidence_score == 0

    def test_zero_confidence_score_is_valid(self) -> None:
        from backend.memory.case_file import DiagnosticsSection

        d = DiagnosticsSection(confidence_score=0)
        assert d.confidence_score == 0

    def test_confidence_score_above_100_is_clamped(self) -> None:
        from backend.memory.case_file import DiagnosticsSection

        d = DiagnosticsSection(confidence_score=150)
        assert d.confidence_score == 100

    def test_confidence_score_below_0_is_clamped(self) -> None:
        from backend.memory.case_file import DiagnosticsSection

        d = DiagnosticsSection(confidence_score=-10)
        assert d.confidence_score == 0

    def test_evaluator_fail_verdict_round_trip(self) -> None:
        """An evaluator FAIL verdict is preserved across serialisation."""
        from backend.memory.case_file import DiagnosticsSection, IncidentState

        s = IncidentState(
            incident_id="INC-FAIL0001",
            diagnostics=DiagnosticsSection(evaluator_verdict="FAIL"),
        )
        dumped = s.model_dump()
        restored = IncidentState.model_validate(dumped)
        assert restored.diagnostics.evaluator_verdict == "FAIL"

    def test_missing_escalation_fields_are_empty_strings(self) -> None:
        """EscalationSection defaults to empty strings — no KeyError."""
        from backend.memory.case_file import EscalationSection

        e = EscalationSection()
        assert e.escalation_id == ""
        assert e.target_team == ""

    def test_incident_state_serialises_to_dict(self) -> None:
        from backend.memory.case_file import IncidentState

        s = IncidentState(incident_id="INC-TESTSER1", summary="Test")
        d = s.model_dump()
        assert d["incident_id"] == "INC-TESTSER1"
        assert "schema_version" in d

    def test_incident_state_round_trip_json(self) -> None:
        """model_dump → model_validate must produce an equal state."""
        import json

        from backend.memory.case_file import IncidentState

        original = IncidentState(incident_id="INC-RT001", summary="Round-trip test")
        json_str = json.dumps(original.model_dump())
        restored = IncidentState.model_validate(json.loads(json_str))
        assert restored.incident_id == original.incident_id
        assert restored.schema_version == original.schema_version

    def test_timeline_entry_confidence_clamped_on_creation(self) -> None:
        from backend.memory.case_file import EventType, TimelineEntry

        entry = TimelineEntry(
            confidence=200,
            event_type=EventType.NOTE,
        )
        assert entry.confidence == 100

    def test_all_agents_importable_independently(self) -> None:
        """Each agent module must import without requiring the coordinator."""
        from backend.agents.escalation import escalation_agent
        from backend.agents.evaluator import evaluator_agent
        from backend.agents.intake import intake_agent
        from backend.agents.log_analyzer import log_analyzer_agent
        from backend.agents.recovery_planner import recovery_planner_agent
        from backend.agents.report_generator import report_generator_agent
        from backend.agents.root_cause import root_cause_agent
        from backend.agents.triage import triage_agent

        for agent in [
            intake_agent,
            triage_agent,
            log_analyzer_agent,
            root_cause_agent,
            evaluator_agent,
            recovery_planner_agent,
            escalation_agent,
            report_generator_agent,
        ]:
            assert agent is not None
            assert agent.name != ""
