# Analysis: mixelpixx/KiCAD-MCP-Server

**Repository**: https://github.com/mixelpixx/KiCAD-MCP-Server
**Version**: 2.1.0-alpha
**License**: MIT
**Language**: TypeScript (MCP layer) + Python (KiCad interface)
**Last significant activity**: November 2025 changelogs

---

## Architecture Overview

### Dual-Layer Design: TypeScript MCP Server + Python KiCad Bridge

The server uses a **two-process architecture**:

1. **TypeScript MCP Server** (`src/server.ts`, 720 lines) — Implements the MCP protocol, handles JSON-RPC 2.0 over STDIO, manages tool registration via `@modelcontextprotocol/sdk`, and routes commands to the Python subprocess.

2. **Python KiCad Interface** (`python/kicad_interface.py`, 2492 lines) — Long-running subprocess that receives JSON commands over stdin, dispatches them to modular command handlers, and returns JSON responses over stdout.

```
MCP Client (Claude/Cline)
    ↕ STDIO (JSON-RPC 2.0)
TypeScript Server (Node.js)
    ↕ stdin/stdout (JSON)
Python Interface Process
    ↕ pcbnew SWIG API / KiCad IPC API
KiCad Application
```

The TypeScript server spawns a single Python child process at startup. Commands are serialized as JSON lines to the subprocess's stdin, and responses are collected from stdout using a chunked JSON parser. A request queue ensures sequential processing with configurable per-command timeouts (30s default, 10min for DRC/exports).

### Backend Abstraction Layer

The Python side has a clean backend abstraction (`python/kicad_api/`):

- **`base.py`** (288 lines) — Abstract `KiCADBackend` and `BoardAPI` base classes defining the interface contract
- **`swig_backend.py`** (214 lines) — Uses KiCad's pcbnew SWIG bindings for file-based operations (marked deprecated)
- **`ipc_backend.py`** (1244 lines) — Uses `kicad-python` (kipy) for real-time IPC communication with running KiCad instance via Protocol Buffers over UNIX sockets
- **`factory.py`** (198 lines) — Auto-detection: tries IPC first, falls back to SWIG. Configurable via `KICAD_BACKEND` env var

### Tool Router Pattern

A notable architectural choice: tools are split into **12 "direct" tools** always visible to the LLM and **47+ "routed" tools** organized into 7 categories, discoverable via 4 meta-tools:

| Router Tool | Purpose |
|---|---|
| `list_tool_categories` | Browse all 7 categories |
| `get_category_tools` | List tools in a specific category |
| `search_tools` | Keyword search across tool names/categories |
| `execute_tool` | Execute any routed tool by name with params |

This is designed to reduce context consumption by ~70% — the LLM only loads schemas for the 12 direct tools plus the 4 router tools, then discovers others on demand.

---

## Complete Tool Inventory

### Direct Tools (Always Visible) — 12 tools

| Tool | Category |
|---|---|
| `create_project` | Project |
| `open_project` | Project |
| `save_project` | Project |
| `get_project_info` | Project |
| `place_component` | Component |
| `move_component` | Component |
| `add_net` | Routing |
| `route_trace` | Routing |
| `get_board_info` | Board |
| `set_board_size` | Board |
| `add_board_outline` | Board |
| `check_kicad_ui` | UI |

### Routed Tools by Category — 47 tools

**Board** (9 tools): `add_layer`, `set_active_layer`, `get_layer_list`, `add_mounting_hole`, `add_board_text`, `add_zone`, `get_board_extents`, `get_board_2d_view`, `launch_kicad_ui`

**Component** (8 tools): `rotate_component`, `delete_component`, `edit_component`, `find_component`, `get_component_properties`, `add_component_annotation`, `group_components`, `replace_component`

**Export** (8 tools): `export_gerber`, `export_pdf`, `export_svg`, `export_3d`, `export_bom`, `export_netlist`, `export_position_file`, `export_vrml`

**DRC** (8 tools): `set_design_rules`, `get_design_rules`, `run_drc`, `add_net_class`, `assign_net_to_class`, `set_layer_constraints`, `check_clearance`, `get_drc_violations`

**Schematic** (8 tools): `create_schematic`, `add_schematic_component`, `add_wire`, `add_schematic_connection`, `add_schematic_net_label`, `connect_to_net`, `get_net_connections`, `generate_netlist`

**Library** (4 tools): `list_libraries`, `search_footprints`, `list_library_footprints`, `get_footprint_info`

**Routing** (2 tools): `add_via`, `add_copper_pour`

### Additional Tools (registered in Python command routes but not in TS registry)

These are registered in `kicad_interface.py` command_routes but not reflected in the TypeScript registry:

- **Symbol Library**: `list_symbol_libraries`, `search_symbols`, `list_library_symbols`, `get_symbol_info`
- **JLCPCB**: `download_jlcpcb_database`, `search_jlcpcb_parts`, `get_jlcpcb_part`, `get_jlcpcb_database_stats`, `suggest_jlcpcb_alternatives`
- **Datasheet**: `enrich_datasheets`, `get_datasheet_url`
- **Schematic extras**: `load_schematic`, `delete_schematic_component`, `edit_schematic_component`, `add_schematic_wire`, `list_schematic_libraries`, `export_schematic_pdf`
- **IPC-specific**: `get_backend_info`, `ipc_add_track`, `ipc_add_via`, `ipc_add_text`, `ipc_list_components`, `ipc_get_tracks`, `ipc_get_vias`, `ipc_save_board`
- **Footprint creation**: `create_footprint`, `edit_footprint_pad`, `list_footprint_libraries`, `register_footprint_library`
- **Symbol creation**: `create_symbol`, `delete_symbol`, `list_symbols_in_library`, `register_symbol_library`
- **Misc**: `route_pad_to_pad`, `get_component_pads`, `get_pad_position`, `place_component_array`, `align_components`, `duplicate_component`, `delete_trace`, `query_traces`, `modify_trace`, `copy_routing_pattern`, `create_netclass`, `route_differential_pair`, `refill_zones`

**Total unique commands in Python**: ~80+

---

## MCP Resources Exposed — 8 resources

| URI | MIME Type | Description |
|---|---|---|
| `kicad://project/current/info` | application/json | Project metadata |
| `kicad://project/current/board` | application/json | Board properties (dimensions, layers, DRC) |
| `kicad://project/current/components` | application/json | Component list with positions/footprints |
| `kicad://project/current/nets` | application/json | Electrical nets and connections |
| `kicad://project/current/layers` | application/json | Layer stack configuration |
| `kicad://project/current/design-rules` | application/json | Current DRC settings |
| `kicad://project/current/drc-report` | application/json | DRC violations from last run |
| `kicad://board/preview.png` | image/png | 2D board rendering (base64 PNG) |

Resources are defined in Python (`python/resources/resource_definitions.py`) and re-exposed through TypeScript resource registration files (`src/resources/project.ts`, `board.ts`, `component.ts`, `library.ts`).

---

## MCP Prompts — 9 prompts

The server also registers MCP prompts (an underused MCP feature) for domain-specific guidance:

- **Component**: `component_selection`, `component_placement_strategy`, `component_replacement_analysis`, `component_troubleshooting`, `component_value_calculation`
- **Routing**: `routing_strategy`, `differential_pair_routing` (in `routing.ts`, 288 lines)
- **Design**: prompts for design review, power integrity, EMC analysis (in `design.ts`, 321 lines)
- **Footprint**: footprint selection guidance (in `footprint.ts`, 137 lines)

---

## Technology Stack

### TypeScript Side
| Dependency | Version | Purpose |
|---|---|---|
| `@modelcontextprotocol/sdk` | ^1.21.0 | MCP server implementation |
| `zod` | ^3.25.0 | Schema validation for tool parameters |
| `express` | ^5.1.0 | Listed but unused (likely leftover from planned HTTP transport) |
| `dotenv` | ^17.0.0 | Environment variable loading |
| TypeScript | ^5.9.3 | Language |
| Node.js | 18+ | Runtime |

### Python Side
| Dependency | Purpose |
|---|---|
| `kicad-skip` >= 0.1.0 | Schematic file manipulation (S-expression parsing) |
| `pcbnew` (SWIG) | KiCad's native Python bindings for PCB operations |
| `kicad-python` (kipy) | Optional: IPC API for real-time KiCad communication |
| `Pillow` >= 9.0.0 | Image processing for board rendering |
| `cairosvg` >= 2.7.0 | SVG rendering |
| `pydantic` >= 2.5.0 | Data validation |
| `requests` >= 2.32.5 | HTTP client for JLCPCB API |
| `colorlog` >= 6.7.0 | Colored logging output |
| `python-dotenv` >= 1.0.0 | Environment configuration |

### Platform Support
- **Linux** (primary, fully tested) — Ubuntu 22.04+
- **Windows 10/11** — Supported with automated PowerShell setup script
- **macOS** — Experimental, requires KiCad's bundled Python with `--system-site-packages`

---

## How It Interfaces with KiCad

### 1. pcbnew SWIG API (Legacy, File-Based)
The traditional approach: import `pcbnew` Python module, manipulate board objects in memory, save to `.kicad_pcb` files. User must manually reload in KiCad UI. This is the **default fallback** and is the more mature code path. The module requires KiCad's bundled Python or correct PYTHONPATH setup.

### 2. KiCad 9.0 IPC API (Experimental, Real-Time)
Uses `kicad-python` (kipy) library to communicate with a running KiCad instance via Protocol Buffers over UNIX sockets (or named pipes on Windows). Changes appear **immediately** in the KiCad UI without reload. Requires `Preferences > Plugins > Enable IPC API Server` in KiCad.

20+ commands are IPC-capable (tracked in `IPC_CAPABLE_COMMANDS` dict), including routing, component placement, zone operations, and board setup. The hybrid approach attempts IPC first and falls back to SWIG per-command.

### 3. kicad-skip (Schematic Manipulation)
Schematics use the `kicad-skip` library which directly parses/writes KiCad S-expression files (`.kicad_sch`). The server extends this with:
- **Dynamic symbol loading**: Parse `.kicad_sym` library files, inject symbol definitions into schematics
- **Wire creation**: Direct S-expression injection (bypasses kicad-skip limitations)
- **Pin discovery**: Parse symbol definitions with rotation-aware coordinate transforms

### 4. KiCad CLI
Used for exports (Gerber, PDF, SVG, 3D) when the native API isn't sufficient. Also used for process detection (`check_kicad_ui`, `launch_kicad_ui`).

---

## Code Quality Assessment

### Strengths

1. **Comprehensive scope**: 80+ commands covering the full PCB design workflow from project creation through DRC to manufacturing export. Also covers schematics, which most competitors skip.

2. **Good abstraction**: The backend factory pattern cleanly separates SWIG vs IPC concerns. Adding a new backend would be straightforward.

3. **Smart tool discovery**: The router pattern is a genuinely useful innovation for managing LLM context with many tools. Having 64+ tools always loaded would waste significant context window.

4. **MCP prompts**: Unique among KiCad MCP servers — provides domain-expert guidance prompts for component selection, routing strategy, and design review.

5. **Cross-platform Python detection**: Extensive logic for finding the correct Python executable across Linux, macOS, and Windows, including venv support and KiCad-bundled Python.

6. **Extensive documentation**: 30+ docs covering architecture, platform guides, troubleshooting, JLCPCB integration, and development status.

7. **JLCPCB integration**: Dual-mode (local SQLite + API) parts catalog with 2.5M+ components, pricing, and cost optimization.

### Weaknesses

1. **Minimal test coverage**: Only 2 test files exist (502 lines total):
   - `tests/test_platform_helper.py` (172 lines)
   - `python/test_ipc_backend.py` (330 lines)
   - No TypeScript tests at all (`"echo 'TypeScript tests not yet configured'"`)
   - CI pipeline has `|| echo "Tests not configured yet"` fallbacks everywhere

2. **Dead code / dual server implementations**: `src/kicad-server.ts` (500 lines) is an older, duplicate server implementation with hardcoded Windows paths (`c:/repo/KiCAD-MCP/`) that appears abandoned alongside the main `src/server.ts`.

3. **Tool registry inconsistency**: The TypeScript tool registry (`registry.ts`) lists 47 routed tools, but the Python command routes register 80+ commands. Many tools exist in Python but aren't exposed through the TypeScript MCP layer or router.

4. **Express dependency is unused**: `express` ^5.1.0 is in dependencies but never used — the server only uses STDIO transport.

5. **No input validation on Python side**: The TypeScript layer validates with Zod schemas, but the Python command handlers generally accept raw dicts without validation. If a tool is called via `execute_tool` router, the Zod validation is bypassed.

6. **Single-threaded request queue**: Commands are processed sequentially. A long-running DRC check (up to 10 minutes) blocks all other operations.

7. **Error handling gaps**: The Python subprocess communication has no reconnection logic. If the Python process crashes, the server is dead until restarted. The `handlePythonResponse` method silently discards data if no request is pending.

8. **Schematic workflow complexity**: The dynamic symbol loading system (parsing `.kicad_sym` files, injecting S-expressions, creating offscreen templates, reloading schematics) is fragile and involves multiple file rewrites per component placement.

9. **Windows-centric legacy**: Remnants of Windows-only paths (`C:\\Program Files\\KiCad\\9.0`) scattered through the codebase, including the PYTHONPATH default in `server.ts`.

10. **Alpha quality**: Self-described as 2.1.0-alpha. Many features listed as "NEEDS TESTING" (JLCPCB), "experimental" (IPC), or "not yet configured" (tests, linting, Docker).

### Code Size

| Layer | Lines |
|---|---|
| TypeScript (src/) | ~6,100 |
| Python commands | ~8,500 |
| Python core (interface, API, schemas, resources, utils) | ~7,000 |
| Tests | ~500 |
| **Total** | **~22,100** |

---

## Summary

mixelpixx/KiCAD-MCP-Server is the **most feature-rich** KiCad MCP implementation available, with 80+ commands spanning PCB layout, schematic design, library management, JLCPCB integration, and manufacturing export. Its TypeScript+Python architecture is reasonable for bridging MCP with KiCad's native Python API, and the tool router pattern is a clever solution for managing LLM context.

However, it is clearly **alpha-quality**: minimal tests, dead code, inconsistent tool registration between layers, and multiple features flagged as experimental. The complexity of the schematic workflow (dynamic symbol loading via S-expression injection) is impressive but fragile. The project would benefit most from: (1) test coverage, (2) cleanup of the TS/Python tool registration gap, and (3) removing dead code like `kicad-server.ts`.
