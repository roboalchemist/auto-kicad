"""LangGraph equivalent exposed over AG-UI (run: .venv-lg/bin/uvicorn lg_app:app --port 8802)."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from fastapi import FastAPI
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command, interrupt

from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
from board_png import make_board_png

HERE = Path(__file__).parent
TRUTH = HERE / 'results' / f"{os.environ.get('TRUTH_TAG', 'lg')}_image_truth.jsonl"
INSTRUCTIONS = (
    'You are a PCB design assistant for KiCad boards. Use the tools you are given. '
    'When you render a board, look carefully at the returned image and describe exactly what it shows '
    '(all visible text, shapes and colors). Keep answers brief.'
)


class DesignState(MessagesState):
    tools: list[Any]  # AG-UI frontend tools, injected by ag-ui-langgraph
    version: int
    last_render: Optional[str]
    render_url: Optional[str]
    last_commit: Optional[str]


@tool
async def render_board(
    view: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Render the current board from a view ('top', 'bottom' or '3d') and return the PNG image."""
    await adispatch_custom_event('render_progress', {'stage': f'rendering {view}'})
    version = state.get('version') or 1
    png, _truth = make_board_png(f'board v{version} {view}', TRUTH)
    fname = f'lg_v{version}_{view}.png'
    (HERE / 'renders' / fname).write_bytes(png)
    content = [
        {'type': 'text', 'text': f'Rendered the {view} view of board v{version}. The image follows.'},
        {'type': 'image', 'base64': base64.b64encode(png).decode(), 'mime_type': 'image/png'},
    ]
    return Command(
        update={
            'messages': [ToolMessage(content=content, tool_call_id=tool_call_id, name='render_board')],
            'last_render': view,
            'render_url': f'/renders/{fname}',
        }
    )


@tool
def commit_design(
    message: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Commit the current design to version control with the given commit message."""
    version = (state.get('version') or 1) + 1
    return Command(
        update={
            'messages': [
                ToolMessage(
                    content=f'Committed the design as v{version} with message {message!r}.',
                    tool_call_id=tool_call_id,
                    name='commit_design',
                )
            ],
            'version': version,
            'last_commit': message,
        }
    )


BACKEND_TOOLS = [render_board, commit_design]
model = ChatAnthropic(
    model=os.environ.get('LG_MODEL', 'claude-haiku-5-5'),
    max_tokens=4096,
    thinking={'type': 'adaptive', 'display': 'summarized'},
    effort=os.environ.get('LG_EFFORT', 'medium'),
    # LG_OUTPUT_VERSION=v1 -> LangChain standard content blocks ({"type": "reasoning"}), which ag-ui-langgraph
    # keeps in MESSAGES_SNAPSHOT; the provider-native default ({"type": "thinking"}) is dropped from snapshots.
    **({'output_version': os.environ['LG_OUTPUT_VERSION']} if os.environ.get('LG_OUTPUT_VERSION') else {}),
)


def _frontend_tools(state: dict) -> list[dict]:
    return [
        {
            'type': 'function',
            'function': {
                'name': t['name'],
                'description': t.get('description', ''),
                'parameters': t.get('parameters') or {'type': 'object', 'properties': {}},
            },
        }
        for t in (state.get('tools') or [])
    ]


async def agent_node(state: DesignState, config: RunnableConfig) -> dict:
    llm = model.bind_tools([*BACKEND_TOOLS, *_frontend_tools(state)])
    response = await llm.ainvoke([SystemMessage(content=INSTRUCTIONS), *state['messages']], config)
    return {'messages': [response]}


def route_after_agent(state: DesignState) -> Literal['tools', 'approve', '__end__']:
    last = state['messages'][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return END
    names = {tc['name'] for tc in last.tool_calls}
    if names & {t['name'] for t in (state.get('tools') or [])}:
        return END  # frontend tool: end the run, the client executes it and sends a ToolMessage back
    if 'commit_design' in names:
        return 'approve'
    return 'tools'


def approve_node(state: DesignState) -> Command[Literal['tools', 'agent']]:
    last = state['messages'][-1]
    call = next(tc for tc in last.tool_calls if tc['name'] == 'commit_design')
    answer = interrupt(
        {
            'reason': 'tool_call',
            'toolCallId': call['id'],
            'message': f"Approve commit_design({json.dumps(call['args'])})?",
            'responseSchema': {
                'type': 'object',
                'properties': {'approved': {'type': 'boolean'}, 'reason': {'type': 'string'}},
                'required': ['approved'],
            },
        }
    )
    if isinstance(answer, dict) and answer.get('approved') is True:
        return Command(goto='tools')
    reason = answer.get('reason') if isinstance(answer, dict) else None
    denial = ToolMessage(
        content=f'User denied the commit. {reason or ""}'.strip(),
        tool_call_id=call['id'],
        name='commit_design',
        status='error',
    )
    return Command(goto='agent', update={'messages': [denial]})


builder = StateGraph(DesignState)
builder.add_node('agent', agent_node)
builder.add_node('approve', approve_node)
builder.add_node('tools', ToolNode(BACKEND_TOOLS))
builder.add_edge(START, 'agent')
builder.add_conditional_edges('agent', route_after_agent, ['tools', 'approve', END])
builder.add_edge('tools', 'agent')
graph = builder.compile(checkpointer=InMemorySaver())

app = FastAPI()
add_langgraph_fastapi_endpoint(
    app,
    LangGraphAgent(
        name='kicad_agent',
        graph=graph,
        # opt in to the standard RUN_FINISHED.outcome=interrupt + RunAgentInput.resume[] path
        emit_interrupt_outcome=os.environ.get('LG_INTERRUPT_OUTCOME', '1') == '1',
        emit_raw_events=os.environ.get('LG_RAW_EVENTS', '1') == '1',
    ),
    '/',
)
