"""ADK Agents package.

Exports the root_agent for ADK CLI discovery and the coordinator
for use within the FastAPI backend.
"""

from backend.agents.agent import root_agent
from backend.agents.coordinator import coordinator

__all__ = ["root_agent", "coordinator"]
