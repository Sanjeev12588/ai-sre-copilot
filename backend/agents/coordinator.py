"""Workflow Coordinator.

The top-level orchestrator for the AI SRE Copilot. Routes the incident
through the specialist agents in the correct order, manages state
transitions, and handles the evaluation feedback loop.

The coordinator uses a SequentialAgent that chains:
    intake → triage → log_analysis → root_cause → evaluation
    → (if FAIL: root_cause retry) → recovery_planning → escalation → report

Because ADK SequentialAgent runs sub_agents in list order and each agent
writes ``next_action`` to session state, the Coordinator Agent (LlmAgent)
reads ``next_action`` and issues a ``transfer_to_agent`` call to the
appropriate specialist.
"""

from __future__ import annotations

from google.adk.agents import SequentialAgent

from backend.agents.escalation import escalation_agent
from backend.agents.evaluator import evaluator_agent
from backend.agents.intake import intake_agent
from backend.agents.log_analyzer import log_analyzer_agent
from backend.agents.recovery_planner import recovery_planner_agent
from backend.agents.report_generator import report_generator_agent
from backend.agents.root_cause import root_cause_agent
from backend.agents.triage import triage_agent

# The coordinator chains all specialist agents in sequence.
# Each agent reads from session state (populated by prior agents) and
# writes its outputs + sets next_action before yielding control.
coordinator = SequentialAgent(
    name="sre_copilot_coordinator",
    description=(
        "Orchestrates the full incident response pipeline: "
        "intake → triage → log analysis → root cause → evaluation "
        "→ recovery planning → escalation → report generation."
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
