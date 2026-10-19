# Contributing

Thanks for taking a look. This project is a research harness for agent-driven PCB
design, so changes usually fall into one of four buckets: the Python agent/tools,
the KiCad engine, the web UI, or the PCB knowledge base.

## Development setup

Requires macOS with KiCad 10 at `/Applications/KiCad/KiCad.app`, Python 3.12, `uv`,
Node 22+, and Homebrew `cairo`.

```bash
cd harness
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev,openai,google]'
./scripts/fetch_vendor.sh          # Java 25 + Freerouting, needed by the autoroute tests
```

Run the three processes:

```bash
.venv/bin/kicad-harness serve      # FastAPI + agent on :8100
npm --prefix web run runtime       # CopilotKit runtime on :8101
npm --prefix web run dev           # Vite on :5173
```

## Before you open a pull request

```bash
cd harness
.venv/bin/pytest tests -q          # uses KiCad's Python for pcbnew; no API calls
npm --prefix web run build         # TypeScript + Vite production build
```

- Keep `kicad_harness/engine/worker.py` compatible with **Python 3.9** — KiCad ships
  its own interpreter and that file runs under it.
- Board-affecting changes should leave both DRC engines clean:
  `kicad-cli pcb drc` for copper, and `demo/drc_rules.py` for JLCPCB/design-intent
  rules.
- UI changes: the browser walkthroughs in `harness/web/e2e/` are dev scripts, not
  tests, but running `node e2e/agent.mjs` then `node e2e/walk.mjs` is a quick smoke
  test.
- Don't commit generated boards, netlists, `node_modules`, virtualenvs, or the parts
  database (it is tracked with Git LFS).

## Commit messages

Short imperative subject, then a body that explains *why* when the change is not
obvious. If a change touches layout coordinates, say which board and which DRC
result you verified.

## Reporting bugs

Open an issue with the board or design you used, the exact command or UI action, and
the full error output. For security issues, see [SECURITY.md](SECURITY.md).
