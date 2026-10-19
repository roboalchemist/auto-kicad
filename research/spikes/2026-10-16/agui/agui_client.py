"""Minimal AG-UI client: POST RunAgentInput, capture raw SSE, summarize, and reduce events into messages/state
the way an AG-UI frontend (e.g. @ag-ui/client under CopilotKit) would."""

from __future__ import annotations

import copy
import json
import uuid
from collections import Counter
from pathlib import Path

import httpx


def post_run(url: str, run_input: dict, out_path: Path, timeout: float = 240) -> tuple[int, list[dict]]:
    events: list[dict] = []
    raw_lines: list[str] = []
    with httpx.Client(timeout=timeout) as client:
        with client.stream(
            'POST', url, json=run_input, headers={'Accept': 'text/event-stream', 'Content-Type': 'application/json'}
        ) as resp:
            status = resp.status_code
            for line in resp.iter_lines():
                raw_lines.append(line)
                if line.startswith('data:'):
                    data = line[5:].strip()
                    try:
                        events.append(json.loads(data))
                    except json.JSONDecodeError:
                        events.append({'type': '__UNPARSEABLE__', 'raw': data[:300]})
    out_path.write_text('\n'.join(raw_lines) + '\n')
    return status, events


def sequence(events: list[dict]) -> str:
    seq: list[list] = []
    for e in events:
        t = e.get('type')
        if t == 'CUSTOM':
            t = f"CUSTOM({e.get('name')})"
        if seq and seq[-1][0] == t:
            seq[-1][1] += 1
        else:
            seq.append([t, 1])
    return ' → '.join(f'{t}×{n}' if n > 1 else t for t, n in seq)


def counts(events: list[dict]) -> dict[str, int]:
    return dict(Counter(e.get('type') for e in events))


def _apply_patch(doc, ops):
    for op in ops:
        parts = [p.replace('~1', '/').replace('~0', '~') for p in op['path'].split('/')[1:]]
        target = doc
        for p in parts[:-1]:
            target = target[int(p)] if isinstance(target, list) else target[p]
        key = parts[-1]
        if op['op'] in ('add', 'replace'):
            if isinstance(target, list):
                target.insert(len(target) if key == '-' else int(key), op['value'])
            else:
                target[key] = op['value']
        elif op['op'] == 'remove':
            del target[int(key) if isinstance(target, list) else key]
        else:
            raise ValueError(f'unsupported patch op {op}')
    return doc


class Reducer:
    """Applies AG-UI events to a message list + state, mirroring the client-side event reducer."""

    def __init__(self, messages: list[dict] | None = None, state: dict | None = None):
        self.messages = copy.deepcopy(messages or [])
        self.state = copy.deepcopy(state) if state is not None else {}
        self.outcome = None
        self.run_error = None
        self.custom: list[dict] = []
        self.state_events: list[dict] = []
        self.run_text: list[str] = []
        self.run_reasoning: list[str] = []
        self.run_tool_calls: list[dict] = []
        self.run_tool_results: list[dict] = []
        self.snapshot_replaced = False

    def _get(self, mid):
        return next((m for m in self.messages if m.get('id') == mid), None)

    def _tool_call(self, tcid):
        for m in self.messages:
            for tc in m.get('toolCalls') or []:
                if tc['id'] == tcid:
                    return tc
        return None

    def apply(self, e: dict) -> None:
        t = e.get('type')
        if t == 'TEXT_MESSAGE_START':
            if not self._get(e['messageId']):
                self.messages.append({'id': e['messageId'], 'role': e.get('role') or 'assistant', 'content': ''})
        elif t == 'TEXT_MESSAGE_CONTENT':
            m = self._get(e['messageId'])
            if m is None:
                m = {'id': e['messageId'], 'role': 'assistant', 'content': ''}
                self.messages.append(m)
            m['content'] = (m.get('content') or '') + e['delta']
            self.run_text.append(e['delta'])
        elif t == 'TOOL_CALL_START':
            pid = e.get('parentMessageId') or f'auto-{uuid.uuid4()}'
            m = self._get(pid)
            if m is None:
                m = {'id': pid, 'role': 'assistant', 'content': ''}
                self.messages.append(m)
            tc = {'id': e['toolCallId'], 'type': 'function', 'function': {'name': e['toolCallName'], 'arguments': ''}}
            m.setdefault('toolCalls', []).append(tc)
            self.run_tool_calls.append(tc)
        elif t == 'TOOL_CALL_ARGS':
            tc = self._tool_call(e['toolCallId'])
            if tc is not None:
                tc['function']['arguments'] += e['delta']
        elif t == 'TOOL_CALL_RESULT':
            msg = {'id': e['messageId'], 'role': 'tool', 'toolCallId': e['toolCallId'], 'content': e['content']}
            existing = self._get(e['messageId'])
            if existing:
                existing.update(msg)
            else:
                self.messages.append(msg)
            self.run_tool_results.append(msg)
        elif t == 'REASONING_MESSAGE_START':
            if not self._get(e['messageId']):
                self.messages.append({'id': e['messageId'], 'role': 'reasoning', 'content': ''})
        elif t == 'REASONING_MESSAGE_CONTENT':
            m = self._get(e['messageId'])
            if m is None:
                m = {'id': e['messageId'], 'role': 'reasoning', 'content': ''}
                self.messages.append(m)
            m['content'] += e['delta']
            self.run_reasoning.append(e['delta'])
        elif t == 'REASONING_ENCRYPTED_VALUE':
            if e.get('subtype') == 'tool-call':
                tc = self._tool_call(e['entityId'])
                if tc is not None:
                    tc['encryptedValue'] = e['encryptedValue']
            else:
                m = self._get(e['entityId'])
                if m is None:
                    m = {'id': e['entityId'], 'role': 'reasoning', 'content': ''}
                    self.messages.append(m)
                m['encryptedValue'] = e['encryptedValue']
        elif t == 'MESSAGES_SNAPSHOT':
            self.messages = copy.deepcopy(e['messages'])
            self.snapshot_replaced = True
        elif t == 'STATE_SNAPSHOT':
            self.state = copy.deepcopy(e['snapshot'])
            self.state_events.append({'type': t, 'keys': sorted(e['snapshot'].keys()) if isinstance(e['snapshot'], dict) else None})
        elif t == 'STATE_DELTA':
            _apply_patch(self.state, e['delta'])
            self.state_events.append({'type': t, 'delta': e['delta']})
        elif t == 'RUN_FINISHED':
            self.outcome = e.get('outcome')
        elif t == 'RUN_ERROR':
            self.run_error = e
        elif t == 'CUSTOM':
            self.custom.append({'name': e.get('name'), 'value': e.get('value')})


def run_input(thread_id: str, messages: list[dict], state: dict, tools: list[dict] | None = None, **extra) -> dict:
    body = {
        'threadId': thread_id,
        'runId': f'run-{uuid.uuid4().hex[:8]}',
        'state': state,
        'messages': messages,
        'tools': tools or [],
        'context': [],
        'forwardedProps': {},
    }
    body.update(extra)
    return body


def short(value, n: int = 220) -> str:
    s = value if isinstance(value, str) else json.dumps(value)
    return s if len(s) <= n else s[:n] + f'…(+{len(s) - n} chars)'
