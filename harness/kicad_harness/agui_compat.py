"""Compatibility patch for pydantic-ai 2.57.0's AG-UI adapter (bug B1 in harness/web/NOTES.md).

When the client supplies frontend tools, the AG-UI adapter composes a run-level
``output_type = [agent.output_type, DeferredToolRequests]``
(pydantic_ai/ui/_adapter.py, in the run-stream path). But the harness agent registers
goal-loop output validators, and pydantic-ai rejects ANY run-level output_type on an
agent with output validators:

    UserError: Cannot set a custom run `output_type` when the agent has output validators

Every web-UI run died ~2 ms in before reaching the model. The composition is redundant
for us anyway: the agent's own output_type is already ``[str, DeferredToolRequests]``,
which is exactly what its validators expect.

The narrow fix: when an agent has output validators, ignore the run-level output_type and
keep the agent's own output schema (the only behavior pydantic-ai permits for such agents).
This matches upstream's own error message semantics; if a future pydantic-ai release stops
composing the output_type (or handles validators), this patch becomes a no-op for those runs.

Import this module once (server.py does it) before serving AG-UI runs.
"""

from __future__ import annotations

import pydantic_ai
from pydantic_ai.agent import Agent

_patched = False


def apply_pydantic_ai_agui_patch() -> None:
    """Guard Agent._prepare_output_schema for validator-agents under AG-UI runs.

    Idempotent. Version-guarded: only patches the known-bad minor (2.57.x); on other
    versions it warns loudly instead of silently no-oping, so a breaking pydantic-ai
    change surfaces in our tests rather than at runtime.
    """
    global _patched
    if _patched:
        return
    version = getattr(pydantic_ai, "__version__", "")
    if not version.startswith("2.57."):
        # Don't patch blindly on an unknown version — but don't crash either.
        # (If upstream fixes the adapter, this is simply unnecessary.)
        import warnings

        warnings.warn(
            f"agui_compat: pydantic-ai {version} is not the known-bad 2.57.x; "
            "the AG-UI output_type/validators patch was NOT applied. If UI runs fail with "
            "'Cannot set a custom run output_type when the agent has output validators', "
            "re-apply this patch for the new internals.",
            stacklevel=2,
        )
        _patched = True
        return

    if not hasattr(Agent, "_prepare_output_schema"):  # pragma: no cover - internal moved
        import warnings

        warnings.warn(
            "agui_compat: Agent._prepare_output_schema not found; the AG-UI "
            "output_type/validators patch was NOT applied.",
            stacklevel=2,
        )
        _patched = True
        return

    _original = Agent._prepare_output_schema

    def _patched(self: Agent, output_type):  # type: ignore[no-untyped-def]
        if output_type is not None and getattr(self, "_output_validators", None):
            # AG-UI frontend tools compose a run output_type, which validator-agents
            # reject. The agent's own schema already includes DeferredToolRequests.
            return self._output_schema
        return _original(self, output_type)

    Agent._prepare_output_schema = _patched  # type: ignore[method-assign]
    _patched = True
