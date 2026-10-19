# Seeed Studio KiCad MCP Server - Analysis Report

**Repository**: [Seeed-Studio/kicad-mcp-server](https://github.com/LynnL4/kicad-mcp-server)
**Author**: LynnL4 (Seeed Studio)
**License**: MIT
**Version**: 0.1.0 (Alpha)
**Status**: Work in Progress

---

## Architecture Overview

The server is built on **FastMCP** and organized into 6 tool modules across 3 categories (analysis, editing, project management), backed by 3 custom parsers and a Pydantic-based type system.

```
FastMCP Server (server.py)
    |
    +-- tools/
    |   +-- schematic.py         # Schematic analysis (5 tools) [Production]
    |   +-- pcb.py               # PCB analysis (4 tools) [Production]
    |   +-- netlist.py           # Netlist analysis (4 tools) [Production]
    |   +-- schematic_editor.py  # Schematic editing (3 tools) [Experimental]
    |   +-- pcb_layout.py        # PCB layout (2 tools) [Experimental]
    |   +-- project.py           # Project management (1 tool) [Production]
    |
    +-- parsers/
    |   +-- schematic_parser.py  # Custom S-expression regex parser
    |   +-- pcb_parser.py        # Custom S-expression regex parser (fallback)
    |   +-- pcb_parser_kicad.py  # pcbnew API parser (preferred, requires KiCad)
    |   +-- netlist_parser.py    # XML parser using ElementTree
    |
    +-- models/types.py          # Pydantic models (ComponentInfo, NetInfo, etc.)
    +-- utils/file_handlers.py   # File validation and path resolution
    +-- config.py                # Environment-based configuration (singleton)
```

### Key Design Decisions

1. **Dual PCB parsing strategy**: A regex-based fallback parser (`pcb_parser.py`) used by the tool layer, plus a `pcbnew`-based parser (`pcb_parser_kicad.py`) that requires KiCad Python API -- though the tools currently use only the regex parser.
2. **Netlist-first connection tracing**: Deliberately recommends exporting XML netlists via `kicad-cli` for accurate pin-level tracing rather than parsing schematics for connectivity.
3. **Template-based project creation**: Copies from KiCad's installed templates to ensure format compatibility rather than generating files from scratch.

---

## Complete Tool Inventory

### Production Tools (14 tools)

#### Schematic Analysis (`tools/schematic.py`) - 5 tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `list_schematic_components` | `(file_path: str, filter_type?: str, filter_value?: str, filter_dnp?: bool)` | List all components with optional filtering by type prefix, value substring, or DNP flag. Returns markdown table. |
| `get_symbol_details` | `(file_path: str, reference: str)` | Get detailed info for a specific component including properties and pins. |
| `search_symbols` | `(file_path: str, pattern: str, search_fields: str = "all")` | Regex search across reference, value, and library_id fields. Capped at 50 results. |
| `list_schematic_nets` | `(file_path: str, filter_power: bool = False)` | List all nets (global labels, local labels, power symbols). Optional power-net filter. |
| `get_schematic_info` | `(file_path: str)` | Schematic metadata: title block, component counts by type prefix, hierarchical sheets, net count. |

#### PCB Analysis (`tools/pcb.py`) - 4 tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `list_pcb_footprints` | `(file_path: str, filter_layer?: str)` | List footprints with reference, value, layer, position, rotation, pad count. |
| `get_pcb_statistics` | `(file_path: str)` | Board dimensions, layer count, thickness, footprint/pad/track/via/zone counts. |
| `analyze_pcb_nets` | `(file_path: str)` | Basic net info (just zone count). Defers to schematic tools for real analysis. |
| `find_tracks_by_net` | `(file_path: str, net_name: str)` | **Stub** - returns total track count but cannot actually filter by net. Notes kicad-skip needed. |

#### Netlist Analysis (`tools/netlist.py`) - 4 tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `generate_netlist` | `(schematic_path: str)` | Runs `kicad-cli sch export netlist --format kicadxml`. Auto-detects sub-sheets and redirects to root schematic. Outputs to `/tmp`. |
| `trace_netlist_connection` | `(netlist_path: str, reference: str, pin_number?: str)` | Traces all connections from a component (all pins or specific pin). Returns connected components per net. |
| `get_netlist_nets` | `(netlist_path: str, filter_pattern?: str)` | Lists all nets with pin connections (capped at 10 per net). Supports regex filtering. |
| `get_netlist_components` | `(netlist_path: str, filter_ref?: str)` | Lists all components with their pin-to-net mappings. Filter by reference prefix. |

#### Project Management (`tools/project.py`) - 1 tool

| Tool | Signature | Description |
|------|-----------|-------------|
| `create_kicad_project` | `(project_path: str, project_name: str, title?: str, company?: str)` | Creates project by copying KiCad template (Arduino_Mega or EuroCard). Updates UUIDs, title block, metadata. |

### Experimental Tools (5 tools)

#### Schematic Editing (`tools/schematic_editor.py`) - 3 tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `add_component_from_library` | `(file_path: str, library_name: str, symbol_name: str, reference: str, value: str, footprint?: str, x?: float, y?: float, unit?: int)` | Appends S-expression symbol block to schematic file. Hardcoded pin defs for ~6 symbols; defaults to 2-pin passive for unknowns. |
| `add_wire` | `(file_path: str, points: list[tuple[float, float]])` | Appends wire segment to schematic. No UUID on the wire element. |
| `add_label` | `(file_path: str, text: str, x: float, y: float, orientation?: float)` | Appends local label with UUID. |

#### PCB Layout (`tools/pcb_layout.py`) - 2 tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `setup_pcb_layout` | `(schematic_path: str, width?: float, height?: float, unit?: str)` | Generates a complete `.kicad_pcb` file from a template string with edge cuts, layers, default nets. **Bug**: uses nanometer units for edge cuts but the template mixes unit systems. |
| `export_gerber` | `(pcb_path: str, output_dir?: str)` | **Does not actually export Gerbers.** Creates a text info file with instructions to use KiCad GUI/CLI. |

### MCP Resources (1)

| Resource | URI | Description |
|----------|-----|-------------|
| `get_config` | `kicad://config` | Returns server configuration (project paths, summary settings, test framework defaults). |

---

## Netlist Tracing Capabilities

This is the server's strongest feature. The netlist subsystem provides:

1. **Automatic netlist generation**: Calls `kicad-cli` directly, with smart sub-sheet detection (redirects to root schematic to avoid kicad-cli silently dropping unnamed local nets).

2. **Bidirectional tracing**: Given a component reference, traces all pins to their nets and lists every other component on each net. Given a net name, lists all connected pins.

3. **Pin-level accuracy**: Because it parses KiCad's official XML netlist format rather than trying to infer connections from schematic geometry.

4. **KiCad 9.0 compatibility**: Handles the `<comp>` tag format (vs older `<component>` tags).

The schematic parser also includes a secondary wire-network tracing system (`build_wire_network`, `trace_wire_network`) that builds a graph from wire segments and uses BFS to find connected labels -- but this is geometry-based and far less reliable than the netlist approach. The project wisely recommends netlist-based tracing.

---

## Technology Stack & Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `fastmcp` | >=0.1.0 | MCP server framework |
| `mcp[cli]` | >=1.2.0 | MCP protocol library |
| `kicad-skip` | >=0.2.5 | KiCad S-expression parser (listed but **not actually imported** anywhere in the code) |
| `pydantic` | >=2.0.0 | Data models for type definitions |
| `python-dotenv` | >=1.0.0 | Environment configuration |
| `jinja2` | >=3.1.0 | Template rendering (listed but **not actually used** in current code) |
| `pcbnew` | (KiCad 9.0) | Optional: KiCad Python API for PCB parsing (pcb_parser_kicad.py) |

**Runtime requirements**: Python 3.10+, KiCad 9.0+ (for `kicad-cli` and optionally `pcbnew`).

**Build system**: Hatchling

---

## How It Interfaces with KiCad

1. **File parsing**: Directly reads `.kicad_sch` (S-expression via regex), `.kicad_pcb` (S-expression via regex or pcbnew API), and `.xml` netlist (ElementTree).

2. **CLI integration**: Calls `kicad-cli sch export netlist` via `subprocess.run()` with 30-second timeout for netlist generation.

3. **Template system**: Locates KiCad's installed templates at platform-specific paths (`/Applications/KiCad/...`, `/usr/share/kicad/...`, `C:/Program Files/KiCad/...`) and copies them for project creation.

4. **File writing**: Editing tools write directly to `.kicad_sch` files by string manipulation (appending S-expression blocks before the final closing parenthesis).

5. **No live KiCad connection**: No IPC, no socket communication, no scripting console integration. Purely file-based.

---

## Code Quality Assessment

### Strengths

- **Clean module organization**: Clear separation of tools, parsers, models, and utilities.
- **Consistent error handling**: All tools use try/except with user-friendly error messages.
- **Markdown output**: All tools return well-formatted markdown tables and headers.
- **Caching**: Parsers cache parsed data (`self._data`) to avoid re-parsing on repeated calls.
- **Dataclass models**: Clean data structures with factory methods (`from_kicad_skip`, `from_dict`).
- **Sub-sheet detection**: The netlist generator intelligently detects sub-sheets and redirects to root schematic.

### Weaknesses

- **Unused dependencies**: `kicad-skip` and `jinja2` are in requirements but not imported anywhere. The code uses custom regex parsing instead of kicad-skip.
- **Duplicate PCBFootprint class**: Defined independently in both `pcb_parser.py` and `pcb_parser_kicad.py` with different field names (`pad_count` vs `pads_count`).
- **pcb_parser_kicad.py is dead code**: The `PCBParserKiCad` class exists but is never imported by any tool. Tools use `PCBParser` (regex-based) from `pcb_parser.py`.
- **Stub tools**: `find_tracks_by_net` and `export_gerber` don't actually do what their names suggest. They return placeholder text.
- **Fragile S-expression editing**: The schematic editor appends content by finding the last `)` and inserting before it. This naive approach can break on comments, trailing whitespace, or nested structures.
- **Hardcoded pin definitions**: `SYMBOL_PINS` dict covers only 6 symbols. All unknown symbols default to 2 passive pins, making the component addition nearly useless for real designs.
- **Bare except clauses**: `pcb_parser_kicad.py:108` uses `except:` (bare) which catches everything including SystemExit.
- **Board dimension calculation**: `get_statistics()` estimates board size from footprint positions rather than parsing Edge.Cuts, which is inaccurate.
- **Test infrastructure**: Tests reference `kicad_mcp_server.tools.e2e_test` and `kicad_mcp_server.tools.core` modules that don't exist in the codebase.
- **Pydantic models unused**: `models/types.py` defines comprehensive Pydantic models but tools use plain dicts and dataclasses instead.
- **No input sanitization**: File paths from MCP clients are passed directly to `Path()` and `subprocess` without sanitization.

---

## Summary: Strengths and Weaknesses

### Strengths

1. **Netlist-based tracing is the standout feature** -- pin-level accuracy, bidirectional queries, sub-sheet awareness, and clean XML parsing.
2. **Honest about limitations** -- README clearly marks experimental tools, recommends KiCad GUI for editing, and documents the recommended workflow.
3. **Good analysis tool coverage** -- 14 production tools covering schematics, PCB, and netlists with filtering, searching, and statistics.
4. **Template-based project creation** -- avoids format compatibility issues by leveraging KiCad's own templates.
5. **Clean architecture** -- well-organized modules with clear separation of concerns.
6. **Cross-platform** -- template path detection for macOS, Linux, and Windows.

### Weaknesses

1. **Several tools are stubs** -- `find_tracks_by_net` and `export_gerber` don't deliver on their promises.
2. **Dead code and unused dependencies** -- `pcb_parser_kicad.py`, `kicad-skip`, `jinja2`, and Pydantic models are all cargo.
3. **Schematic editing is nearly non-functional** -- hardcoded pins for 6 symbols, naive string concatenation for file modification, no electrical connection verification.
4. **PCB layout generation is hardcoded** -- `setup_pcb_layout` generates a fixed template with hardcoded nets and a dummy connector footprint, mixing unit systems.
5. **No pcbnew integration in tools** -- despite documenting pcbnew as a core design principle, the actual tools use regex-based parsing.
6. **Test suite is broken** -- references nonexistent modules (`e2e_test`, `core`).
7. **Config vestigial** -- includes `default_test_framework` and `default_test_type` settings for test generation that was removed from scope.

### Overall Assessment

A well-structured analysis-focused MCP server with excellent netlist tracing capabilities. The analysis tools (schematic, PCB, netlist) form a solid foundation. However, the editing tools are barely functional prototypes, there's significant dead code, and the gap between documentation claims and actual implementation is notable. The project would benefit from removing the experimental editing tools (or gating them behind a flag), cleaning up unused dependencies, and wiring in the pcbnew-based parser that already exists but isn't used.

**Best suited for**: Design review and analysis workflows where designs are created in KiCad GUI and analyzed/verified via MCP.

**Tool count**: 19 registered MCP tools (14 production, 5 experimental) + 1 MCP resource.

**Lines of code**: ~2,250 across source files (as claimed in README, confirmed by analysis).
