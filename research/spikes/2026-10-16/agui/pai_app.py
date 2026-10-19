"""Pydantic AI agent exposed over AG-UI (run: .venv/bin/uvicorn pai_app:app --port 8801)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ag_ui.core import EventType, StateDeltaEvent, StateSnapshotEvent
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from pydantic_ai import Agent, BinaryContent, CustomEvent, RunContext, ToolReturn
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.tools import DeferredToolRequests
from pydantic_ai.ui import StateDeps
from pydantic_ai.ui.ag_ui import AGUIAdapter

from board_png import make_board_png

HERE = Path(__file__).parent
TRUTH = HERE / 'results' / 'pai_image_truth.jsonl'


class DesignState(BaseModel):
    version: int = 1
    last_render: str | None = None
    render_url: str | None = None
    last_commit: str | None = None


@dataclass(kw_only=True)
class RenderProgress(CustomEvent):
    stage: str


agent = Agent(
    os.environ.get('PAI_MODEL', 'anthropic:claude-haiku-5-5'),
    deps_type=StateDeps[DesignState],
    output_type=[str, DeferredToolRequests],
    instructions=(
        'You are a PCB design assistant for KiCad boards. Use the tools you are given. '
        'When you render a board, look carefully at the returned image and describe exactly what it shows '
        '(all visible text, shapes and colors). Keep answers brief.'
    ),
    model_settings=AnthropicModelSettings(
        max_tokens=4096,
        anthropic_thinking={'type': 'adaptive', 'display': 'summarized'},
        anthropic_effort=os.environ.get('PAI_EFFORT', 'medium'),  # type: ignore[typeddict-item]
    ),
)


@agent.tool
async def render_board(ctx: RunContext[StateDeps[DesignState]], view: str) -> ToolReturn:
    """Render the current board from a view ('top', 'bottom' or '3d') and return the PNG image."""
    await ctx.emit(RenderProgress(stage=f'rendering {view}'))
    state = ctx.deps.state
    png, _truth = make_board_png(f'board v{state.version} {view}', TRUTH)
    fname = f'pai_v{state.version}_{view}.png'
    (HERE / 'renders' / fname).write_bytes(png)
    state.last_render = view
    state.render_url = f'/renders/{fname}'
    return ToolReturn(
        # multimodal return_value -> sent to the model natively inside the tool_result
        return_value=[
            f'Rendered the {view} view of board v{state.version}. The image follows.',
            BinaryContent(data=png, media_type='image/png'),
        ],
        # AG-UI events in metadata are forwarded to the client right after TOOL_CALL_RESULT
        metadata=[StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=state.model_dump())],
    )


@agent.tool(requires_approval=True)
async def commit_design(ctx: RunContext[StateDeps[DesignState]], message: str) -> ToolReturn:
    """Commit the current design to version control with the given commit message."""
    state = ctx.deps.state
    state.version += 1
    state.last_commit = message
    return ToolReturn(
        return_value=f'Committed the design as v{state.version} with message {message!r}.',
        metadata=[
            StateDeltaEvent(
                type=EventType.STATE_DELTA,
                delta=[
                    {'op': 'replace', 'path': '/version', 'value': state.version},
                    {'op': 'replace', 'path': '/last_commit', 'value': message},
                ],
            )
        ],
    )


async def run_agent(request: Request) -> Response:
    # fresh deps per request: dispatch_request writes RunAgentInput.state into deps.state
    return await AGUIAdapter.dispatch_request(request, agent=agent, deps=StateDeps(DesignState()))


app = Starlette(routes=[Route('/', run_agent, methods=['POST'])])
