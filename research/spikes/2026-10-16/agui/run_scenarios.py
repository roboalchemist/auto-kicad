"""Drive both scenarios (HITL+image, frontend tool) against an AG-UI endpoint.

usage: python run_scenarios.py {pai|lg} URL [hitl|fe|all]
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from agui_client import Reducer, counts, post_run, run_input, sequence, short

HERE = Path(__file__).parent
STREAMS = HERE / 'streams'
RESULTS = HERE / 'results'

PROMPT_HITL = "Render the top view, tell me what you see, then commit the design with message 'v1'"
PROMPT_FE = 'Focus the viewer on U1'
FOCUS_TOOL = {
    'name': 'focus_viewer',
    'description': 'Frontend tool: pan/zoom the board viewer in the user\'s browser to a component reference designator.',
    'parameters': {
        'type': 'object',
        'properties': {'ref': {'type': 'string', 'description': 'Reference designator, e.g. U1 or R5'}},
        'required': ['ref'],
    },
}
INITIAL_STATE = {'version': 1, 'last_render': None, 'render_url': None, 'last_commit': None}


def do_run(fw: str, name: str, url: str, body: dict):
    path = STREAMS / f'{fw}_{name}.sse'
    status, events = post_run(url, body, path)
    red = Reducer(body['messages'], body.get('state'))
    for e in events:
        red.apply(e)
    rep = {
        'name': name,
        'http_status': status,
        'stream_file': str(path),
        'request_keys': sorted(body.keys()),
        'n_events': len(events),
        'sequence': sequence(events),
        'counts': counts(events),
        'reasoning_text': ''.join(red.run_reasoning),
        'assistant_text': ''.join(red.run_text),
        'tool_calls': [
            {'id': tc['id'], 'name': tc['function']['name'], 'args': tc['function']['arguments']}
            for tc in red.run_tool_calls
        ],
        'tool_results': [
            {
                'toolCallId': r['toolCallId'],
                'content_len': len(r['content']),
                'has_png': ('image/png' in r['content'] or 'iVBOR' in r['content']),
                'content_head': short(r['content'], 260),
            }
            for r in red.run_tool_results
        ],
        'state_events': red.state_events,
        'final_state': {k: v for k, v in (red.state or {}).items() if k not in ('messages',)},
        'state_has_messages_key': isinstance(red.state, dict) and 'messages' in red.state,
        'custom_events': [{'name': c['name'], 'value': short(c['value'], 400)} for c in red.custom],
        'outcome': red.outcome,
        'run_error': red.run_error,
        'messages_after': [
            {k: (short(v, 120) if k in ('content', 'encryptedValue') else v) for k, v in m.items()} for m in red.messages
        ],
    }
    print(f'\n=== {fw}:{name}  HTTP {status}  events={len(events)}')
    print('SEQ:', rep['sequence'])
    print('COUNTS:', rep['counts'])
    if rep['reasoning_text']:
        print('REASONING:', short(rep['reasoning_text'], 400))
    print('TEXT:', short(rep['assistant_text'], 700))
    for tc in rep['tool_calls']:
        print('TOOL_CALL:', tc['name'], tc['args'])
    for tr in rep['tool_results']:
        print('TOOL_RESULT:', tr['toolCallId'], 'len', tr['content_len'], 'png' if tr['has_png'] else '', tr['content_head'][:160])
    for se in rep['state_events']:
        print('STATE_EV:', se)
    print('STATE:', rep['final_state'], '(+messages key)' if rep['state_has_messages_key'] else '')
    for c in rep['custom_events']:
        print('CUSTOM:', c['name'], c['value'][:300])
    print('OUTCOME:', json.dumps(rep['outcome'])[:900] if rep['outcome'] else None)
    if rep['run_error']:
        print('RUN_ERROR:', rep['run_error'])
    return red, rep


def image_check(fw: str, text: str) -> dict:
    truth_file = RESULTS / f'{fw}_image_truth.jsonl'
    if not truth_file.exists():
        return {'truth': None}
    truth = json.loads(truth_file.read_text().strip().splitlines()[-1])
    low = text.lower()
    return {
        'truth': truth,
        'code_mentioned': truth['code'].lower() in low,
        'color_mentioned': truth['color'] in low,
        'shape_mentioned': truth['shape'] in low,
    }


def scenario_hitl(fw: str, url: str, reports: list) -> None:
    thread = f'{fw}-hitl-{uuid.uuid4().hex[:6]}'
    msgs = [{'id': 'u-hitl-1', 'role': 'user', 'content': PROMPT_HITL}]
    red1, rep1 = do_run(fw, '1_render_then_commit', url, run_input(thread, msgs, INITIAL_STATE))
    reports.append(rep1)

    outcome = red1.outcome or {}
    interrupts = outcome.get('interrupts') if outcome.get('type') == 'interrupt' else None
    legacy = [c for c in red1.custom if c['name'] == 'on_interrupt']
    if interrupts:
        resume = [{'interruptId': i['id'], 'status': 'resolved', 'payload': {'approved': True}} for i in interrupts]
        body = run_input(thread, red1.messages, red1.state, resume=resume)
        print('\n>> resuming via RunAgentInput.resume[]:', json.dumps(resume))
    elif legacy:
        body = run_input(thread, red1.messages, red1.state)
        body['forwardedProps'] = {'command': {'resume': {'approved': True}}}
        print('\n>> resuming via legacy forwardedProps.command.resume')
    else:
        print('\n!! no interrupt surfaced; skipping resume')
        return
    red2, rep2 = do_run(fw, '2_resume_approved', url, body)
    reports.append(rep2)
    chk = image_check(fw, rep1['assistant_text'] + '\n' + rep2['assistant_text'])
    print('\nIMAGE CHECK:', chk)
    reports.append({'name': 'image_check', **chk})


def scenario_fe(fw: str, url: str, reports: list) -> None:
    thread = f'{fw}-fe-{uuid.uuid4().hex[:6]}'
    msgs = [{'id': 'u-fe-1', 'role': 'user', 'content': PROMPT_FE}]
    red3, rep3 = do_run(fw, '3_frontend_tool_call', url, run_input(thread, msgs, INITIAL_STATE, tools=[FOCUS_TOOL]))
    reports.append(rep3)
    fe_calls = [tc for tc in red3.run_tool_calls if tc['function']['name'] == 'focus_viewer']
    if not fe_calls:
        print('\n!! agent did not call focus_viewer')
        return
    tool_msgs = []
    for tc in fe_calls:
        args = json.loads(tc['function']['arguments'] or '{}')
        tool_msgs.append(
            {
                'id': f'tool-{uuid.uuid4().hex[:8]}',
                'role': 'tool',
                'toolCallId': tc['id'],
                'content': json.dumps({'ok': True, 'focused': args.get('ref'), 'zoom': '4x', 'visible_parts': ['U1', 'C3', 'R7']}),
            }
        )
    body = run_input(thread, red3.messages + tool_msgs, red3.state, tools=[FOCUS_TOOL])
    print('\n>> sending frontend tool result(s):', [m['content'] for m in tool_msgs])
    _red4, rep4 = do_run(fw, '4_frontend_tool_result', url, body)
    reports.append(rep4)


def main() -> None:
    fw, url = sys.argv[1], sys.argv[2]
    which = sys.argv[3] if len(sys.argv) > 3 else 'all'
    STREAMS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    reports: list = []
    if which in ('hitl', 'all'):
        scenario_hitl(fw, url, reports)
    if which in ('fe', 'all'):
        scenario_fe(fw, url, reports)
    out = RESULTS / f'{fw}_report_{which}.json'
    out.write_text(json.dumps(reports, indent=1, default=str))
    print('\nreport ->', out)


if __name__ == '__main__':
    main()
