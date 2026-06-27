"""Monitoring MCP Server.

Exposes real-time observability data to SRE agents via the Model Context Protocol:
- Tools  : get_alerts, get_metrics, query_logs
- Resources: topology://current, incidents://history
- Prompts : rca-template

Run standalone (stdio transport):
    python -m backend.mcp_servers.monitoring_server
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"

mcp = FastMCP(
    name="AI SRE Copilot — Monitoring Server",
    instructions=(
        "Provides live observability data: active alerts, service metrics, "
        "log queries, service topology, and historical incidents. "
        "Use these tools to gather evidence before performing root cause analysis."
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


def _compute_summary(values: list[float]) -> dict[str, float | None]:
    """Compute basic descriptive statistics for a list of numeric values."""
    if not values:
        return {"min": None, "max": None, "avg": None, "current": None}
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "avg": round(sum(values) / len(values), 4),
        "current": round(values[-1], 4),
    }


# ─── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_alerts() -> list[dict[str, Any]]:
    """Fetch all currently active (FIRING or PENDING) alerts.

    Returns a list of alert objects.  Each object contains:

    - alert_id    : Unique alert identifier (e.g. "ALERT-2026-001")
    - name        : Machine-readable alert rule name
    - service     : Affected service identifier
    - severity    : CRITICAL | WARNING | INFO
    - status      : FIRING | PENDING | RESOLVED
    - started_at  : ISO-8601 timestamp when the alert fired
    - duration_seconds: Seconds the alert has been active
    - labels      : Dict of routing / classification labels
    - annotations : Dict containing summary, description, runbook_url

    Only FIRING and PENDING alerts are returned; RESOLVED ones are excluded.
    """
    logger.info("Tool get_alerts() invoked")
    all_alerts: list[dict[str, Any]] = _load_json("alerts.json")
    active = [a for a in all_alerts if a.get("status") in ("FIRING", "PENDING")]
    logger.debug("Returning %d active alerts (total %d)", len(active), len(all_alerts))
    return active


@mcp.tool()
def get_metrics(
    service_id: str,
    metric_name: str,
    range_minutes: int = 60,
) -> dict[str, Any]:
    """Retrieve time-series performance metrics for a specific service.

    Args:
        service_id   : Service identifier (e.g. "checkout-service",
                       "payments-db-v2", "api-gateway", "billing-service",
                       "auth-service").
        metric_name  : Metric to query.  Available per service:
                       checkout-service  -> db_connection_pool_usage,
                                            error_rate, latency_p99,
                                            request_rate
                       payments-db-v2   -> db_connection_pool_usage,
                                            query_latency_p99,
                                            active_transactions
                       billing-service  -> db_connection_pool_usage,
                                            request_rate
                       api-gateway      -> request_rate, error_rate
                       auth-service     -> request_rate, latency_p99
        range_minutes: Number of most-recent data points to return
                       (one point ≈ 5 min of data; default 60 returns last 12
                       data points).

    Returns:
        Dict with keys:
        - service_id   : echoed from input
        - metric_name  : echoed from input
        - unit         : measurement unit (e.g. "connections", "ms", "req/s")
        - data_points  : list of {timestamp, value} dicts (newest last)
        - summary      : {min, max, avg, current} computed over returned points
    """
    logger.info(
        "Tool get_metrics() invoked: service=%s metric=%s range=%d min",
        service_id,
        metric_name,
        range_minutes,
    )
    all_metrics: dict[str, Any] = _load_json("metrics.json")

    service_data = all_metrics.get(service_id)
    if service_data is None:
        available = sorted(all_metrics.keys())
        raise ValueError(
            f"Unknown service '{service_id}'. Available services: {available}"
        )

    metric_data = service_data.get(metric_name)
    if metric_data is None:
        available = sorted(service_data.keys())
        raise ValueError(
            f"Unknown metric '{metric_name}' for service '{service_id}'. "
            f"Available metrics: {available}"
        )

    # Each stored data point represents ~5 minutes; convert range_minutes
    points_needed = max(1, range_minutes // 5)
    data_points: list[dict[str, Any]] = metric_data["data_points"][-points_needed:]
    values = [dp["value"] for dp in data_points]

    return {
        "service_id": service_id,
        "metric_name": metric_name,
        "unit": metric_data.get("unit", ""),
        "max_value": metric_data.get("max_value"),
        "description": metric_data.get("description", ""),
        "data_points": data_points,
        "summary": _compute_summary(values),
    }


@mcp.tool()
def query_logs(
    service_id: str,
    query_string: str = "",
    count: int = 50,
) -> list[dict[str, Any]]:
    """Search and filter log entries for a given service.

    Args:
        service_id   : Service whose logs to query (e.g. "checkout-service",
                       "billing-service", "payments-db-v2", "api-gateway",
                       "auth-service").
        query_string : Optional case-insensitive keyword/substring filter
                       applied to the log message and metadata fields.
                       Leave empty to return all logs for the service.
        count        : Maximum entries to return (default 50; capped at 200).

    Returns:
        List of log entry dicts, each containing:
        - timestamp : ISO-8601 timestamp
        - level     : DEBUG | INFO | WARNING | ERROR | CRITICAL
        - service   : service name
        - message   : log message text
        - trace_id  : distributed trace identifier
        - metadata  : structured additional fields (stack traces, counts, etc.)

    Entries are ordered chronologically (oldest first).
    """
    logger.info(
        "Tool query_logs() invoked: service=%s query='%s' count=%d",
        service_id,
        query_string,
        count,
    )
    count = min(max(1, count), 200)

    all_logs: dict[str, list[dict[str, Any]]] = _load_json("logs.json")
    service_logs = all_logs.get(service_id, [])

    if not service_logs:
        logger.warning("No logs found for service '%s'", service_id)
        return []

    if query_string:
        qs = query_string.lower()
        service_logs = [
            entry
            for entry in service_logs
            if qs in entry.get("message", "").lower()
            or qs in json.dumps(entry.get("metadata", {})).lower()
        ]
        logger.debug(
            "Log filter '%s' matched %d entries for service '%s'",
            query_string,
            len(service_logs),
            service_id,
        )

    result = service_logs[:count]
    logger.debug(
        "Returning %d log entries for service='%s'",
        len(result),
        service_id,
    )
    return result


# ─── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("topology://current")
def get_topology() -> str:
    """Return the current microservice dependency graph as a JSON string.

    The topology document describes:
    - services     : All known services with id, name, team, criticality,
                     status, replica counts, and metadata.
    - dependencies : Directed edges showing which service calls which,
                     with protocol, type (SYNC/ASYNC), and timeout.
    - what_if_impact: Pre-computed blast-radius analysis per service for
                      use by the What-If simulator.

    Agents should read this resource before performing root cause analysis
    or impact simulation.
    """
    logger.info("Resource topology://current accessed")
    topology = _load_json("topology.json")
    return json.dumps(topology, indent=2)


@mcp.resource("incidents://history")
def get_incidents_history() -> str:
    """Return historical resolved incidents as a JSON string.

    Each incident record contains:
    - incident_id     : Unique identifier (e.g. "INC-789")
    - title           : Short description
    - date            : Date of occurrence
    - severity        : P0–P4
    - duration_minutes: Time to resolution
    - affected_services: List of services involved
    - root_cause      : Detailed root cause description
    - runbook_used    : Which runbook resolved it (if any)
    - lessons_learned : List of post-mortem action items
    - metrics_at_peak : Key metric values at incident peak

    Use this resource to correlate current symptoms against past patterns
    and to recommend proven runbooks.
    """
    logger.info("Resource incidents://history accessed")
    history = _load_json("incidents_history.json")
    return json.dumps(history, indent=2)


# ─── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def rca_template() -> str:
    """Structured Root Cause Analysis guidance prompt for the Root Cause Agent.

    This prompt template instructs the agent to produce evidence-based,
    structured diagnostic output with confidence scoring, blast-radius
    assessment, and an explicit human-approval gate.
    """
    return (
        "You are an expert Site Reliability Engineer conducting a "
        "Root Cause Analysis (RCA).\n\n"
        "## Available Evidence\n"
        "You have access to:\n"
        "- Active alerts (via get_alerts tool)\n"
        "- Service metrics time-series (via get_metrics tool)\n"
        "- Service log samples (via query_logs tool)\n"
        "- Microservice dependency graph (via topology://current resource)\n"
        "- Historical incidents (via incidents://history resource)\n\n"
        "## Analysis Instructions\n"
        "1. Gather all relevant evidence before forming a hypothesis.\n"
        "2. Cross-reference current symptoms against historical incidents.\n"
        "3. Prioritize the service with the earliest anomaly onset.\n"
        "4. Consider cascade effects via the dependency graph.\n"
        "5. Assign a confidence score based on evidence completeness.\n\n"
        "## Required Output Format\n\n"
        "### Incident Summary\n"
        "[One-paragraph description of what is happening and its business impact]\n\n"
        "### Primary Root Cause\n"
        "[Single precise sentence identifying the root cause]\n\n"
        "### Evidence Chain\n"
        "1. [Evidence point 1 — cite metric name, value, and timestamp]\n"
        "2. [Evidence point 2 — cite log message and service]\n"
        "3. [Evidence point 3 — historical incident correlation if applicable]\n\n"
        "### Confidence Score\n"
        "[0–100]% — [One sentence justifying this confidence level]\n\n"
        "### Blast Radius\n"
        "- Directly impacted services: [list]\n"
        "- Cascading risk services: [list]\n"
        "- Estimated user impact: [percentage and description]\n\n"
        "### Contributing Factors\n"
        "- [Factor 1]\n"
        "- [Factor 2]\n\n"
        "### Recommended Runbook\n"
        "[Runbook ID and title — or 'None identified']\n\n"
        "### Requires Human Approval Before Action\n"
        "[YES / NO] — [Reason]\n"
    )


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logger.info("Starting AI SRE Copilot — Monitoring MCP Server")
    mcp.run()
