# kicad-harness

An agent that edits a KiCad 10 board toward a goal while you watch, chat with it, click parts of the board to critique them, and roll versions back.

- **Headless core** (Python): a Pydantic AI agent with tools over KiCad.
  - Placement, routing (including Freerouting), outline, zones, footprints, nets and silkscreen.
  - Inspection: DRC, measurements, and 2D/3D renders the model looks at.
  - Every edit is a git commit in the design's workspace.
  - A goal loop keeps the agent working until machine-checkable criteria pass.
- **Web UI:** CopilotKit chat plus a live board viewer.
  - Click any pad, track, via, footprint or point to leave a tagged comment with a severity. Comments carry forward to later versions and the agent reads and answers them.
  - Browse, compare, restore and branch versions; each version shows a board thumbnail, an inline
  diff against the previous version, and a few-word LLM note of what changed.
- Switch the session's model from the header (persisted, applied to later runs) and manage several
  projects from the Projects dialog (thumbnails, switching, and creating one from an uploaded
  .kicad_pcb or the demo fixture).
  - Replay any agent run.
  - Front and back 2D views with a KiCad-style dot grid and a bottom-left scale legend, measure mode,
  and an interactive 3D tab (orbit/pan/zoom over the real board model, vias as real holes).

The contracts between the parts are in [DESIGN.md](DESIGN.md); why this stack was chosen is in [../research/agent-harness-2026.md](../research/agent-harness-2026.md).

## Web UI

Three processes (see also [web/NOTES.md](web/NOTES.md)):

```bash
cd harness
.venv/bin/kicad-harness serve        # FastAPI + agent on :8100
npm --prefix web run runtime         # Node CopilotRuntime on :8101
npm --prefix web run dev             # Vite on :5173, proxies /api and /copilotkit
```

Open http://127.0.0.1:5173. The agent needs a real model in the environment before `serve`
(`HARNESS_MODEL` plus the matching API key, e.g. the OpenRouter route documented in the repo `AGENTS.md`).

- The Agent tab has a single composer: it chats when the agent is idle and steers the live run when
  one is active (the placeholder and button label change). "▶ Run goal" starts the goal loop, the
  checkbox enables it, and Supervised turns every destructive tool into an approval card.
- The header's ☾/☀ button switches the app between light and dark (saved in the browser); the board
  canvas always uses the KiCad dark theme.
- The Review tab lists anchored comments; the board's Comment mode is how you create them.
- Versions supports view / compare (diff overlay on the board) / restore / branch.
- Activity replays runs from `/runs/{id}/events`; Goal shows the criteria and their live status.

Scripted browser walkthroughs (dev only, not tests; both print a [shot] line per screenshot):
`node web/e2e/agent.mjs` then `node web/e2e/walk.mjs`. Run the agent one first — the board
walkthrough's view/compare/restore phases need at least two versions. Phase names as args
(e.g. `node web/e2e/walk.mjs measure diff`), screenshots into `web/e2e/screenshots/`.

## Setup

Needs macOS with KiCad 10 at `/Applications/KiCad/KiCad.app`, Homebrew `cairo`, Python 3.12, `uv`, and Node 22+.

```bash
cd harness
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[dev,openai,google]'
./scripts/fetch_vendor.sh          # Java 25 + Freerouting into .vendor/ (for autoroute)
```

### Choosing a model

`HARNESS_MODEL` takes any pydantic-ai model string; the provider's SDK must be installed
(`.[openai]`, `.[google]`). Two routes are verified:

```bash
# Any OpenAI-compatible endpoint, e.g. OpenRouter, needs the openai extra
export OPENAI_API_KEY=sk-or-...
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
export HARNESS_MODEL=openai:anthropic/claude-sonnet-5

# Google directly, needs the google extra
export GEMINI_API_KEY=...
export HARNESS_MODEL=google:gemini-3.1-pro-preview
```

The direct `anthropic:` route needs your own `ANTHROPIC_API_KEY`; the two routes above are the
ones this project was developed against.

Settings come from the environment (see `kicad_harness/config.py`):

| Variable | Default |
|---|---|
| `HARNESS_HOME` (workspaces, database, caches) | `harness/var` |
| `HARNESS_MODEL` | `anthropic:claude-sonnet-5-5` |
| `KICAD_APP` | `/Applications/KiCad/KiCad.app` |

## Headless use

```bash
K=.venv/bin/kicad-harness
$K init blinker --from tests/fixtures/blinker.kicad_pcb --goal examples/goal-led-left.json
$K run blinker                       # agent works until the goal passes (exit 0) or the budget runs out (exit 3)
$K steer blinker "keep R3 on the same side as D1"   # from another terminal, while it runs
$K comment blinker --ref D1 --pad 1 --severity must_fix --tag placement --body "pad too close to the edge"
$K versions blinker
$K threads blinker
$K restore blinker <sha>
```

`run` prints the agent's reasoning, every tool call and result, and each version it commits. Flags:
- `--no-loop` stops after one answer instead of looping until the goal passes.
- `--supervised` asks before destructive tools.
- `--thread ID` continues an earlier conversation.

## Goals

A goal is `goal.json` in the workspace: a summary for the agent, plus criteria the harness checks itself.

| Criterion type | Passes when |
|---|---|
| `drc_errors`, `drc_warnings`, `unconnected` | `max` or fewer |
| `board_size` | outline within `max_w` × `max_h` |
| `edge_clearance` | every pad at least `min_mm` from the edge |
| `max_distance` / `min_distance` | `a` to `b` copper distance within limit (`U1`, `U1.3`, `net:GND`) |
| `within_region` | footprint `ref` entirely inside `region` [x1, y1, x2, y2] |
| `open_threads` | at most `max` open review threads (optionally only some `severities`) |

`budget.max_requests` and `budget.max_minutes` bound a loop. Examples are in `examples/`.

## Tests

```bash
.venv/bin/pytest tests -q          # real KiCad; scripted models, no API calls
```
