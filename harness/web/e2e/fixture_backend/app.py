"""Fixture backend for the web e2e check: the 2026-10-16 spike agent (research/spikes/2026-10-16/agui/pai_app.py)
served the way the real harness backend will be.

- `POST /agui`: Pydantic AI over AG-UI (`AGUIAdapter`).
- `GET /api/renders/<file>`: the PNGs `render_board` writes, so `state.render_url` loads in the browser.
- `GET /api/health`: readiness probe.

Run: `.venv/bin/uvicorn app:app --port 8100`. `PAI_MODEL` picks the model (default `anthropic:claude-haiku-5-5`);
`PAI_MODEL=scripted` uses a deterministic stand-in that makes the same tool calls without API spend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ag_ui.core import EventType, StateDeltaEvent, StateSnapshotEvent
from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pydantic_ai import Agent, BinaryContent, CustomEvent, RunContext, ToolReturn
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import DeferredToolRequests
from pydantic_ai.ui import StateDeps
from pydantic_ai.ui.ag_ui import AGUIAdapter

from board_png import make_board_png
from scripted_model import scripted_model

HERE = Path(__file__).parent
RENDERS = HERE / 'renders'
TRUTH = HERE / 'results' / 'image_truth.jsonl'
RENDERS.mkdir(exist_ok=True)

MODEL_NAME = os.environ.get('PAI_MODEL', 'anthropic:claude-haiku-5-5')


class DesignState(BaseModel):
    version: int = 1
    last_render: str | None = None
    render_url: str | None = None
    last_commit: str | None = None


@dataclass(kw_only=True)
class RenderProgress(CustomEvent):
    stage: str


def _model_settings() -> ModelSettings | None:
    if not MODEL_NAME.startswith('anthropic:'):
        return None
    return AnthropicModelSettings(
        max_tokens=4096,
        anthropic_thinking={'type': 'adaptive', 'display': 'summarized'},
        anthropic_effort=os.environ.get('PAI_EFFORT', 'medium'),  # type: ignore[typeddict-item]
    )


agent = Agent(
    scripted_model() if MODEL_NAME == 'scripted' else MODEL_NAME,
    deps_type=StateDeps[DesignState],
    output_type=[str, DeferredToolRequests],
    instructions=(
        'You are a PCB design assistant for KiCad boards. Use the tools you are given. '
        'When you render a board, look carefully at the returned image and describe exactly what it shows '
        '(all visible text, shapes and colors). Keep answers brief.'
    ),
    model_settings=_model_settings(),
)


@agent.tool
async def render_board(ctx: RunContext[StateDeps[DesignState]], view: str) -> ToolReturn:
    """Render the current board from a view ('top', 'bottom' or '3d') and return the PNG image."""
    await ctx.emit(RenderProgress(stage=f'rendering {view}'))
    state = ctx.deps.state
    png, _truth = make_board_png(f'board v{state.version} {view}', TRUTH)
    fname = f'v{state.version}_{view}_{ctx.tool_call_id[-8:]}.png'
    (RENDERS / fname).write_bytes(png)
    state.last_render = view
    state.render_url = f'/api/renders/{fname}'
    return ToolReturn(
        # A multimodal return_value goes to the model natively inside the tool_result.
        return_value=[
            f'Rendered the {view} view of board v{state.version}. The image follows.',
            BinaryContent(data=png, media_type='image/png'),
        ],
        # AG-UI events in metadata reach the client right after TOOL_CALL_RESULT.
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


app = FastAPI(title='KiCad harness fixture backend')


@app.post('/agui')
async def run_agent(request: Request) -> Response:
    # Fresh deps per request: dispatch_request writes RunAgentInput.state into deps.state.
    return await AGUIAdapter.dispatch_request(request, agent=agent, deps=StateDeps(DesignState()))


@app.get('/api/health')
async def health() -> dict[str, object]:
    return {'ok': True, 'model': MODEL_NAME}


app.mount('/api/renders', StaticFiles(directory=RENDERS), name='renders')
