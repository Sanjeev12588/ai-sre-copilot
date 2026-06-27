# AI SRE Copilot

AI SRE Copilot is an autonomous incident response assistant that analyzes alerts, triages incidents, investigates logs, diagnoses root causes, recommends simulated remediations, and evaluates findings.

This repository represents **Phase 5: Application Gateway & Real-Time Orchestration**, implementing a production-ready FastAPI gateway, WebSocket streaming, event-driven orchestration, background execution, security headers, rate limiting, and integration testing on top of the Phase 4 incident state & lifecycle engine.

---

## Folder Structure

```
ai-sre-copilot/
├── README.md
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── PROJECT_LOG.md
├── .pre-commit-config.yaml
├── .env.example
├── .gitignore
├── .dockerignore
│
├── backend/                           # Python FastAPI + ADK Core
│   ├── __init__.py
│   │
│   ├── agents/                        # ADK Agents (State/Lifecycle logic)
│   │   ├── __init__.py
│   │   ├── agent.py                   # Exports root_agent
│   │   ├── intake.py                  # Parses alert input
│   │   ├── coordinator.py             # Orchestrates & updates Case File
│   │   ├── triage.py                  # Severity & scope analyzer
│   │   ├── log_analyzer.py            # Log anomaly scraper
│   │   ├── root_cause.py              # RCA generator
│   │   ├── evaluator.py               # Reviews RCA, assigns trust scores
│   │   ├── recovery_planner.py        # Recommends runbooks (Simulation)
│   │   ├── escalation.py              # Pagers / Notifications
│   │   └── report_generator.py        # Post-mortem & comms drafter
│   │
│   ├── mcp_servers/                   # MCP Server Implementations
│   │   ├── __init__.py
│   │   ├── monitoring_server.py       # Exposes topology, metrics, logs
│   │   └── incident_server.py         # Exposes runbooks, simulated actions
│   │
│   ├── memory/                        # Session & Case File management
│   │   ├── __init__.py
│   │   └── case_file.py               # Incident Case File structure & utils
│   │
│   ├── security/                      # Input & action guardrails
│   │   ├── __init__.py
│   │   ├── input_validator.py         # Prompt injection validation
│   │   └── pii_redactor.py            # Sanitizes logs before agents see them
│   │
│   └── api/                           # FastAPI Router & Websockets
│       ├── __init__.py
│       ├── main.py                    # Entry point for FastAPI & Web App
│       └── websocket.py               # Streaming agent trace updates to React
│
├── frontend/                          # React/Vite/TS dashboard
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── css/
│   │   │   └── styles.css             # Curated premium SRE styling
│   │   └── components/
│   │       ├── IncidentFeed.tsx       # Active/historical incidents list
│   │       ├── ReasoningTimeline.tsx  # AI Reasoning trace visualization
│   │       ├── WhatIfSimulator.tsx    # Impact analyzer panel
│   │       └── ActionConsole.tsx      # Runbook confirmation panel
│   └── dist/                          # Compiled assets (served by FastAPI)
│
├── docs/                              # Project Documentation
│   ├── architecture/
│   ├── diagrams/
│   ├── api/
│   ├── screenshots/
│   ├── demo/
│   └── kaggle/
│
└── tests/                             # Test Suite
    ├── __init__.py
    ├── test_agents.py
    ├── test_mcp.py
    └── test_security.py
```

---

## Prerequisites

Ensure you have the following installed on your host system:
1. **Python 3.11 or higher**
2. **uv** (Python package manager)
3. **Node.js v18+** and **npm**
4. **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/apikey)

---

## Setup & Installation

1. Clone the repository and navigate into the root directory:
   ```bash
   cd ai-sre-copilot
   ```

2. Copy the environment template and configure your API key:
   ```bash
   cp .env.example .env
   # Open .env and add your GOOGLE_API_KEY
   ```

3. Set up the Python virtual environment and synchronize dependencies:
   ```bash
   uv sync
   ```

4. Install Node dependencies for the React frontend:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

---

## Running the Application Locally

### Running the Python Backend (Development)
To start the FastAPI web server locally:
```bash
uv run uvicorn backend.api.main:app --reload --port 8000
```
API endpoints will be available at `http://127.0.0.1:8000`.

### Running the React Frontend (Development)
To start the Vite development server with hot reload:
```bash
cd frontend
npm run dev
```
The React development UI will be available at `http://localhost:5173`.

### Running with Docker
To build and run the entire stack containerized:
```bash
docker build -t ai-sre-copilot .
docker run -p 8000:8000 --env-file .env ai-sre-copilot
```

---

## Linting & Formatting

Validate Python code syntax, imports, formatting, and stylistic guidelines:
```bash
# Lint check
uv run ruff check backend tests
# Format check
uv run ruff format --check backend tests
```
To auto-fix format/lint issues:
```bash
uv run ruff check backend tests --fix
uv run ruff format backend tests
```

---

## Phase 4: Incident Lifecycle & State Management

### Incident Lifecycle Diagram

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    Incident Lifecycle States                    │
  └─────────────────────────────────────────────────────────────────┘

       NEW
        │
        ▼
      TRIAGED
        │
        ▼
    INVESTIGATING
        │
        ▼
  ROOT_CAUSE_IDENTIFIED
        │
        ▼
    EVALUATING ──────────────────────────────────────────┐
        │   (FAIL: retry RCA)                            │
        │ (PASS)                                         │
        ▼                                                │
  PENDING_APPROVAL ◄───────────────────────────────────── ┘
      │       │
      ▼       ▼
  MITIGATING  ESCALATED
      │    ╲       │
      │     ▼      │
      └──► RESOLVED ◄──────────────────────────────────┘
                │
                ▼
             CLOSED  (terminal — no outbound transitions)
```

The lifecycle is enforced by `backend/memory/lifecycle.py` which raises
`InvalidTransitionError` on any attempt to make an undocumented jump.

---

### State Management

All agents share a single `IncidentState` Pydantic model stored in ADK
session state.  Each agent reads only its required fields and writes only
its owned section:

| Agent                 | Reads                              | Writes                                   |
|-----------------------|------------------------------------|------------------------------------------|
| `IntakeAgent`         | raw alert input                    | `incident_id`, `raw_alert`, `status=NEW` |
| `TriageAgent`         | `raw_alert`, `diagnostics`         | `diagnostics.severity`, `blast_radius`   |
| `LogAnalyzerAgent`    | `diagnostics.affected_services`    | `diagnostics.log_findings`               |
| `RootCauseAgent`      | `diagnostics.log_findings`         | `diagnostics.root_cause`, `confidence`   |
| `EvaluatorAgent`      | `diagnostics.*`                    | `diagnostics.evaluator_verdict`          |
| `RecoveryPlannerAgent`| `diagnostics.root_cause`           | `recommendations.*`                      |
| `EscalationAgent`     | `diagnostics`, `recommendations`   | `escalation.*`                           |
| `ReportGeneratorAgent`| all sections                       | `report`, `stakeholder_update`           |

**Phase 4 fields added to `IncidentState`:**
- `schema_version` — integer, bumped on breaking schema changes
- `title`, `description`, `environment` — richer incident context
- `created_at`, `updated_at` — auto-populated ISO-8601 timestamps
- `assigned_team`, `recovery_status`, `verification_status`, `report_status`, `escalation_status`
- `metadata` — free-form dict for extensibility without schema changes

---

### Timeline Structure

Every agent appends a `TimelineEntry` to `IncidentState.timeline`.  Entries
are ordered by insertion (append-only) and contain:

```python
class TimelineEntry(BaseModel):
    timestamp: str          # ISO-8601 UTC
    agent_name: str         # e.g. "RootCauseAgent"
    event_type: EventType   # Enum: ROOT_CAUSE_FOUND, STATUS_CHANGED, ...
    action: str             # Short verb: "rca_completed"
    summary: str            # Human-readable description
    confidence: int         # 0–100, clamped
    tools_used: list[str]   # MCP tools called during this step
    duration_ms: int        # Wall-clock duration
    entry_status: str       # SUCCESS | FAILURE | SKIPPED
```

Legacy fields (`agent`, `message`) are preserved for backward compatibility
with existing agent instructions.

Use `backend/utils/incident_utils.py::format_timeline()` to render the
full timeline as a human-readable string for reports and demos.

---

### Persistence Architecture

```
  IncidentStore (ABC)          ← agents depend on this interface only
       │
       ├── JsonIncidentStore   ← current implementation (file-based)
       │     active/    INC-AABBCCDD.json
       │     archived/  INC-XXYYZZ.json
       │
       └── (Future) RedisStore / FirestoreStore / PostgresStore
             → one-line DI wiring change, zero agent changes
```

**Supported operations:**
- `save(incident)` — atomic write (`.tmp` → rename)
- `load(incident_id)` — raises `IncidentNotFoundError` if missing
- `update(incident)` — overwrites existing record
- `list_incidents()` — returns all active IDs
- `archive(incident_id)` — moves to `archived/` subdirectory
- `delete(incident_id)` — permanent deletion (silent if missing)
- `exists(incident_id)` — cheap file-existence check (no deserialization)

Every JSON file includes `schema_version` at the top level for future
migration tooling.

---

### Session Memory

```
  MemoryStore (ABC)            ← dependency inversion interface
       │
       └── InMemoryStore       ← thread-safe dict (dev/test)
             │
             └── (Future) RedisStore / FirestoreStore
```

Each session stores:
- `IncidentState` — current incident snapshot
- `agent_outputs` — keyed by agent name
- `tool_call_history` — ordered MCP tool calls
- `decision_log` — timestamped decision strings

Multiple incidents run in separate sessions and are fully isolated.

---

### Running Phase 4 Tests

```bash
# Phase 4 new test files only
uv run python -m pytest tests/test_lifecycle.py tests/test_memory.py tests/test_persistence.py tests/test_utils.py -v

# Full test suite (all phases)
uv run python -m pytest tests/ -v
```

**Test breakdown:**

| File                    | Tests | Coverage                                      |
|-------------------------|-------|-----------------------------------------------|
| `test_agents.py`        | 77    | All 8 agents, coordinator, state, mock MCP    |
| `test_lifecycle.py`     | 37    | Valid/invalid transitions, side effects       |
| `test_memory.py`        | 30    | InMemoryStore CRUD, isolation, concurrency    |
| `test_persistence.py`   | 34    | JSON store, schema_version, atomic writes     |
| `test_utils.py`         | 55    | ID gen, timestamps, confidence, event bus     |
| `test_mcp.py`           | 62    | MCP server tools and resources                |
| `test_security.py`      | 1     | Security module imports                       |
| **Total**               | **296+** | —                                           |

---

### New Modules (Phase 4)

```
backend/
  memory/
    case_file.py        # Extended IncidentState (schema_version, timestamps, etc.)
    lifecycle.py        # State machine: transition(), can_transition(), VALID_TRANSITIONS
    session.py          # MemoryStore (ABC) + InMemoryStore + SessionContext
  persistence/
    base.py             # IncidentStore (ABC) + IncidentNotFoundError
    json_store.py       # JsonIncidentStore (atomic writes, archive, exists)
  utils/
    incident_utils.py   # generate_incident_id, aggregate_confidence, format_timeline, …
  events/
    event_bus.py        # publish_event, subscribe, unsubscribe (WebSocket-ready)
```

---

## Phase 5: Application Gateway & Real-Time Orchestration

### API Architecture

```
  Client (e.g. React Dashboard)
    │
    ├─── [HTTP Requests] ───► FastAPI Gateway (Uvicorn / 8000)
    │                          │
    │                          ├── CORS, Payload limits, Secure headers
    │                          ├── Lifespan DI: JsonIncidentStore, ADKWorkflowOrchestrator
    │                          │
    │                          └── REST Endpoints: GET/POST /api/incidents
    │                                │
    │                                └── [Background Task] ──► ADK Workflow Orchestrator
    │                                                            │
    │                                                            ├── Runner.run_async()
    │                                                            ├── SequentialAgent Coordinator
    │                                                            ├── InMemorySessionService
    │                                                            └── [State Sync] ──► JSON Persistence
    │
    └─── [WebSockets] ──────► /ws/incidents/{incident_id}
                               │
                               └── ConnectionManager (heartbeats, channels, bridge)
                                     ▲
                                     └── [Bridged Task] ─── Event Bus (subscribe)
```

---

### Request & Event Streaming Flow

1. **Intake request:** Client issues `POST /api/incidents`.
2. **Persistence:** The gateway generates `incident_id`, initializes the `IncidentState` as `NEW`, saves it to JSON file persistence, and returns the metadata instantly (non-blocking).
3. **Background launch:** FastAPI queues the `ADKWorkflowOrchestrator` execution.
4. **Execution:** The orchestrator invokes the ADK `Runner` running the `coordinator` agent.
5. **Real-time broadcast:**
   - As sub-agents run (Intake, Triage, Log Analyzer, RCA, etc.), they yield events.
   - The orchestrator fetches intermediate session states, synchronizes them to the JSON file store, and publishes progress to the Event Bus.
   - The Event Bus bridge task intercepts the published events and broadcasts them via WebSockets to all clients connected to `/ws/incidents/{incident_id}`.
6. **Graceful Completion:** The workflow completes, report details are generated and saved, final status is updated (e.g. `RESOLVED`), and the websocket channel is updated.

---

### REST API Endpoint Documentation

#### 1. Create Incident
- **URL:** `/api/incidents`
- **Method:** `POST`
- **Request Body:**
```json
{
  "title": "Database degradation",
  "description": "DB connection pool size critical",
  "environment": "staging",
  "raw_alert": {
    "name": "DatabaseDegradation",
    "service": "checkout-db",
    "severity": "P1"
  }
}
```
- **Response (201 Created):**
```json
{
  "incident_id": "INC-CD2523DE",
  "title": "Database degradation",
  "description": "DB connection pool size critical",
  "status": "NEW",
  "severity": "P1",
  "environment": "staging",
  "assigned_team": "",
  "recovery_status": "",
  "verification_status": "",
  "report_status": "",
  "escalation_status": "",
  "created_at": "2026-06-27T10:22:54.495411+00:00",
  "updated_at": "2026-06-27T10:22:54.495411+00:00",
  "summary": "",
  "confidence": 0,
  "timeline": [
    {
      "timestamp": "2026-06-27T10:22:54.495411+00:00",
      "agent_name": "system",
      "event_type": "INCIDENT_CREATED",
      "action": "incident_created",
      "summary": "Incident registered via API. Severity: P1",
      "confidence": 0,
      "tools_used": [],
      "duration_ms": 0,
      "entry_status": "SUCCESS"
    }
  ]
}
```

#### 2. List Incidents
- **URL:** `/api/incidents`
- **Method:** `GET`
- **Response (200 OK):** A JSON array of `IncidentResponse` objects.

#### 3. Get Incident Details
- **URL:** `/api/incidents/{incident_id}`
- **Method:** `GET`
- **Response (200 OK):** Detail representation matching the `IncidentResponse` model.

#### 4. Get Incident Timeline
- **URL:** `/api/incidents/{incident_id}/timeline`
- **Method:** `GET`
- **Response (200 OK):** A list of event timeline log DTOs.

#### 5. Get Incident Post-Mortem Report
- **URL:** `/api/incidents/{incident_id}/report`
- **Method:** `GET`
- **Response (200 OK):**
```json
{
  "incident_id": "INC-CD2523DE",
  "report": "Full Markdown Incident Post-Mortem Report ...",
  "stakeholder_update": "Non-technical executive update text...",
  "generated_at": "2026-06-27T10:25:00.123456+00:00"
}
```

#### 6. Health & Readiness Checks
- **Health:** `/health` (also `/api/health`) — Gateway status.
- **Readiness:** `/ready` (also `/api/ready`) — Downstream database/persistence connectivity check.

---

### WebSocket Endpoint Documentation

- **URL:** `/ws/incidents/{incident_id}`
- **Protocol:** `WS` / `WSS`
- **Channel Behavior:** Broadcasts state syncs and event logs as they happen during agent execution:
```json
{
  "event_type": "STATUS_CHANGED",
  "incident_id": "INC-CD2523DE",
  "payload": {
    "previous": "NEW",
    "new": "TRIAGED"
  },
  "timestamp": "2026-06-27T10:23:00.123456+00:00"
}
```
Supports client keep-alive pings (`{"type": "ping"}`) and client disconnections.

---

### Running Phase 5 tests

```bash
# Run new API gateway & WebSocket tests only
uv run python -m pytest tests/test_api.py -v

# Run the complete test suite (all phases)
uv run python -m pytest tests/ -v
```

---

### New Modules (Phase 5)

```
backend/
  config.py               # Centralized configuration (timeouts, paths, keys)
  api/
    __init__.py           # Exports the FastAPI app
    dto.py                # Request and Response schemas (Pydantic DTOs)
    routes.py             # REST routes with FastAPI DI
    websocket.py          # WebSocket ConnectionManager with Heartbeats
    main.py               # Main entrypoint, Lifespan, custom Logging/Security middlewares
  services/
    orchestrator.py       # ADKWorkflowOrchestrator: runner bridge + error escalation
```
