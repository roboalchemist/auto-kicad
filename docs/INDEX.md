# Documentation

Guides, references and research notes. The runnable code lives in
[`harness/`](../harness/) and [`demo/`](../demo/); start with the top-level
[README](../README.md).

## Guides

| Document | What it covers |
|---|---|
| [JLCPCB PCBA guide](guides/JLCPCB_PCBA_GUIDE.md) | File formats, LCSC part numbers, tooling, rotation fixes, testing, ordering |
| [PCBWay PCBA guide](guides/PCBWAY_PCBA_GUIDE.md) | File formats, sourcing modes, fiducials, testing, JLCPCB comparison |
| [KiCad DRC guide](guides/KICAD_DRC_GUIDE.md) | DRC report format and how to interpret it |
| [DRC quick reference](guides/DRC_QUICK_REFERENCE.md) | The checks `demo/drc_rules.py` implements and their limits |
| [KiCad S-expression format](guides/KICAD_FORMAT_QUICK_REF.md) | Board, footprint and netlist file structure |
| [Footprint generators](guides/KICAD_FOOTPRINT_GENERATORS.md) | The KiCad footprint-generation ecosystem and its tradeoffs |
| [KiCad 5 → 8 footprints](guides/KICAD_5_TO_8_FOOTPRINT_CONVERSION.md) | Converting old `(module …)` footprints to the current format |

## Footprint research

| Document | What it covers |
|---|---|
| [Research overview](footprints/README_FOOTPRINT_RESEARCH.md) | Entry point: use-case navigation and tool selection |
| [Quick reference](footprints/FOOTPRINT_QUICK_REFERENCE.md) | Fastest paths, minimal working examples |
| [Tool directory](footprints/FOOTPRINT_TOOLS_DIRECTORY.md) | Catalog of generators, install commands and licenses |
| [Code examples](footprints/FOOTPRINT_CODE_EXAMPLES.md) | Seven runnable generators (SMD, THT, BGA, connectors) |

## Research notes

| Document | What it covers |
|---|---|
| [Research summary](research/RESEARCH_SUMMARY.md) | Findings from surveying KiCad MCP servers and layout tooling |
| [Footprint format findings](research/RESEARCH_FINDINGS_FOOTPRINT_FORMAT.md) | What the format supports and where the sharp edges are |

## Project

- [WORKLOG.md](WORKLOG.md) — session-by-session engineering log, including failures
- [screenshots/](screenshots/) — UI screenshots used in the top-level README
- [harness/README.md](../harness/README.md) — harness setup, CLI and model configuration
- [harness/DESIGN.md](../harness/DESIGN.md) — the harness architecture contract
