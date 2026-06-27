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
