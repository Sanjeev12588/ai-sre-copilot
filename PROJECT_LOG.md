# Project Log — AI SRE Copilot

This log tracks key milestones, problems encountered, technical fixes, and development lessons learned throughout each phase of the project.

---

## Phase 1: Project Foundation

### Completed
* **Directory Restructuring**: Separated the backend and frontend code to root level (`backend/` and `frontend/`) instead of nesting the frontend inside Python's `src/`.
* **Docs Structure**: Set up a comprehensive documentation structure in the `docs/` folder.
* **CI/CD Pipeline**: Configured GitHub Actions CI workflow in `.github/workflows/ci.yml` to automatically lint, format, build, and test the project.
* **Pre-commit Hooks**: Setup `.pre-commit-config.yaml` to run Ruff lints, formats, and basic checks before code is committed.
* **Docker Compose**: Created `docker-compose.yml` for unified backend/frontend local containerized development.
* **Base Stubs and Configurations**: Created stub modules for all planned SRE agents, MCP server, security checkpoint, and FastAPI backend, and verified all basic pytest units and React packages compile/build successfully.

### Problems & Solutions
1. **Nest React App Inside `src/`**: Originally scaffolded React inside `src/frontend`, which would have made Docker builds and separation of concerns complex.
   * **Fix**: Moved it to the root level `frontend/` and renamed `src/` to `backend/`. Updated all import lines in tests and file paths in the Dockerfile and static file server.
2. **FastAPI Static File Routing**: When React was moved, the static files search directory was broken relative to `backend/api/main.py`.
   * **Fix**: Adjusted relative path from `../frontend/dist` to `../../frontend/dist` to scale two folders up to the root level and target the newly created `frontend/dist/`.

### Lessons Learned
* Structuring the project directory cleanly into `backend/` and `frontend/` at the workspace root is a best practice. It simplifies build dependencies, Docker multi-stage pipelines, and standard CI configurations right from Day 1.

---

## Phase 2: MCP Layer

### Completed
* **Mock Enterprise Dataset**: Implemented realistic microservice topology (`topology.json`), alerts (`alerts.json`), metrics (`metrics.json`), logs (`logs.json`), runbooks (`runbooks.json`), and historical incidents (`incidents_history.json`) mapping the database connection pool exhaustion incident.
* **Monitoring MCP Server**: Created `backend/mcp_servers/monitoring_server.py` exposing tools (`get_alerts`, `get_metrics`, `query_logs`), resources (`topology://current`, `incidents://history`), and prompts (`rca-template`).
* **Incident MCP Server**: Created `backend/mcp_servers/incident_server.py` exposing tools (`simulate_runbook_execution`, `escalate_incident`), resources (`runbooks://list`, `runbook://{runbook_id}`), and prompts (`incident-status-update`).
* **API Documentation**: Generated comprehensive documentation for all tools, resources, prompts, and datasets in `docs/api/mcp_reference.md`.
* **Verification**: Created `tests/test_mcp.py` containing 78 unit tests covering all tools, resources, prompts, parameters, validation, and error cases.

### Problems & Solutions
1. **Interactive Git Prompts in Background Tasks**: Pushing to GitHub in background commands can hang if Git prompts for credentials.
   * **Fix**: Used `$env:GIT_TERMINAL_PROMPT=0` to ensure Git fails early or uses cached system credentials rather than hanging the agent task loop.
2. **Parentheses Formatting on Assertions**: The pre-commit `ruff-format` hook failed because multi-line assert statements were formatted differently.
   * **Fix**: Added the reformatted file and re-committed, which successfully passed all pre-commit hooks.

### Lessons Learned
* Testing MCP servers via direct function unit tests is extremely fast and effective compared to launching full stdio servers for basic API and logic validation.
* Keeping strings wrapped at 88 characters ensures compliance with Ruff formatting rules from the start.
