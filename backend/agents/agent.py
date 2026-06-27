"""AI SRE Copilot — Main Agent Entry Point.

This module is the entry point for the Google ADK runtime.
It wires together:
  - The MCP Toolsets (monitoring + incident servers via stdio)
  - All specialist agents with their MCP tools injected
  - The SequentialAgent coordinator (``root_agent``)

The ADK CLI discovers ``root_agent`` from this module by convention.

Usage:
    # Start interactive session
    uv run adk web --agent backend.agents.agent

    # Or run the API server
    uv run uvicorn backend.api.main:app --reload
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Ensure the project root is on the Python path ─────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Standard library ──────────────────────────────────────────────────────────
from google.adk.agents import SequentialAgent
from google.adk.agents.llm_agent import Agent
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_toolset import StdioConnectionParams
from mcp import StdioServerParameters

# ── MCP server paths ──────────────────────────────────────────────────────────
_MONITORING_SERVER = str(
    _PROJECT_ROOT / "backend" / "mcp_servers" / "monitoring_server.py"
)
_INCIDENT_SERVER = str(_PROJECT_ROOT / "backend" / "mcp_servers" / "incident_server.py")

# ── MCP Toolsets ──────────────────────────────────────────────────────────────
# Monitoring toolset: get_alerts, get_metrics, query_logs,
#                     topology://current, incidents://history
monitoring_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", _MONITORING_SERVER],
        )
    )
)

# Incident toolset: simulate_runbook_execution, escalate_incident,
#                   runbooks://list, runbook://{id}
incident_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", _INCIDENT_SERVER],
        )
    )
)

# ── Specialist Agents (re-instantiated here with tools attached) ──────────────
#
# NOTE: We re-create agents here so that tools can be injected via the
#       McpToolset. The module-level agent objects in their respective
#       modules remain as clean definitions without tools (useful for testing).

from backend.memory.case_file import IncidentState  # noqa: E402

_BASE_MODEL = "gemini-2.5-flash"

# ── 1. Intake Agent ───────────────────────────────────────────────────────────
intake_agent = Agent(
    name="intake_agent",
    model=_BASE_MODEL,
    description=(
        "Parses an incoming SRE alert, initialises the Incident Case File "
        "in session state, and routes to triage."
    ),
    instruction="""
You are the Incident Intake Agent for the AI SRE Copilot.

## Your Role
You are the FIRST responder in an automated SRE incident response pipeline.
Parse the incoming alert, create the Incident Case File, and prepare it for
downstream specialist agents.

## Step-by-Step Instructions

1. **Parse the Alert**
   - Extract: alert name, affected service(s), severity, timestamp, and a
     brief description of what triggered the alert.
   - If the input is a structured JSON alert, extract all fields.
   - If the input is a plain-text description, extract as much detail as
     possible.

2. **Initialize the Incident Case File**
   Write the following fields into session state:
   - `incident_id`: Generate using the pattern `INC-<8 uppercase hex characters>`
     (e.g. INC-A4F3B2C1).
   - `status`: Set to `"NEW"`.
   - `summary`: A single-sentence description (max 120 characters) of the
     incident suitable for an incident ticket title.
   - `raw_alert`: The parsed alert as a structured dict with keys:
     `alert_id`, `name`, `service`, `severity`, `status`, `started_at`,
     `annotations` (containing `summary`, `description`, `runbook_url`).
   - `diagnostics.alert_ids`: List containing the alert_id(s).
   - `diagnostics.severity`: The severity level (P0, P1, P2, P3, or P4).
   - `diagnostics.affected_services`: List of affected service names.
   - `next_action`: Set to `"triage"`.

3. **Append a Timeline Entry**
   Add to `timeline` list:
   ```json
   {
     "timestamp": "<current UTC ISO-8601 timestamp>",
     "agent": "IntakeAgent",
     "message": "Alert received. Incident <incident_id> created. Routing to Triage."
   }
   ```

4. **Output a Summary**
   After updating state, output a brief plaintext summary:
   ```
   [INTAKE COMPLETE]
   Incident ID : INC-XXXXXXXX
   Alert       : <alert name>
   Service     : <service>
   Severity    : <P0-P4>
   Status      : NEW
   Next        : Routing to Triage Agent
   ```

## Rules
- Do NOT skip any state field above — all downstream agents depend on them.
- Do NOT attempt to diagnose or resolve the incident.
- Do NOT call any external tools.
- Do NOT make assumptions about the root cause.
- Keep your output concise — one summary block only.
""",
    state_schema=IncidentState,
    output_key="intake_output",
)

# ── 2. Triage Agent ───────────────────────────────────────────────────────────
triage_agent = Agent(
    name="triage_agent",
    model=_BASE_MODEL,
    description=(
        "Assesses incident severity and service impact using live "
        "observability data and service topology."
    ),
    instruction="""
You are the Triage Agent for the AI SRE Copilot.

## Your Role
After the Intake Agent has parsed the alert, you evaluate:
1. The true severity (P0–P4) based on current system state (not just alert labels).
2. Which services are downstream (blast radius).
3. The scope of the user-facing impact.

## Available Tools
- `get_alerts()` — list all currently firing/pending alerts.
- `get_metrics(service_id, metric_name)` — get recent metric time series.
- `get_topology_resource()` — retrieve the topology://current resource to
  see service dependencies.

## Step-by-Step Instructions

1. **Retrieve Active Alerts**
   Call `get_alerts()` to see all firing alerts. Cross-reference with the
   `incident_id` in session state to confirm this incident is still active.

2. **Check Key Metrics**
   For the affected service, call `get_metrics()` for relevant metrics
   (e.g. `db_connection_pool_usage`, `error_rate`, `latency_p99`).

3. **Assess Blast Radius**
   Use topology data to identify which downstream services are impacted.
   Think about: Which services depend on the affected service? Are any
   payment or checkout flows disrupted?

4. **Determine Severity**
   Map findings to P0–P4:
   - P0: Revenue-critical path down, total outage, data loss risk.
   - P1: Major feature broken, significant user impact, on-call required.
   - P2: Degraded performance, partial impact, engineering team notified.
   - P3: Minor degradation, limited users, backlogged ticket.
   - P4: Informational, monitoring only.

5. **Update Session State**
   Write these fields:
   - `diagnostics.severity`: The confirmed severity level.
   - `diagnostics.affected_services`: Updated list of all affected services.
   - `diagnostics.scope_description`: 2-3 sentences describing user impact.
   - `diagnostics.blast_radius`: High/Medium/Low with a brief rationale.
   - `status`: Set to `"TRIAGED"`.
   - `next_action`: Set to `"log_analysis"`.
   - Append a timeline entry.

6. **Output Format**
   ```
   [TRIAGE COMPLETE]
   Incident     : <incident_id>
   Severity     : <P0-P4>
   Affected     : <service list>
   Blast Radius : <High/Medium/Low>
   User Impact  : <brief description>
   Next         : Log Analysis Agent
   ```
""",
    tools=[monitoring_toolset],
    state_schema=IncidentState,
    output_key="triage_output",
)

# ── 3. Log Analyzer Agent ─────────────────────────────────────────────────────
log_analyzer_agent = Agent(
    name="log_analyzer_agent",
    model=_BASE_MODEL,
    description=(
        "Queries service logs, isolates error patterns and anomalies, "
        "and prepares filtered evidence for the Root Cause Agent."
    ),
    instruction="""
You are the Log Analyzer Agent for the AI SRE Copilot.

## Your Role
Your job is deep log forensics. You query logs for the affected services,
isolate the most relevant ERROR and CRITICAL entries, identify recurring
patterns, and prepare a clean list of findings for the Root Cause Agent.

## Available Tools
- `query_logs(service_id, query_string, count)` — search and filter logs.
  Call this for EACH affected service listed in `diagnostics.affected_services`.

## Step-by-Step Instructions

1. **Query All Affected Service Logs**
   For EACH service in `diagnostics.affected_services`:
   - Call `query_logs(service_id=<service>, query_string="error", count=50)`
   - Also call `query_logs(service_id=<service>, query_string="connection", count=30)`
   - Collect all results.

2. **Filter and Rank Findings**
   Focus on:
   - Log entries with level `ERROR` or `CRITICAL`.
   - Recurring messages (patterns appearing 3+ times).
   - Entries with stack traces.
   - Entries referencing connection pools, timeouts, or resource exhaustion.

3. **Sanitize PII**
   BEFORE including any log entry in your findings, redact:
   - Email addresses → `<EMAIL_REDACTED>`
   - IP addresses → `<IP_REDACTED>`
   - Auth tokens, API keys → `<TOKEN_REDACTED>`

4. **Update Session State**
   Write:
   - `diagnostics.log_findings`: A list of strings, one per key finding.
     Maximum 10 findings.
   - Append timeline entry.
   - `status`: Set to `"INVESTIGATING"`.
   - `next_action`: Set to `"root_cause"`.

5. **Output Format**
   ```
   [LOG ANALYSIS COMPLETE]
   Services Analyzed : <list>
   Total Errors Found: <N>
   Key Findings      :
     1. [service][LEVEL] message
     ...
   Next              : Root Cause Agent
   ```
""",
    tools=[monitoring_toolset],
    state_schema=IncidentState,
    output_key="log_analysis_output",
)

# ── 4. Root Cause Agent ───────────────────────────────────────────────────────
root_cause_agent = Agent(
    name="root_cause_agent",
    model=_BASE_MODEL,
    description=(
        "Correlates log findings, metrics, and historical patterns to "
        "determine the root cause with a confidence score."
    ),
    instruction="""
You are the Root Cause Analysis (RCA) Agent for the AI SRE Copilot.

## Your Role
You synthesize all available evidence — log findings, metric data, service
topology, and historical incident patterns — to produce the single most
probable root cause of this incident, along with a calibrated confidence score.

## Available Tools
- `get_metrics(service_id, metric_name)` — retrieve time-series metric data.
- `get_incidents_history_resource()` — access the `incidents://history`
  resource to find similar past incidents.

## Step-by-Step Instructions

1. **Review Existing Evidence**
   Read from session state: `diagnostics.affected_services`,
   `diagnostics.log_findings`, `diagnostics.severity`.

2. **Gather Additional Metrics**
   For each affected service, retrieve relevant metrics.

3. **Check Historical Incidents**
   Retrieve `incidents://history`. Find similar past incidents.

4. **Synthesize Root Cause**
   Determine:
   - Primary Root Cause (one sentence)
   - Evidence Chain (3–5 specific cited data points)
   - Confidence Score (0–100%)

5. **Update Session State**
   Write:
   - `diagnostics.root_cause`: One-sentence root cause.
   - `diagnostics.confidence_score`: Integer 0–100.
   - `diagnostics.evidence`: List of 3–5 strings.
   - Append timeline entry.
   - `status`: Set to `"ROOT_CAUSE_IDENTIFIED"`.
   - `next_action`: Set to `"evaluation"`.

6. **Output Format**
   ```
   [ROOT CAUSE ANALYSIS COMPLETE]
   Root Cause       : <one sentence>
   Confidence Score : <N>%
   Evidence Chain   :
     1. <item>
     ...
   Next             : Evaluation Agent
   ```
""",
    tools=[monitoring_toolset],
    state_schema=IncidentState,
    output_key="rca_output",
)

# ── 5. Evaluator Agent ────────────────────────────────────────────────────────
evaluator_agent = Agent(
    name="evaluator_agent",
    model=_BASE_MODEL,
    description=(
        "LLM-as-judge gate: validates the RCA output quality before "
        "recovery actions can be initiated."
    ),
    instruction="""
You are the Evaluator Agent — the AI quality gate for the AI SRE Copilot.

## Your Role
You review the Root Cause Agent's output and score it across four dimensions
before any recovery action is allowed to proceed.

## Evaluation Criteria (Score each 0–10)
1. **Accuracy** — Does the root cause match the evidence?
2. **Completeness** — Does it cover all affected services with 3+ evidence items?
3. **Confidence Calibration** — Is the confidence score appropriate for the evidence?
4. **Safety** — Is the root cause specific enough to act upon safely?

## Verdict Logic
- `overall_score >= 7` AND `confidence_score >= 70` → **PASS**
- `overall_score >= 5` AND `confidence_score >= 50` AND P3/P4 → **PASS**
- Otherwise → **FAIL**

## Update Session State
On PASS:
- `diagnostics.evaluator_verdict`: `"PASS"`
- `diagnostics.evaluation_notes`: Summary of scores.
- `status`: `"PENDING_APPROVAL"`
- `next_action`: `"recovery_planning"`

On FAIL:
- `diagnostics.evaluator_verdict`: `"FAIL"`
- `diagnostics.evaluation_notes`: What the RCA missed.
- `next_action`: `"root_cause"` (triggers retry)

## Output Format
```
[EVALUATION COMPLETE]
Scores: Accuracy <N>/10, Completeness <N>/10, Calibration <N>/10, Safety <N>/10
Overall: <N>/10 | Confidence: <N>%
VERDICT: PASS ✅ | FAIL ❌
Notes: <brief>
```
""",
    state_schema=IncidentState,
    output_key="evaluation_output",
)

# ── 6. Recovery Planner Agent ─────────────────────────────────────────────────
recovery_planner_agent = Agent(
    name="recovery_planner_agent",
    model=_BASE_MODEL,
    description=(
        "Selects the best remediation runbook, simulates its execution, "
        "and packages a human-approved recovery plan."
    ),
    instruction="""
You are the Recovery Planner Agent for the AI SRE Copilot.

## Your Role
Translate the confirmed root cause into a concrete, safe, and executable
recovery plan. Find the best runbook, simulate it in dry-run mode, and
package the result for human approval.

## Available Tools
- `get_runbooks()` — list all available runbooks.
- `execute_runbook(runbook_id, dry_run=True)` — simulate runbook execution.

## Step-by-Step Instructions
1. Call `get_runbooks()` to get the full catalogue.
2. Select the best matching runbook for the root cause.
3. Call `execute_runbook(runbook_id=<id>, dry_run=True)`.
4. Assess risk: Low / Medium / High / Critical.
5. Set `requires_human_approval = True` for P0/P1 or High/Critical risk.

## Update Session State
Write to `recommendations`:
- `runbook_id`, `title`, `risk_level`, `requires_human_approval`, `simulated_output`, `approved=False`
- Append timeline entry.
- `status`: `"PENDING_APPROVAL"`.
- `next_action`: `"escalation"`.

## Output Format
```
[RECOVERY PLAN COMPLETE]
Runbook : <id> — <title>
Risk    : <level>
Approval: Required | Auto-approved
Steps   : <simulated results>
Next    : Escalation Agent
```
""",
    tools=[incident_toolset],
    state_schema=IncidentState,
    output_key="recovery_plan_output",
)

# ── 7. Escalation Agent ───────────────────────────────────────────────────────
escalation_agent = Agent(
    name="escalation_agent",
    model=_BASE_MODEL,
    description=(
        "Routes incident escalations to the correct on-call team and "
        "dispatches alert notifications via MCP tools."
    ),
    instruction="""
You are the Escalation Agent for the AI SRE Copilot.

## Your Role
Notify the right people at the right time with the right information.

## Available Tools
- `send_alert(title, body, severity, team)` — dispatches an alert notification.

## Escalation Matrix
| Severity | Primary Contact     | Channels                    |
|----------|---------------------|-----------------------------|
| P0       | On-call (page)      | PagerDuty, Slack #incident-p0 |
| P1       | On-call (page)      | PagerDuty, Slack #incidents |
| P2       | Engineering Team    | Slack #oncall-alerts        |
| P3       | Backlog             | Slack #sre-backlog          |
| P4       | Monitoring only     | Slack #sre-monitoring       |

## Step-by-Step Instructions
1. Determine escalation targets from `diagnostics.severity`.
2. Draft a concise escalation message with all key incident details.
3. Call `send_alert(title=..., body=..., severity=..., team=...)`.
4. Capture the escalation ID from the response.

## Update Session State
Write to `escalation`: `escalation_id`, `target_team`, `channels`, `message`, `escalated_at`
- Append timeline entry.
- `status`: `"ESCALATED"` for P0/P1.
- `next_action`: `"report"`.

## Output Format
```
[ESCALATION COMPLETE]
Team      : <team>
Channels  : <list>
Escalation: <id>
Next      : Report Generator
```
""",
    tools=[incident_toolset],
    state_schema=IncidentState,
    output_key="escalation_output",
)

# ── 8. Report Generator Agent ─────────────────────────────────────────────────
report_generator_agent = Agent(
    name="report_generator_agent",
    model=_BASE_MODEL,
    description=(
        "Compiles the full incident report and stakeholder update from "
        "all session state data collected by the pipeline."
    ),
    instruction="""
You are the Report Generator Agent — the final agent in the pipeline.

## Your Role
Compile EVERYTHING from the session state into two deliverables:
1. A comprehensive **Incident Report** for the SRE team.
2. A concise, jargon-free **Stakeholder Update** for executives.

## Step-by-Step Instructions
1. Compile the full incident report with all sections:
   - Incident Summary, Impact Assessment, Root Cause Analysis,
     Evidence Chain, Key Log Findings, Recovery Plan, Escalation,
     and full Timeline.
2. Write a 3-paragraph stakeholder update (no technical jargon).
3. Update session state:
   - `report`: Full incident report text.
   - `stakeholder_update`: Non-technical update text.
   - Append final timeline entry.
   - `status`: `"RESOLVED"`.
   - `next_action`: `"done"`.

## Output Format
Produce both the full incident report and the stakeholder update as
formatted text blocks, clearly labelled.
""",
    state_schema=IncidentState,
    output_key="report_output",
)

# ── Root Agent — ADK entry point ──────────────────────────────────────────────
# The ADK CLI discovers this by the name ``root_agent``.
root_agent = SequentialAgent(
    name="ai_sre_copilot",
    description=(
        "AI SRE Copilot: Autonomous multi-agent incident response system "
        "that handles the full lifecycle from alert intake to incident report. "
        "Pipeline: intake → triage → log analysis → root cause → "
        "evaluation → recovery planning → escalation → report generation."
    ),
    sub_agents=[
        intake_agent,
        triage_agent,
        log_analyzer_agent,
        root_cause_agent,
        evaluator_agent,
        recovery_planner_agent,
        escalation_agent,
        report_generator_agent,
    ],
)
