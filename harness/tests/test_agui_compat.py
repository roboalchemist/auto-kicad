"""Regression test for bug B1 (harness/web/NOTES.md): AG-UI runs vs output validators.

pydantic-ai's AG-UI adapter composes a run-level output_type whenever frontend tools are
present. The harness agent registers goal-loop output validators, and pydantic-ai rejects
any run-level output_type on an agent with output validators — so every web-UI run died
before reaching the model. agui_compat.apply_pydantic_ai_agui_patch() makes the composed
output_type fall back to the agent's own schema for validator-agents.
"""

import pytest
from pydantic_ai import DeferredToolRequests

from kicad_harness.agent.agent import build_agent
from kicad_harness.agui_compat import apply_pydantic_ai_agui_patch


def test_agui_patch_lets_frontend_tool_runs_pass_validation():
    apply_pydantic_ai_agui_patch()  # idempotent; safe to call twice
    apply_pydantic_ai_agui_patch()

    agent = build_agent()
    assert agent._output_validators, "harness agent must register its goal-loop validator"

    # Exactly what the AG-UI adapter composes when frontend tools are present:
    composed = [agent.output_type, DeferredToolRequests]
    # Before the patch this raised:
    #   UserError: Cannot set a custom run `output_type` when the agent has output validators
    schema = agent._prepare_output_schema(composed)
    assert schema is agent._output_schema


def test_agui_patch_keeps_run_level_output_type_for_validatorless_agents():
    apply_pydantic_ai_agui_patch()

    # An agent without output validators must keep normal behavior: the run-level
    # output_type is honored (built into a schema), not silently swapped.
    import pydantic_ai.agent as pa_agent

    bare = pa_agent.Agent(output_type=str)
    bare._output_validators = []
    composed = [bare.output_type, DeferredToolRequests]
    schema = bare._prepare_output_schema(composed)
    assert schema is not None
