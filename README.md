# AI SRE Copilot

AI SRE Copilot is an autonomous incident response assistant that analyzes alerts, triages incidents, investigates logs, diagnoses root causes, recommends simulated remediations, and evaluates findings.

This repository represents **Phase 1: Project Foundation**, establishing the complete production-ready folder structure, configuration files, and build environment.

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
