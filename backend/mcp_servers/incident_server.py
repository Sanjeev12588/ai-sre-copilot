"""Incident MCP Server.

Exposes runbook management and incident response actions to SRE agents
via the Model Context Protocol:
- Tools    : simulate_runbook_execution, escalate_incident
- Resources: runbooks://list, runbook://{runbook_id}
- Prompts  : incident-status-update

Run standalone (stdio transport):
    python -m backend.mcp_servers.incident_server
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"

mcp = FastMCP(
    name="AI SRE Copilot — Incident Server",
    instructions=(
        "Provides incident response capabilities: runbook simulation, "
        "escalation to on-call teams, and stakeholder communication templates. "
        "Always simulate a runbook before recommending execution. "
        "Require human approval for HIGH or CRITICAL risk runbooks."
    ),
)


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _load_json(filename: str) -> Any:
    """Load and parse a JSON file from the data directory.

    Args:
        filename: Filename relative to the data directory.

    Returns:
        Parsed JSON content.

    Raises:
        FileNotFoundError: If the data file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    path = DATA_DIR / filename
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.error("Data file not found: %s", path)
        raise
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", path, exc)
        raise


def _now_iso() -> str:
    """Return the current UTC datetime as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


# ─── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def simulate_runbook_execution(
    runbook_id: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Simulate executing a remediation runbook and return the predicted outcome.

    This is a **safe read-only simulation** — it does NOT make real changes to
    production systems.  The simulation evaluates each step, runs pre-flight
    checks, and predicts outcomes based on the current system state.

    Args:
        runbook_id : The runbook identifier (e.g. "RB-DB-004", "RB-SVC-001").
                     Call the runbooks://list resource to see all available IDs.
        parameters : Optional key/value overrides for runbook step placeholders
                     (e.g. {"service_name": "checkout-service",
                              "namespace": "checkout"}).
                     Defaults to None (uses runbook defaults).

    Returns:
        Dict containing:
        - runbook_id             : echoed from input
        - title                  : human-readable runbook title
        - status                 : SUCCESS | PARTIAL | BLOCKED
        - simulation_output      : list of per-step simulation results
        - risk_level             : LOW | MEDIUM | HIGH | CRITICAL
        - estimated_duration_seconds: expected real-world execution time
        - requires_human_approval: bool — True if manual approval is required
        - approval_required_from : team/role that must approve (or null)
        - pre_flight_checks      : list of checks with pass/fail status
        - simulated_at           : ISO-8601 timestamp of simulation

    Raises:
        ValueError: If the runbook_id is not found in the runbook library.
    """
    params = parameters or {}
    logger.info(
        "Tool simulate_runbook_execution() invoked: runbook=%s params=%s",
        runbook_id,
        params,
    )

    runbooks: dict[str, Any] = _load_json("runbooks.json")
    runbook = runbooks.get(runbook_id)
    if runbook is None:
        available = sorted(runbooks.keys())
        raise ValueError(
            f"Runbook '{runbook_id}' not found. Available runbooks: {available}"
        )

    # Simulate pre-flight checks (all pass in mock environment)
    pre_flight_results = [
        {"check": check, "status": "PASS", "detail": "Simulated check passed."}
        for check in runbook.get("pre_flight_checks", [])
    ]

    # Simulate each step using stored simulated_result
    step_results = []
    for step in runbook.get("steps", []):
        # Substitute any parameters into command string
        command = step.get("command", "")
        for key, val in params.items():
            command = command.replace(f"{{{key}}}", str(val))

        step_results.append(
            {
                "step": step["step"],
                "action": step["action"],
                "command": command,
                "expected_outcome": step.get("expected_outcome", ""),
                "simulated_result": step.get(
                    "simulated_result", "Simulation completed."
                ),
                "status": "SUCCESS",
            }
        )

    return {
        "runbook_id": runbook_id,
        "title": runbook.get("title", ""),
        "description": runbook.get("description", ""),
        "status": "SUCCESS",
        "simulation_output": step_results,
        "risk_level": runbook.get("risk_level", "UNKNOWN"),
        "estimated_duration_seconds": runbook.get("estimated_duration_seconds", 0),
        "requires_human_approval": runbook.get("requires_human_approval", True),
        "approval_required_from": runbook.get("approval_required_from"),
        "pre_flight_checks": pre_flight_results,
        "post_execution_monitoring": runbook.get("post_execution"),
        "rollback": runbook.get("rollback"),
        "simulated_at": _now_iso(),
    }


@mcp.tool()
def escalate_incident(
    oncall_team: str,
    incident_summary: str,
    severity: str = "P1",
    incident_id: str = "UNKNOWN",
) -> dict[str, Any]:
    """Simulate escalating an incident by paging the on-call team.

    Generates and returns the escalation payload that would be dispatched
    via PagerDuty/OpsGenie integration.  This is a **simulated call** —
    no real pages are sent in the development environment.

    Args:
        oncall_team      : Target on-call team routing key.
                           Valid teams: "db-oncall", "platform-oncall",
                           "checkout-oncall", "payments-oncall",
                           "engineering-vp", "data-platform-oncall".
        incident_summary : Brief description of the incident for the page
                           (140 chars max recommended for SMS compatibility).
        severity         : Incident severity P0–P4 (default "P1").
                           P0 triggers phone + SMS + Slack; P1 triggers
                           SMS + Slack; P2+ triggers Slack only.
        incident_id      : Case file incident ID for cross-referencing
                           (e.g. "INC-892").

    Returns:
        Dict containing:
        - escalation_id  : Unique escalation identifier
        - status         : SENT | QUEUED | FAILED
        - target_team    : team that was paged
        - channels       : list of notification channels used
        - severity       : severity level
        - incident_id    : cross-reference to case file
        - message        : full message sent to the team
        - escalated_at   : ISO-8601 timestamp
        - simulated       : True (always in dev/test mode)
    """
    logger.info(
        "Tool escalate_incident() invoked: team=%s severity=%s incident=%s",
        oncall_team,
        severity,
        incident_id,
    )

    # Map severity to notification channels
    channel_map = {
        "P0": ["phone", "sms", "slack", "pagerduty"],
        "P1": ["sms", "slack", "pagerduty"],
        "P2": ["slack", "pagerduty"],
        "P3": ["slack"],
        "P4": ["slack"],
    }
    channels = channel_map.get(severity.upper(), ["slack"])

    escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    message = (
        f"[{severity.upper()}] INCIDENT ESCALATION | {incident_id}\n"
        f"Team: {oncall_team}\n"
        f"Summary: {incident_summary}\n"
        f"Escalation ID: {escalation_id}\n"
        f"Channels: {', '.join(channels)}\n"
        f"Action Required: Acknowledge within 5 minutes for P0/P1."
    )

    logger.info("Escalation %s simulated for team '%s'", escalation_id, oncall_team)

    return {
        "escalation_id": escalation_id,
        "status": "SENT",
        "target_team": oncall_team,
        "channels": channels,
        "severity": severity.upper(),
        "incident_id": incident_id,
        "message": message,
        "escalated_at": _now_iso(),
        "simulated": True,
        "note": (
            "This is a simulated escalation. "
            "In production this would trigger PagerDuty/OpsGenie."
        ),
    }


# ─── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("runbooks://list")
def list_runbooks() -> str:
    """Return the runbook library index as a JSON string.

    Lists all available runbooks with their id, title, category,
    risk_level, applies_to services, severity_threshold, and whether
    human approval is required.  Use this to identify which runbook
    to simulate for a given incident.
    """
    logger.info("Resource runbooks://list accessed")
    runbooks: dict[str, Any] = _load_json("runbooks.json")

    index = [
        {
            "id": rb_id,
            "title": rb.get("title", ""),
            "category": rb.get("category", ""),
            "risk_level": rb.get("risk_level", ""),
            "applies_to": rb.get("applies_to", []),
            "severity_threshold": rb.get("severity_threshold", ""),
            "requires_human_approval": rb.get("requires_human_approval", True),
            "estimated_duration_seconds": rb.get("estimated_duration_seconds", 0),
        }
        for rb_id, rb in runbooks.items()
    ]
    return json.dumps({"runbooks": index, "total": len(index)}, indent=2)


@mcp.resource("runbook://{runbook_id}")
def get_runbook(runbook_id: str) -> str:
    """Return a specific runbook's full detail as a JSON string.

    Args:
        runbook_id: The runbook identifier (e.g. "RB-DB-004").

    Returns:
        Full runbook JSON including description, pre_flight_checks,
        steps with commands and expected outcomes, rollback procedure,
        and post-execution monitoring criteria.

    Raises:
        ValueError: If the runbook_id is not found.
    """
    logger.info("Resource runbook://%s accessed", runbook_id)
    runbooks: dict[str, Any] = _load_json("runbooks.json")
    runbook = runbooks.get(runbook_id)

    if runbook is None:
        available = sorted(runbooks.keys())
        raise ValueError(f"Runbook '{runbook_id}' not found. Available: {available}")

    return json.dumps(runbook, indent=2)


# ─── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def incident_status_update() -> str:
    """Template prompt for generating external stakeholder status updates.

    Guides the Report Generator agent to produce clear, non-technical
    incident status messages suitable for Slack channels, status pages,
    or executive briefings.
    """
    return (
        "You are an SRE communications specialist. "
        "Generate a clear, concise incident status update "
        "for external stakeholders.\n\n"
        "## Guidelines\n"
        "- Use plain language — no jargon, no internal tool names.\n"
        "- Be factual and honest about impact.\n"
        "- Always state current status (Investigating / Mitigating / Resolved).\n"
        "- Include ETA only if you are confident; otherwise say 'TBD'.\n"
        "- Do NOT share internal runbook names or infrastructure details.\n\n"
        "## Required Output Format\n\n"
        "**[STATUS] Incident Update — {service} | {timestamp}**\n\n"
        "**What is affected:**\n"
        "[Plain description of user-facing impact]\n\n"
        "**Current status:**\n"
        "[INVESTIGATING | MITIGATING | RESOLVED]\n\n"
        "**What we know:**\n"
        "[2-3 sentences on what caused the issue "
        "— at a level suitable for customers]\n\n"
        "**What we are doing:**\n"
        "[Current remediation action in progress]\n\n"
        "**Next update:**\n"
        "[Timestamp or 'When status changes']\n\n"
        "**Impact duration:**\n"
        "[How long the issue has been active]\n"
    )


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logger.info("Starting AI SRE Copilot — Incident MCP Server")
    mcp.run()
