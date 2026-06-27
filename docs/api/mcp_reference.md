# MCP Layer API Reference

> Phase 2 — AI SRE Copilot

## Overview

The MCP layer exposes two independent FastMCP servers that give SRE agents
structured, typed access to observability data and incident response actions.

| Server | Module | Transport |
|---|---|---|
| Monitoring Server | `backend.mcp_servers.monitoring_server` | stdio (MCP) |
| Incident Server | `backend.mcp_servers.incident_server` | stdio (MCP) |

---

## Monitoring MCP Server

**Name:** `AI SRE Copilot — Monitoring Server`

Run standalone:
```bash
python -m backend.mcp_servers.monitoring_server
```

### Tools

#### `get_alerts()`

Fetch all active (FIRING or PENDING) alerts. RESOLVED alerts are excluded.

**Returns:** `list[dict]`

| Field | Type | Description |
|---|---|---|
| `alert_id` | `str` | Unique alert ID (e.g. `ALERT-2026-001`) |
| `name` | `str` | Alert rule name |
| `service` | `str` | Affected service |
| `severity` | `str` | `CRITICAL` \| `WARNING` \| `INFO` |
| `status` | `str` | `FIRING` \| `PENDING` |
| `started_at` | `str` | ISO-8601 timestamp |
| `duration_seconds` | `int` | Active duration |
| `labels` | `dict` | Routing labels |
| `annotations` | `dict` | summary, description, runbook_url |

---

#### `get_metrics(service_id, metric_name, range_minutes=60)`

Retrieve time-series performance metrics.

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `service_id` | `str` | — | Service identifier |
| `metric_name` | `str` | — | Metric name |
| `range_minutes` | `int` | `60` | Minutes of history (1 point ≈ 5 min) |

**Available services and metrics:**

| Service | Metrics |
|---|---|
| `checkout-service` | `db_connection_pool_usage`, `error_rate`, `latency_p99`, `request_rate` |
| `payments-db-v2` | `db_connection_pool_usage`, `query_latency_p99`, `active_transactions` |
| `billing-service` | `db_connection_pool_usage`, `request_rate` |
| `api-gateway` | `request_rate`, `error_rate` |
| `auth-service` | `request_rate`, `latency_p99` |

**Returns:** `dict`

| Field | Type | Description |
|---|---|---|
| `service_id` | `str` | Echoed from input |
| `metric_name` | `str` | Echoed from input |
| `unit` | `str` | Measurement unit |
| `data_points` | `list[dict]` | `[{timestamp, value}]` sorted oldest first |
| `summary` | `dict` | `{min, max, avg, current}` |

**Raises:** `ValueError` if service or metric not found.

---

#### `query_logs(service_id, query_string="", count=50)`

Search log entries for a given service.

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `service_id` | `str` | — | Service to query |
| `query_string` | `str` | `""` | Case-insensitive keyword filter |
| `count` | `int` | `50` | Max results (capped at 200) |

**Returns:** `list[dict]` — each entry has `timestamp`, `level`, `service`, `message`, `trace_id`, `metadata`.

---

### Resources

#### `topology://current`

Returns the complete microservice dependency graph as a JSON string.

```json
{
  "services": [...],
  "dependencies": [...],
  "what_if_impact": {...}
}
```

#### `incidents://history`

Returns historical resolved incidents as a JSON string. Used for pattern correlation.

```json
[
  {
    "incident_id": "INC-789",
    "root_cause": "...",
    "runbook_used": "RB-DB-004",
    ...
  }
]
```

---

### Prompts

#### `rca-template`

Structured Root Cause Analysis guidance. Instructs the RCA agent to produce:
- Incident summary
- Primary root cause (one sentence)
- Evidence chain (cited metric values + log messages)
- Confidence score (0–100%)
- Blast radius assessment
- Human approval gate

---

## Incident MCP Server

**Name:** `AI SRE Copilot — Incident Server`

Run standalone:
```bash
python -m backend.mcp_servers.incident_server
```

### Tools

#### `simulate_runbook_execution(runbook_id, parameters=None)`

Safe simulation of a remediation runbook. **Does NOT make real production changes.**

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `runbook_id` | `str` | — | Runbook ID (e.g. `RB-DB-004`) |
| `parameters` | `dict \| None` | `None` | Key/value substitutions for step commands |

**Returns:** `dict`

| Field | Type | Description |
|---|---|---|
| `runbook_id` | `str` | Echoed ID |
| `title` | `str` | Human-readable title |
| `status` | `str` | `SUCCESS` \| `PARTIAL` \| `BLOCKED` |
| `simulation_output` | `list[dict]` | Per-step results |
| `risk_level` | `str` | `LOW` \| `MEDIUM` \| `HIGH` \| `CRITICAL` |
| `requires_human_approval` | `bool` | True if manual approval needed |
| `pre_flight_checks` | `list[dict]` | Checks with `status: PASS/FAIL` |
| `simulated_at` | `str` | ISO-8601 timestamp |

**Raises:** `ValueError` if runbook not found.

---

#### `escalate_incident(oncall_team, incident_summary, severity="P1", incident_id="UNKNOWN")`

Simulate escalating an incident to the on-call team (PagerDuty/OpsGenie simulation).

**Severity → Channels mapping:**

| Severity | Channels |
|---|---|
| P0 | phone, sms, slack, pagerduty |
| P1 | sms, slack, pagerduty |
| P2 | slack, pagerduty |
| P3 | slack |
| P4 | slack |

**Returns:** `dict` with `escalation_id`, `status`, `channels`, `message`, `escalated_at`, `simulated: True`.

---

### Resources

#### `runbooks://list`

Returns the runbook library index as JSON:

```json
{
  "runbooks": [
    {
      "id": "RB-DB-004",
      "title": "Graceful Database Connection Pool Reset",
      "risk_level": "MEDIUM",
      "requires_human_approval": true,
      ...
    }
  ],
  "total": 5
}
```

#### `runbook://{runbook_id}`

Returns full runbook detail including steps, pre-flight checks, and rollback procedure.

**Available runbooks:**

| ID | Title | Risk | Human Approval |
|---|---|---|---|
| `RB-DB-004` | Graceful DB Connection Pool Reset | MEDIUM | Yes |
| `RB-DB-001` | Emergency DB Connection Kill | HIGH | Yes |
| `RB-DB-002` | DB Failover to Read Replica | CRITICAL | Yes |
| `RB-CACHE-001` | Flush Redis Cache — Selective | LOW | No |
| `RB-SVC-001` | Rolling Service Restart | MEDIUM | Yes |

---

### Prompts

#### `incident-status-update`

Template for generating external stakeholder status updates. Produces clean,
non-technical messages for Slack, status pages, or executive briefings.

---

## Mock Dataset

Located in `backend/mcp_servers/data/`:

| File | Description |
|---|---|
| `alerts.json` | 5 alerts (4 active, 1 resolved) for the DB pool exhaustion scenario |
| `metrics.json` | 16 time-series data points per metric across 5 services |
| `logs.json` | Structured log entries with trace IDs and metadata per service |
| `topology.json` | 7 services, 8 dependency edges, what-if blast radius data |
| `runbooks.json` | 5 detailed runbooks with steps, pre-flight checks, rollback |
| `incidents_history.json` | 4 historical incidents for RCA correlation |

### Incident Scenario Narrative

The mock data tells a coherent story:

1. **10:00** — `checkout-service` DB pool at 35% (normal baseline)
2. **10:30** — Pool climbs to 62% (slow connection leak begins)
3. **11:00** — Pool saturates at 99%. CRITICAL alerts fire.
4. **11:15** — Pool at 100%. `checkout-service` returns HTTP 503.
5. **Historical match** — INC-789 had identical symptoms, resolved with `RB-DB-004`.
6. **Recommended action** — Simulate `RB-DB-004`, obtain human approval, execute.
