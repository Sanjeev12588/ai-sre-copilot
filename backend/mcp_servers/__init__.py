"""MCP Servers package.

Exposes two FastMCP servers:
- monitoring_server: Observability data (alerts, metrics, logs, topology)
- incident_server  : Runbook library and incident response actions
"""

from backend.mcp_servers.incident_server import mcp as incident_mcp
from backend.mcp_servers.monitoring_server import mcp as monitoring_mcp

__all__ = ["monitoring_mcp", "incident_mcp"]
