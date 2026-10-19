"""Deterministic stand-in for the LLM (`PAI_MODEL=scripted`).

It makes the same tool calls the real model makes for the two e2e prompts, so the whole
browser → CopilotRuntime → AG-UI → Pydantic AI path can be exercised without API spend.
It cannot see images; use the real model to check that renders reach the model.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator

from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, DeltaToolCall, FunctionModel

Delta = str | dict[int, DeltaThinkingPart | DeltaToolCall]


def _last_prompt(messages: list[ModelMessage]) -> tuple[int, str]:
    for i in range(len(messages) - 1, -1, -1):
        message = messages[i]
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    content = part.content
                    text = content if isinstance(content, str) else ' '.join(c for c in content if isinstance(c, str))
                    return i, text
    return 0, ''


def _returned_tools(messages: list[ModelMessage]) -> set[str]:
    return {
        part.tool_name
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    }


async def _text(text: str) -> AsyncIterator[str]:
    for word in re.findall(r'\S+\s*', text):
        await asyncio.sleep(0.03)
        yield word


def _call(index: int, name: str, args: dict) -> dict[int, DeltaToolCall]:
    return {index: DeltaToolCall(name=name, json_args=json.dumps(args), tool_call_id=f'call_{uuid.uuid4().hex[:12]}')}


async def scripted_stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Delta]:
    start, prompt = _last_prompt(messages)
    done = _returned_tools(messages[start:])

    if 'focus' in prompt.lower():
        ref_match = re.search(r'\b([A-Z]{1,3}\d+)\b', prompt)
        ref = ref_match.group(1) if ref_match else 'U1'
        if 'focus_viewer' not in done:
            yield _call(0, 'focus_viewer', {'ref': ref})
        else:
            async for chunk in _text(f'The viewer is now focused on {ref}.'):
                yield chunk
        return

    if 'render_board' not in done:
        yield {0: DeltaThinkingPart(content='The user wants a top render first, then a commit. ')}
        yield {0: DeltaThinkingPart(content='I will render, describe it, and request the commit.')}
        yield {0: DeltaThinkingPart(signature='scripted-signature')}
        async for chunk in _text('Rendering the top view first.'):
            yield chunk
        yield _call(1, 'render_board', {'view': 'top'})
    elif 'commit_design' not in done:
        message_match = re.search(r"message\s+'([^']+)'", prompt)
        async for chunk in _text('The render shows the board label and the check code. Committing now.'):
            yield chunk
        yield _call(0, 'commit_design', {'message': message_match.group(1) if message_match else 'update'})
    else:
        async for chunk in _text('Done: the design is committed.'):
            yield chunk


def scripted_model() -> FunctionModel:
    return FunctionModel(stream_function=scripted_stream, model_name='scripted')
