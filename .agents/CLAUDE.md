# kicad-claude

Research and development project for AI-driven PCB design using KiCad. Goal: enable Claude Code to design PCBs end-to-end — from component selection through schematic capture, placement, routing, and manufacturing file generation — without requiring the KiCad GUI.

## Project Structure

```
kicad-claude/
├── .agents/
│   ├── CLAUDE.md           # This file
│   ├── commands/
│   │   └── pcb-review.md   # /pcb-review slash command: 12 parallel domain review agents
│   ├── rules/              # 23 PCB design knowledge base rules (auto-loaded as context)
│   └── skills/
│       └── pcb-design/     # Progressive-loading PCB design skill
│           ├── SKILL.md    # Skill index + quick reference
│           └── reference/  # Topic-specific rule files (read-on-demand)
├── data/
│   ├── jlcpcb-components.sqlite3  # 1.2GB JLCPCB parts DB (git-lfs)
│   └── datasheets/         # Component datasheets (PDF)
├── demo/                   # All runnable demo code and outputs
│   ├── blinker.py          # End-to-end pipeline: DB search → library fetch → circuit → PCB
│   ├── layout.py           # BoardLayout class: S-expression PCB manipulation (no pcbnew, 1393 lines)
│   ├── do_layout.py        # First layout demo (v1, simpler routing)
│   ├── do_layout_v2.py     # Improved layout following all PCB rules (current best)
│   ├── drc_rules.py        # Custom DRC engine: 27 checks against JLCPCB rules (881 lines)
│   ├── drc_runner.py       # kicad-cli DRC wrapper with JSON parsing (353 lines)
│   ├── blinker_sklib.py    # Generated skidl library for demo circuit
│   ├── render_data_v2.json # Current board data (8 components, 17 tracks, 2 vias)
│   ├── blinker_routed_v2.kicad_pcb  # Current board layout (generated, gitignored)
│   └── scripts/
│       ├── render_pcb.py   # PCB rendering via pcbnew + cairosvg/Pillow compositing
│       └── render.sh       # KiCad Python auto-detection wrapper
├── reference/              # Reference documents (PDFs, datasheets)
├── research/               # KiCad MCP server analysis + submodules
│   ├── *.md                # Analysis reports for 5 KiCad MCP servers
│   ├── lamaalrajih-kicad-mcp/      # (submodule) Best MCP server — FastMCP, CLI-first
│   ├── seeed-kicad-mcp-server/     # (submodule) Seeed Studio MCP — dual parser strategy
│   ├── mixelpixx-kicad-mcp-server/ # (submodule) Most ambitious — TypeScript + Python
│   ├── finerestaurant-kicad-mcp-python/ # (submodule) Python MCP with protobuf
│   ├── huaqiu-kicad-mcp*/          # (submodule) Huaqiu Electronics MCP
│   └── libs/               # Library generation tools (submodules)
│       ├── kicad-footprint-generator/  # Official KiCad footprint generator (KicadModTree)
│       ├── JLC2KiCad_lib/      # JLCPCB → KiCad symbol/footprint converter
│       ├── easyeda2kicad/      # EasyEDA → KiCad converter
│       ├── skidl/              # Python circuit description language
│       ├── KiPart/             # KiCad symbol generator from CSV/spreadsheets
│       └── pykicad/, kicad-tools/, kicad-symgen/
├── scripts/
│   └── convert_footprint_kicad5_to_8.py  # Batch-convert KiCad 5 → 8 .kicad_mod format
├── test_samples/
│   └── datasheets/         # Component datasheets (e.g., MCP3008.pdf)
├── FOOTPRINT_*.md          # Footprint generation research documents
├── docs/INDEX.md                # Research index (footprint generation docs)
├── docs/WORKLOG.md              # Session-by-session progress log
├── docs/guides/KICAD_DRC_GUIDE.md      # DRC research and reference
├── docs/guides/KICAD_FORMAT_QUICK_REF.md  # KiCad S-expression format reference
├── docs/guides/KICAD_5_TO_8_FOOTPRINT_CONVERSION.md  # Footprint format conversion guide
├── blinker_sklib.py        # ⚠️ Artifact: duplicate of demo/blinker_sklib.py (skidl generated)
└── blinker.erc / blinker.log  # ⚠️ Artifacts: skidl output from root-level runs
```

## Key Libraries & Frameworks

| Library | Version | Purpose | Install |
|---------|---------|---------|---------|
| **skidl** | 2.2.1 ✅ | Python circuit description → KiCad netlist | `pip install skidl` |
| **KicadModTree** | 1.1.2 ✅ | Programmatic footprint generation (.kicad_mod) | `pip install KicadModTree` |
| **JLC2KiCadLib** | 1.2.3 ✅ | JLCPCB LCSC ID → KiCad symbols + footprints | `pip install JLC2KiCadLib` (import as `JLC2KiCadLib`) |
| **pcbnew** | — ✅ | KiCad Python API (board manipulation, SVG export) | Ships with KiCad.app — NOT system Python |
| **cairosvg** | 2.8.2 ✅ | SVG → PNG rasterization for PCB rendering | `pip install cairosvg` |
| **Pillow** | 12.2.0 ✅ | Image compositing for multi-layer PCB renders | `pip install Pillow` |

## Core Code

### `demo/layout.py` — BoardLayout (1393 lines)

The main layout engine. Provides programmatic PCB manipulation via direct S-expression parsing (**no pcbnew dependency** — runs with any Python 3.9+).

**Key methods:**

| Method | Description |
|--------|-------------|
| `BoardLayout.new_board(pcb_path, components, footprint_dir)` | Create a new .kicad_pcb from component list |
| `BoardLayout(pcb_path)` | Load an existing .kicad_pcb for editing |
| `place_component(ref, x_mm, y_mm, rotation)` | Position a component on the board |
| `add_track(net, points, width, layer)` | Add a routed trace |
| `add_via(x, y, net, drill)` | Add a via |
| `set_board_outline(width_mm, height_mm)` | Define rectangular board outline |
| `set_pad_nets(pad_net_map)` | Assign net names to component pads (written for `new_board()` boards) |
| `auto_place_grid(spacing_mm)` | Auto-place components in a grid |
| `get_netlist_connections()` | Extract net → component/pad mapping |
| `run_drc()` | Basic DRC (clearance, shorts) — returns list of violation dicts |
| `placement_stats(netlist)` | Quality metrics: HPWL, congestion, crosstalk, directness |
| `export_render_data(path, footprint_dir)` | Export JSON for pcbnew renderer |
| `list_components()` | List all components with positions |
| `save(output_path)` | Save .kicad_pcb to disk |

**Internal helpers:** `_sexp_parse()`, `_sexp_write()`, `_transform_footprint()`, `_generate_pcb_content()`, `_patch_existing_content()`, `_pad_abs_position()`, `_mst_length()`

**Behavior worth knowing:**
- Nets are registered as `add_track()`, `add_via()`, and `set_pad_nets()` use them; any net name works.
- KiCad stores pad and text angles inside a placed footprint in board orientation, so rotating a footprint rotates those angles too (handled for new and loaded boards).
- `new_board()` writes the KiCad 8 format (numbered nets). Loading accepts KiCad 5–10 boards, including KiCad 10's name-only `(net "VCC")`. Saving a board this module didn't generate only appends the outline, tracks, and vias; boards it generated get their previous tracks/vias replaced.
- A footprint that can't be found under `footprint_dir` becomes a 2-pad placeholder, with a warning.

### `demo/blinker.py` — End-to-End Pipeline Demo

4-step pipeline for the 555 LED blinker circuit:
1. **Search**: Query JLCPCB SQLite DB (`data/jlcpcb-components.sqlite3`) for real parts (NE555, resistors, caps, LED)
2. **Fetch**: Download KiCad symbols/footprints via JLC2KiCad_lib → `demo/libs/`
3. **Wire**: Build 555 astable circuit using skidl → `blinker.net`
4. **Generate**: Create `.kicad_pcb` from netlist via `BoardLayout`

Fallback: hardcoded LCSC IDs (`C7593`, `C17414`, etc.) if DB unavailable.

### `demo/do_layout_v2.py` — Rule-Compliant Layout (Current Best)

Improved layout following all `.agents/rules/pcb-*.md` constraints:
- Signal flow left-to-right, ICs first; C3 bypass cap between U1 pin 8 (VCC) and pin 1 (GND), ~2.6mm from each
- 45-degree routing only (no 90° bends); 0.25mm signals, 0.5mm VCC/GND
- Everything on F.Cu except one B.Cu link from U1.4 (RESET) to VCC: 2 vias. R2 and C1 are rotated 180° so their THRESHOLD pads face U1
- Placement and routing are hand-coded coordinates (no autorouter); reads net connectivity from `demo/blinker.net`, so run `blinker.py` first
- Runs both DRC engines (kicad-cli + `drc_rules.py` via KiCad Python) and exits 1 if either reports an error or can't run
- Current board: 25×20mm, 8 components; kicad-cli 0 errors / 0 warnings, `drc_rules.py` 0 errors / 13 warnings

### `demo/do_layout.py` — First Layout Demo (v1)

Earlier, simpler placement with basic L-shaped routing. Superseded by v2.

### `demo/drc_rules.py` — Custom Python DRC Engine (881 lines)

27 automated checks against JLCPCB manufacturing rules (`.kicad_dru`). Uses pcbnew API for accurate pad/silkscreen bounding box geometry.

**Rule domains and check count:**
- JLCPCB manufacturing (pad/via clearance, track width, hole sizes, annular ring, edge clearance, track crossings)
- Silkscreen (text height/thickness, pad clearance, overlap)
- Routing (90-degree bends, acute angles)
- DFM (tombstoning risk, copper balance, fiducials)
- Power (missing bypass caps, bypass cap distance from IC pin)
- EMC (return via proximity)
- Test/Debug (test points present)
- Mechanical (board edge clearance, corner radii, mounting holes, board size, power connector)

Every violation cites its source rule file and section (e.g., `pcb-dfm.md → Trace & Space`).

**Run:**
```bash
$KICAD_PYTHON demo/drc_rules.py demo/render_data_v2.json
```

Exit codes: 0 = no errors, 1 = DRC errors, 2 = the board couldn't be checked (pcbnew not importable, `footprint_dir` or a footprint missing). It never falls back to guessed pad geometry. Clearance checks use each pad's rotated bounding box and copper layers.

### `demo/drc_runner.py` — kicad-cli DRC Wrapper (353 lines)

Programmatic wrapper around `kicad-cli pcb drc` with structured JSON output. Classes: `KicadDrcRunner`, `DrcViolation`, `DrcViolationItem`, `DrcSeverity`.

**Note:** kicad-cli DRC works on the generated demo board (KiCad 10.0.3) and is the authority on copper shorts and connectivity. Run it alongside `drc_rules.py`, which covers the JLCPCB and design-intent rules.

### `demo/scripts/render_pcb.py` — PCB Renderer

Builds pcbnew BOARD in-memory from `render_data.json`, exports per-layer SVGs, then composites via subprocess to system Python (cairosvg + Pillow). Layer colorization: F.Cu=red, B.Cu=blue, silk=gray, vias=gold.

```bash
./demo/scripts/render.sh demo/render_data_v2.json demo/blinker_render.png
```

### `scripts/convert_footprint_kicad5_to_8.py` — Format Converter

Batch-converts KiCad 5 `(module ...)` footprints to KiCad 8 `(footprint "...")` format.

```bash
# Single file
python scripts/convert_footprint_kicad5_to_8.py input.kicad_mod output.kicad_mod

# Batch
for f in old.pretty/*.kicad_mod; do python scripts/convert_footprint_kicad5_to_8.py "$f"; done
```

## render_data.json Schema

The intermediate format used to pass board data between `layout.py` and `drc_rules.py`/`render_pcb.py`:

```json
{
  "footprint_dir": "libs/footprints",
  "outline": [25.0, 20.0],
  "nets": {"VCC": 1, "GND": 2, "DISCHARGE": 3, ...},
  "components": [
    {"ref": "U1", "footprint": "SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL", "value": "NE555DR", "x": 9, "y": 10, "rotation": 0, "pad_nets": {"1": "GND", "8": "VCC", ...}}
  ],
  "tracks": [
    {"net": "VCC", "points": [[x1, y1], [x2, y2]], "width": 0.5, "layer": "F.Cu"}
  ],
  "vias": [
    {"net": "GND", "x": 5.0, "y": 8.0, "drill": 0.3}
  ]
}
```

`footprint_dir` is relative to the JSON file's directory (absolute paths also work). `outline` is `[width, height]` in mm.

## Design Knowledge Base

### `.agents/rules/` — 23 Rule Files (Auto-Loaded)

Loaded as context for every Claude session in this project:

| Category | Rules |
|----------|-------|
| Process | `pcb-design-process`, `pcb-metrics`, `pcb-autorouter` |
| Layout | `pcb-placement`, `pcb-routing`, `pcb-copper-pours`, `pcb-stackup`, `pcb-mechanical` |
| Signal | `pcb-high-speed`, `pcb-mixed-signal`, `pcb-rf`, `pcb-emc` |
| Components | `pcb-bom-components`, `pcb-bga-fine-pitch`, `pcb-solder-mask-finish` |
| Manufacturing | `pcb-dfm`, `pcb-silkscreen`, `pcb-hdi`, `pcb-test-debug` |
| Reliability | `pcb-thermal`, `pcb-power`, `pcb-reliability`, `pcb-version-control` |

### `.agents/skills/pcb-design/` — Progressive-Loading Skill

Topic-indexed reference docs in `reference/` (read only what's needed per task):

```
reference/
├── design-process.md, placement.md, routing.md, metrics.md, autorouter.md
├── review.md               ← /pcb-review process and 12-domain agent prompts
├── stackup.md, high-speed.md, mixed-signal.md
├── power.md, emc.md, thermal.md, mechanical.md
├── dfm.md, silkscreen.md, copper-pours.md, test-debug.md, bom-components.md, hdi.md
├── reliability/
│   ├── coatings.md, potting-vibration.md, environmental.md
├── bga-fine-pitch/
│   ├── bga-design.md, bga-manufacturing.md
├── rf/
│   ├── rf-fundamentals.md, rf-layout.md
├── solder-mask-finish/
│   ├── solder-mask.md, surface-finish.md
└── version-control/
    ├── git-workflow.md, release-management.md
```

### `.agents/commands/pcb-review.md` — `/pcb-review` Command

Runs a 12-domain parallel design review using background sub-agents:

| Domain | Rule File |
|--------|-----------|
| Placement, Routing, Power, DFM | pcb-placement, pcb-routing, pcb-power, pcb-dfm |
| EMC, Thermal, Silkscreen, Test/Debug | pcb-emc, pcb-thermal, pcb-silkscreen, pcb-test-debug |
| Mechanical, Copper Pours, BOM, Stackup | pcb-mechanical, pcb-copper-pours, pcb-bom-components, pcb-stackup |

## Installation

No package manager — standalone Python scripts, deps installed manually:

```bash
pip install skidl KicadModTree cairosvg Pillow JLC2KiCadLib

# pcbnew — ships with KiCad.app, NOT pip-installable
# KiCad Python path (Python 3.9):
export KICAD_PYTHON="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"

# kicad-cli binary (NOT in PATH by default):
export KICAD_CLI="/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
```

All packages are already installed on this machine (miniconda3 `python3`). JLC2KiCadLib is an editable install of `research/libs/JLC2KiCad_lib` (`pip install -e research/libs/JLC2KiCad_lib`); re-run that after moving or renaming the repo, because it records the absolute path.

## Development Notes

- **No test framework** — validation is `do_layout_v2.py`'s dual DRC (kicad-cli + `drc_rules.py` against `render_data_v2.json`)
- **Two Python environments**:
  - System `python3` (miniconda3) for `layout.py`, `do_layout_v2.py`, `blinker.py` — all pure S-expression, no pcbnew
  - KiCad Python **3.9** (`$KICAD_PYTHON`) for `drc_rules.py`, `render_pcb.py` — needs pcbnew module
- **Python version compat**: KiCad Python 3.9 doesn't support `str | None` union syntax — use `Optional[str]` in files that run under KiCad Python
- **kicad-cli path**: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` — **NOT in PATH** by default (KiCad 10.0.3 here)
- **kicad-cli DRC**: Works on the generated demo board. The tracked footprints in `demo/libs/footprints/` were converted to KiCad 9 format with `pcbnew.FootprintSave()` (commit 75fdc99); fresh JLC2KiCad_lib downloads are KiCad 5 `(module …)` — convert them the same way (or with `scripts/convert_footprint_kicad5_to_8.py`) if kicad-cli rejects a board
- **Run `blinker.py` from `demo/`**: skidl writes `blinker_sklib.py`, `blinker.erc`, and `blinker.log` into the current directory
- **JLC2KiCadLib import**: `from JLC2KiCadLib.JLC2KiCadLib import add_component` (note: `JLC2KiCadLib`, not `JLC2KiCad_lib`)
- **Git LFS**: Used for `data/*.sqlite3` (1.2GB JLCPCB database)
- **Submodules**: Multiple git submodules in `research/libs/` (JLC2KiCad_lib, KiPart, easyeda2kicad, kicad-footprint-generator, etc.) and `research/databases/` — run `git submodule update --init` after clone
- **Generated files gitignored**: `demo/libs/` (downloaded libraries — except `demo/libs/footprints/*.kicad_mod`, which are force-tracked; `git add -f` new ones), `demo/*.net`, `demo/*.kicad_pcb`, `demo/*.kicad_pro`, `*-drc.json`

## Research Findings

### KiCad MCP Servers (5 analyzed, `research/`)
Best candidate: **lamaalrajih/kicad-mcp** — CLI-first (no pcbnew dependency), FastMCP 2.x, modular architecture, most feature-complete. See `research/lamaalrajih-kicad-mcp.md`.

### Component Databases (`research/databases/`)
| Submodule | Purpose |
|-----------|---------|
| `jlcparts/` | JLCPCB parts web app + Python library — builds SQLite from LCSC API |
| `jlcpcb-parts-database/` | Alternative JLCPCB scraper + CSV/SQLite export |
| `jlcpcb-economic-parts/` | Focuses on economic (basic) parts only, CSV/HTML |
| `lcsc-scrape/` | Rust-based LCSC scraper for full catalog |
| `research/KICAD_PYTHON_DRC_RESEARCH.md` | pcbnew Python API DRC patterns |
| `research/INDEX_DRC_RESEARCH.md` | Index of DRC research findings |

### Component Libraries
Primary approach: JLCPCB SQLite DB → JLC2KiCad_lib → KiCad symbols/footprints. Fallback: hardcoded LCSC IDs in `blinker.py`.

### Footprint Generation
Primary tool: **pointhi/kicad-footprint-generator** (KicadModTree + parametric YAML). 5 research docs: `FOOTPRINT_*.md`, `docs/INDEX.md`.

### KiCad Format
- KiCad 8 uses `(footprint ...)`, KiCad 5 uses `(module ...)` — converter at `scripts/convert_footprint_kicad5_to_8.py`
- S-expression format reference: `docs/guides/KICAD_FORMAT_QUICK_REF.md`
- DRC format: `docs/guides/KICAD_DRC_GUIDE.md`, `docs/guides/DRC_QUICK_REFERENCE.md`

## Current State (from docs/WORKLOG.md)

**Demo board**: 555 LED blinker, 2-layer, 25×20mm, 8 components (NE555 SOIC-8, 3 resistors, 2 caps, 1 bypass cap C3, 1 LED — all 0805)

**DRC status (2026-10-16):**
- kicad-cli: 0 errors, 0 warnings, 0 unconnected items
- `drc_rules.py`: 0 errors, 13 warnings: tombstoning risk (4, 0.5mm power vs 0.25mm signal on 0805 pads), U1.4 is 6.9mm from the nearest VCC cap, timing cap C1 is 9.1mm from U1.6, copper balance (2), missing production features (fiducials, test points, connector, corner radii, mounting holes)

**Key known issues:**
- No copper pour — layout.py can't create zones yet, hence the copper balance warnings
- SOIC-8 pin routing has inherent 3W rule violations at 1.27mm pitch
- Production features (fiducials, test points, mounting holes) not implemented — prototype board only
