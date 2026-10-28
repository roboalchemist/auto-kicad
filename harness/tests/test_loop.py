"""Goal-loop reliability: the failures that used to abort a run must not end it.

Every test here corresponds to a real abort seen in the live UI:

- "Model token limit (16000) exceeded before any response was generated"
- "Tool 'schematic_summary' exceeded max retries count of 5"
- a tool call that never returns because the thread pool or a library load stalled
"""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from kicad_harness.server import stream_with_token_retry

# Reuse the real-services fixtures and scripted model from the phase tests.
from kicad_harness.agent.agent import build_agent
from tests.test_agent import Script
from tests.test_phase import deps_for, new_project, services  # noqa: F401  (pytest fixtures)


def _adapter(behaviour):
    """A fake adapter whose behaviour is a list of 'raise-token' | 'yield' steps per attempt."""
    seen: list[int] = []

    def make_stream(budget: int):
        seen.append(budget)

        async def gen():
            step = behaviour[min(len(seen) - 1, len(behaviour) - 1)]
            if step == "raise-token":
                raise UnexpectedModelBehavior(
                    f"Model token limit ({budget}) exceeded before any response was generated."
                )
            if step == "raise-other":
                raise UnexpectedModelBehavior("something unrelated went wrong")
            yield {"type": "ok"}

        return gen()

    return make_stream, seen


async def test_token_limit_retries_with_a_bigger_budget():
    make_stream, seen = _adapter(["raise-token", "yield"])
    events = [e async for e in stream_with_token_retry(make_stream, initial_budget=32000)]
    assert events == [{"type": "ok"}]
    assert seen == [32000, 64000], seen


async def test_token_limit_retry_is_capped():
    """Persistent token-limit failures must surface, not loop forever."""
    make_stream, seen = _adapter(["raise-token", "raise-token", "raise-token", "raise-token"])
    with pytest.raises(UnexpectedModelBehavior, match="token limit"):
        async for _ in stream_with_token_retry(make_stream, initial_budget=32000, max_budget=64000):
            pass
    assert seen == [32000, 64000], f"should stop once at the cap, not keep retrying: {seen}"


async def test_unrelated_model_errors_are_not_retried():
    make_stream, seen = _adapter(["raise-other", "yield"])
    with pytest.raises(UnexpectedModelBehavior, match="unrelated"):
        async for _ in stream_with_token_retry(make_stream, initial_budget=32000):
            pass
    assert seen == [32000], "a non-token error must not be retried"


async def test_successful_stream_passes_events_through():
    make_stream, seen = _adapter(["yield"])
    events = [e async for e in stream_with_token_retry(make_stream, initial_budget=48000)]
    assert events == [{"type": "ok"}]
    assert seen == [48000]


# ---------------------------------------------------------------------------------------------
# Tool refusals must not consume the retry budget


async def test_board_tools_refuse_with_data_not_retries(services, new_project):
    """Calling board tools repeatedly in the schematic phase must not kill the run.

    Each refusal used to raise ModelRetry; five of them ended the run with
    "exceeded max retries count of 5".
    """
    name, _ws = new_project
    calls = [("query", {"kind": "footprint"})] * 3
    calls += [("measure", {"a": "R1.1", "b": "R1.2"})] * 3
    calls += [("list_feedback", {}), ("check", {})]
    script = Script([calls, "done"])
    agent = build_agent()
    deps = deps_for(services, name)
    with agent.override(model=script.model()):
        result = await agent.run("poke board tools", deps=deps)

    assert result.output == "done", "the run must survive 8 board-tool refusals"
    returns = [
        p for m in result.all_messages() for p in getattr(m, "parts", []) if type(p).__name__ == "ToolReturnPart"
    ]
    assert len(returns) == 8, [getattr(r, "tool_name", "") for r in returns]
    for r in returns:
        assert isinstance(r.content, dict), r.content
        assert r.content.get("ok") is False, r.content
        assert "schematic phase" in r.content.get("error", ""), r.content


async def test_board_laid_out_passes_once_the_board_exists(services, new_project):
    """Regression: a goal written in the schematic phase reported [board] unmet forever.

    The board_laid_out term was only supplied while still in the schematic phase, so after the
    handoff the criterion could never pass and the loop finished as "Goal NOT MET" despite
    having produced a board.
    """
    from kicad_harness.agent import goal as goals

    name, ws = new_project
    ws.set_goal(
        {
            "summary": "wired, clean, laid out",
            "criteria": [
                {"id": "wired", "type": "unconnected_pins", "max": 0},
                {"id": "board", "type": "board_laid_out", "min": 1},
            ],
        }
    )
    ws.set_phase("board")
    ws.board_path.write_bytes(
        __import__("pathlib").Path(__file__).parent.joinpath("fixtures", "blinker.kicad_pcb").read_bytes()
    )

    run_deps = deps_for(services, name)
    from kicad_harness.agent.agent import _evaluate

    class Ctx:
        deps = run_deps
        tool_call_id = None
        tool_call_approved = False

    evaluation = await _evaluate(Ctx())
    board = next(c for c in evaluation["criteria"] if c["id"] == "board")
    assert board["passed"] is True, evaluation


async def test_budget_shrinks_when_the_provider_rejects_it():
    """Regression: raising max_tokens hit a 402 "can only afford 25411 tokens".

    A fixed large budget can exceed the account's credit limit, so the retry must also be able
    to *reduce* the budget, not just raise it.
    """
    seen: list[int] = []

    def make_stream(budget: int):
        seen.append(budget)

        async def gen():
            if len(seen) == 1:
                raise RuntimeError(
                    "status_code: 402 ... This request requires more credits, or fewer max_tokens. "
                    "You requested up to 32000 tokens, but can only afford 25411."
                )
            yield {"type": "ok"}

        return gen()

    events = [e async for e in stream_with_token_retry(make_stream, initial_budget=32000)]
    assert events == [{"type": "ok"}]
    assert seen == [32000, 16000], seen


async def test_budget_shrink_is_bounded():
    seen: list[int] = []

    def make_stream(budget: int):
        seen.append(budget)

        async def gen():
            raise RuntimeError("402: fewer max_tokens, can only afford 100")
            yield  # pragma: no cover

        return gen()

    with pytest.raises(RuntimeError, match="can only afford"):
        async for _ in stream_with_token_retry(make_stream, initial_budget=32000, min_budget=4096):
            pass
    assert seen[-1] == 4096 and len(seen) <= 6, seen


def test_next_budget_moves_in_the_right_direction():
    """Budget adaptation: grow when thinking ate it, shrink when the provider refused it."""
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    from kicad_harness.server import next_budget

    exhausted = UnexpectedModelBehavior(
        "Model token limit (16000) exceeded before any response was generated."
    )
    assert next_budget(16000, exhausted) == 32000          # too small -> grow
    assert next_budget(64000, exhausted) is None           # already at the ceiling

    credit = RuntimeError("402: fewer max_tokens, you can only afford 25411 tokens")
    assert next_budget(32000, credit) == 16000             # too large -> shrink
    assert next_budget(4096, credit) is None               # already at the floor

    assert next_budget(16000, RuntimeError("something else broke")) is None
