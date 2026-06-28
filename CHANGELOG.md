# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-28

### Added
- **Multi-Agent Orchestrator:** Implemented cooperative multi-agent system powered by Google ADK featuring 8 specialized SRE agents.
- **Vibrant SRE Dashboard:** Premium React/TypeScript dashboard with widgets, live incident timeline, manual approval gates, and a simulated alert fire panel.
- **Secured API Gateway:** FastAPI application gateway incorporating IP rate limiting, prompt injection checkers, a hash-chained audit logger, and WebSocket security boundaries.
- **MCP Servers Integration:** Separated agent execution from target infrastructures using standard Model Context Protocol (MCP) servers (Monitoring MCP and Incident MCP).
- **Comprehensive Documentation:** Programmatically generated vector-quality system architecture, agent workflow, and sequence diagrams.

### Fixed
- **CI Workflow Pinning:** Resolved setup-uv Action failures by pinning version tags to stable release `@v8.2.0` (immutable tags).
- **Backend Test Suite Failures:** Standardized mock incident ID schemas, resolved rate limiter conflicts between quick test suites, and isolated database directories.

## [0.0.1] - 2026-06-20
- Initial bootstrap of backend service structure, dummy agent executors, and persistence layer setup.
