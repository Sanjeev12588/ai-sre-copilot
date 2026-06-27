"""Unit tests for MCP Server tools and resources."""


def test_mcp_servers_import():
    """Verify that MCP server modules can be imported without errors."""
    from backend.mcp_servers import incident_server, monitoring_server

    assert monitoring_server is not None
    assert incident_server is not None
