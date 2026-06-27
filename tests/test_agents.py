"""Unit tests for ADK Agents and Workflow Coordinator."""


def test_agents_import():
    """Verify that agent modules can be imported without errors."""
    from backend.agents import coordinator, intake, triage

    assert intake is not None
    assert coordinator is not None
    assert triage is not None
