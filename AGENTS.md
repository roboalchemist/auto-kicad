# Repository guide

Notes for anyone (human or agent) working in this repo. The long-form harness design is in
`harness/DESIGN.md`; usage is in `README.md` and `harness/README.md`.

## Layout

- `harness/` — the agent harness: Python package (`kicad_harness/`), tests, and the React UI
  (`web/`). This is where almost all current work happens.
- `demo/` — the standalone 555 blinker pipeline from before the harness: skidl netlist,
  placement/routing, and `layout.py`, a pure-Python KiCad S-expression library.
- `.claude/rules/`, `.claude/skills/` — PCB design knowledge loaded as agent context.
- `research/` — notes plus public third-party tools/databases as git submodules.
- `data/` — the JLCPCB parts database (Git LFS).

## Two Pythons, not interchangeable

- System `python3` runs `demo/layout.py`, `demo/blinker.py`, `demo/do_layout*.py`.
  `layout.py` uses `str | None`, so KiCad's Python cannot import it.
- KiCad's bundled Python (3.9) runs anything that imports `pcbnew`:
  `demo/drc_rules.py`, `demo/scripts/render_pcb.py`, and `kicad_harness/engine/worker.py`.
  Keep that code 3.9-compatible.

Neither tool is on `PATH` by default:

```bash
export KICAD_PYTHON=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
export KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
```

`pcbnew` prints `assert "traits" failed ... create wxApp` on stderr. It is harmless.

## Harness

```bash
cd harness
.venv/bin/pytest tests -q          # real KiCad, scripted models, no API calls
npm --prefix web run build         # TypeScript + production bundle
```

- Designs live in `$HARNESS_HOME/workspaces` (default `harness/var`) plus a SQLite store.
  `HARNESS_HOME` relocates everything.
- `HARNESS_MODEL` takes any pydantic-ai model string; the provider SDK must be installed
  (`.[openai]`, `.[google]`).
- The web UI is three processes: Python `:8100`, CopilotKit runtime `:8101`, Vite `:5173`.
- `harness/web/NOTES.md` records integration details and known gaps (3D units, pins,
  outline rendering, model catalog, version summaries).

## Demo pipeline (run in this order)

`demo/*.net`, `demo/*.kicad_pcb`, and `demo/*.kicad_pro` are gitignored; regenerate them.

1. `cd demo && python3 blinker.py` — parts DB search, JLC2KiCadLib fetch (network), skidl
   netlist. Run it inside `demo/`; skidl writes its scratch files into the current directory.
2. `python3 demo/do_layout_v2.py` — placement and routing are hard-coded coordinates; there
   is no autorouter in this path. Writes `demo/blinker_routed_v2.kicad_pcb` and
   `demo/render_data_v2.json`, then runs both DRC engines. Exit 1 means a DRC error.
3. `./demo/scripts/render.sh demo/render_data_v2.json demo/blinker_render.png`.

## DRC

Run both engines; they catch different things.

```bash
$KICAD_CLI pcb drc board.kicad_pcb --format json --severity-all --output x-drc.json
$KICAD_PYTHON demo/drc_rules.py demo/render_data_v2.json
```

`kicad-cli` is the authority on copper (shorts, clearance, unconnected, mask bridges).
`drc_rules.py` checks JLCPCB and design-intent rules and cites the `.claude/rules` source
for each violation. Exit 2 means it could not load `pcbnew` or a footprint and checked
nothing.

## Parts database

`data/jlcpcb-components.sqlite3` is a 1.2 GB Git LFS object (~437k parts). Never write to
it. It is in WAL mode, so open it read-only with `immutable=1` (`uri=True` in Python);

```python
sqlite3.connect("file:data/jlcpcb-components.sqlite3?immutable=1", uri=True)
```

`components.lcsc` is an integer without the `C` prefix (C7593 → `7593`), `basic=1` marks a
JLC Basic part, and `components_fts` is empty — search with `LIKE`.

## Rules

`.claude/rules/pcb-*.md` and the matching `reference/*.md` files under
`.claude/skills/pcb-design/` overlap heavily. When editing a rule, update both copies and
`RULE_REFS` in `demo/drc_rules.py`, which cites filenames and section headings.
