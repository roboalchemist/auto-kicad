# Huaqiu-Electronics/kicad-mcp Analysis

**Repositories analyzed:**
- [Huaqiu-Electronics/kicad-mcp](https://github.com/Huaqiu-Electronics/kicad-mcp) (umbrella/meta repo)
- [Huaqiu-Electronics/kicad-mcp-server](https://github.com/Huaqiu-Electronics/kicad-mcp-server) (actual MCP server)
- Also references: [kicad-mcp-client](https://github.com/Huaqiu-Electronics/kicad-mcp-client), [kicad-win-builder](https://github.com/Huaqiu-Electronics/kicad-win-builder)

**License:** MIT

---

## Architecture Overview

Huaqiu's approach is **unique among all analyzed KiCad MCP servers** -- it is a **built-in integration** shipped as part of a custom KiCad distribution (the "Huaqiu Distribution"), not a standalone external tool. The architecture has four major components:

### 1. Custom KiCad Fork (C++ Layer)
Huaqiu maintains a fork of KiCad at `gitlab.com/kicad-hq/kicad` (tracking the `release/9.0` branch). They have added:
- A **"Robot" button** in both the PCB and Schematic editors that toggles a Copilot panel
- An embedded **IPC communication channel** (NNG/nanomsg sockets) between KiCad's C++ core and external processes
- Extended C++ SDK APIs exposed via the IPC channel (drawing primitives, symbol manipulation, PCB operations, frame management)

### 2. KiCad MCP Server (Python - this repo)
A Python MCP server (`main.py` + `sdk_api_params.py`) that:
- Connects to KiCad via **NNG (nanomsg next-gen)** sockets using `pynng`
- Exposes 76 MCP tools that map to KiCad C++ SDK APIs
- Uses `FastMCP` from the official MCP Python SDK
- Runs via stdio transport, launched by the MCP client

### 3. KiCad MCP Client
An embedded [mcp-agent](https://github.com/lastmile-ai/mcp-agent) instance that:
- Is auto-launched by the KiCad editor on startup
- Receives a dual-communicating IPC channel and the KiCad IPC API URL
- Manages the MCP server lifecycle and routes tool calls

### 4. Frontend (NextChat)
A hosted [NextChat](https://github.com/ChatGPTNextWeb/NextChat) instance at `chat.eda.cn` that:
- Renders inside KiCad via a webview
- Communicates with KiCad through a webview IPC API
- KiCad forwards messages between the UI and the mcp-agent

### Communication Flow
```
User <-> NextChat (webview) <-> KiCad Editor <-> mcp-agent (MCP Client)
                                     |                    |
                                     |              MCP Server (stdio)
                                     |                    |
                                     +--- NNG/IPC --------+
                                     |
                               KiCad C++ SDK
```

---

## Technology Stack & Dependencies

| Component | Technology |
|-----------|-----------|
| MCP Framework | `mcp[cli]>=1.3.0` (FastMCP) |
| IPC Transport | `pynng>=0.8.1` (nanomsg next-gen, Req/Rep pattern) |
| LLM Integration | `typechat>=0.0.4` (Microsoft TypeChat for structured LLM output) |
| LLM Provider | OpenAI-compatible API (configurable endpoint/key/model) |
| RAG/Embeddings | `langchain>=0.1.0`, `langchain-community>=0.1.0`, `chromadb>=0.4.22` |
| HTTP Client | `httpx>=0.28.1` |
| HTML Parsing | `beautifulsoup4>=4.13.3` |
| Python Version | `>=3.11` |
| Package Manager | `uv` (with Tsinghua mirror for China) |
| Logging | RotatingFileHandler (10MB, 5 backups) |

---

## IPC Protocol Details

The server communicates with KiCad via **NNG Req/Rep sockets** (not HTTP like most other MCP servers).

### Message Format
```json
{
  "cmd": "cpp_sdk_action",
  "params": {
    "action": "cpp_sdk_api",
    "context": {
      "api": "<api_name>",
      "parameter": { ... }
    }
  }
}
```

### Command Types
- `cpp_sdk_action` -- Mutating operations (draw, place, modify, move, rotate)
- `cpp_sdk_query` -- Read-only queries (querySymbolPin, getSymbolLibrary, queryCurrentFrameType, etc.)
- `netlist` -- Special command to retrieve XML netlist (base64-encoded)
- `placeNetLabels` -- Special command for net label placement

### Socket Configuration
- **Timeout:** 30 seconds for both send and receive
- **URL format:** IPC socket path (e.g., `ipc:///tmp/kicad_copilot_pair-<uuid>.ipc`)
- Passed as a CLI argument when launching the MCP server

---

## Complete MCP Tool Inventory (76 tools)

### Netlist & Net Labels (3 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 1 | `generate_net_labels` | `net_list: str` | Uses TypeChat + LLM to generate net label connections from XML netlist |
| 2 | `place_all_net_labels` | `nets: API_PLACE_NETLABELS` | Batch-places net labels onto the schematic |
| 3 | `get_current_kicad_project` | (none) | Returns cleaned XML netlist (nets section stripped) |

### Schematic Drawing Primitives (7 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 4 | `draw_multi_wires` | `lines: API_MULTI_LINES_PARAMS` | Draw multiple geometric line segments (non-electrical) |
| 5 | `draw_multi_buses` | `lines: API_MULTI_LINES_PARAMS` | Draw multiple bus lines (signal groups) |
| 6 | `draw_circle` | `circle: API_CIRCLE_PARAMS` | Draw circle (center + radius) |
| 7 | `draw_arc` | `arc: API_ARC_PARAMS` | Draw arc (start + end + center) |
| 8 | `draw_bezier` | `bezier: API_BEZIER_PARAMS` | Draw Bezier curve (start + c1 + c2 + end) |
| 9 | `draw_rectangle` | `rectangle: API_RECTANGLE_PARAMS` | Draw rectangle (top_left + width + height) |
| 10 | `create_table` | `table: API_TABLE_PARAMS` | Create table (pos + rows + cols) |

### Schematic Text & Labels (7 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 11 | `create_textbox` | `textbox: API_TEXTBOX_PARAMS` | Create textbox (box + text) |
| 12 | `create_common_text` | `text: API_LABEL_PARAMS` | Place non-electrical text annotation |
| 13 | `create_local_label` | `label: API_LABEL_PARAMS` | Create local label (intra-sheet net connectivity) |
| 14 | `create_global_label` | `label: API_LABEL_PARAMS` | Create global label (cross-sheet net connectivity) |
| 15 | `create_hier_label` | `label: API_LABEL_PARAMS` | Create hierarchical label (parent-child sheet connectivity) |
| 16 | `create_class_label` | `label: API_CLASS_LABEL_PARAMS` | Create class label (net_class + component_class) |
| 17 | `create_hier_sheet` | `sheet: API_HIER_SHEET_PARAMS` | Create hierarchical sheet (box + title) |

### Symbol Operations (8 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 18 | `query_symbol_pin` | `query: API_QUERY_SYMBOL` | Query pin info for a symbol by reference designator |
| 19 | `query_symbol_library` | (none) | List all available symbol libraries (global + project) |
| 20 | `place_symbol` | `params: API_PLACE_SYMBOL` | Place component symbol (category, value, position, reference) |
| 21 | `move_symbol` | `params: API_MOVE_SYMBOL` | Move symbol to new position |
| 22 | `rotate_symbol` | `params: API_ROTATE_SYMBOL` | Rotate symbol 90 degrees |
| 23 | `modify_symbol_value` | `params: API_MODIFY_SYMBOL_VALUE` | Change symbol value (e.g., resistance) |
| 24 | `modify_symbol_reference` | `params: API_MODIFY_SYMBOL_REFERENCE` | Change symbol reference designator |
| 25 | `create_symbol_library` | `params: API_CREATE_SYMBOL_LIBARARY` | Create new symbol library |

### Symbol Library Editing (1 tool)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 26 | `create_symbol_pin` | `params: API_CREATE_LIB_SYMBOL_PIN` | Create pin in symbol library |

### PCB Track & Via (2 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 27 | `create_pcb_track` | `params: API_PCB_TRACK_PARAMS` | Create PCB track/trace |
| 28 | `create_pcb_via` | `params: API_PCB_VIA_PARAMS` | Create PCB via |

### PCB Pad Operations (7 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 29 | `create_pcb_pad` | `params: API_PCB_PAD_PARAMS` | Create PCB pad |
| 30 | `move_pcb_pad` | `params: API_MOVE_PCB_PAD_PARAMS` | Move PCB pad |
| 31 | `rotate_pcb_pad` | `params: API_ROTATE_PCB_PAD` | Rotate PCB pad |
| 32 | `modify_pcb_pad_number` | `params: API_MODIFY_PAD_NUMBER` | Change pad number |
| 33 | `modify_pcb_pad_size` | `params: API_MODIFY_PAD_SIZE` | Change pad size |
| 34 | `modify_pcb_pad_drill_size` | `params: API_MODIFY_PAD_DRILL_SIZE` | Change pad drill size |
| 35 | `modify_pcb_pad_drill_shape` | `params: API_MODIFY_PAD_DRILL_SHAPE` | Change pad drill shape |

### PCB Pad Position (1 tool)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 36 | `set_pcb_pad_new_position` | `params: API_SET_PAD_POSITION` | Set absolute pad position |

### PCB Layer & Footprint Queries (3 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 37 | `query_pcb_layer_names` | (none) | List all PCB layer names |
| 38 | `query_pcb_all_footprint_info` | (none) | Get info for all footprints |
| 39 | `query_pcb_footprint_info` | `params: API_PCB_REFERENCE_LIST` | Get info for specific footprints by reference |

### PCB Footprint Manipulation (4 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 40 | `move_pcb_footprint` | `params: API_MOVE_FOOTPRINT_PARAMS` | Move footprint |
| 41 | `modify_pcb_footprint_reference` | `params: API_MODIFY_FOOTPRINT_REFERENCE` | Change footprint reference |
| 42 | `set_pcb_footprint_position` | `params: API_SET_FOOTPRINT_POSITION` | Set absolute footprint position |
| 43 | `rotate_pcb_footprint` | `params: API_ROTATE_FOOTPRINT_PARAMS` | Rotate footprint |

### Frame/Window Management (5 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 44 | `queryCurrentFrameType` | (none) | Query current active frame type (PCB/Schematic/etc.) |
| 45 | `closeFrame` | `params: API_FRAME_PARAMS` | Close a specific frame window |
| 46 | `openFrame` | `params: API_FRAME_PARAMS` | Open a specific frame window |
| 47 | `saveFrame` | (none) | Save current frame |
| 48 | `saveAsFrame` | (none) | Save-as current frame |

### Import/Export (3 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 49 | `importNonKicadSchematic` | (none) | Import non-KiCad schematic (Altium, Eagle, etc.) |
| 50 | `importVectorGraphicsFile` | (none) | Import vector graphics (SVG, DXF, etc.) |
| 51 | `exportNetlist` | (none) | Export netlist |

### Dialog/UI Operations (7 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 52 | `openSchematicSetupDlg` | (none) | Open schematic setup dialog |
| 53 | `openPageSettingDlg` | (none) | Open page settings dialog |
| 54 | `openPrintDlg` | (none) | Open print dialog |
| 55 | `openPlotDlg` | (none) | Open plot dialog |
| 56 | `closeCurrentFrame` | (none) | Close current frame |
| 57 | `openFindDialog` | (none) | Open find dialog |
| 58 | `openFindAndReplaceDialog` | (none) | Open find and replace dialog |

### Selection & Editing (3 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 59 | `deleteTool` | (none) | Activate delete tool |
| 60 | `selectAllItems` | (none) | Select all items |
| 61 | `unSelectAllItems` | (none) | Deselect all items |

### Panel Toggles (6 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 62 | `openEditTextAndGraphicPropertyDialog` | (none) | Open text/graphic property editor |
| 63 | `togglePropertyPanel` | (none) | Toggle properties panel |
| 64 | `toggleSearchPanel` | (none) | Toggle search panel |
| 65 | `toggleHierarchyPanel` | (none) | Toggle hierarchy panel |
| 66 | `toggleNetNavigatorPanel` | (none) | Toggle net navigator panel |
| 67 | `toggleDesignBlockPanel` | (none) | Toggle design block panel |

### Browser & View (3 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 68 | `openSymbolLibraryBrowser` | (none) | Open symbol library browser |
| 69 | `zoomView` | `params: API_ZOOM_PARAMS` | Zoom the view |
| 70 | `showBusSyntaxHelp` | (none) | Show bus syntax help |

### Verification & Simulation (2 tools)
| # | Tool | Parameters | Description |
|---|------|-----------|-------------|
| 71 | `runERCCheck` | (none) | Run electrical rules check |
| 72 | `showSpiceSimulator` | (none) | Open SPICE simulator |

**Note:** The grep count finds 76 `@mcp.tool()` decorators. The discrepancy with the claimed 72 may be due to tools added after the README was written, or the README count excluding some utility tools.

---

## Type System (52 TypedDict classes)

The `sdk_api_params.py` file defines 52 TypedDict classes providing strong typing for all API parameters. Key categories:

- **Geometric primitives:** `API_POINT_PARAMS`, `API_SIZE_PARAMS`, `API_LINE_PARAMS`, `API_MULTI_LINES_PARAMS`, `API_CIRCLE_PARAMS`, `API_ARC_PARAMS`, `API_BEZIER_PARAMS`, `API_RECTANGLE_PARAMS`
- **Schematic elements:** `API_LABEL_PARAMS`, `API_CLASS_LABEL_PARAMS`, `API_TEXTBOX_PARAMS`, `API_TABLE_PARAMS`, `API_HIER_SHEET_PARAMS`
- **Symbol operations:** `API_QUERY_SYMBOL`, `API_PLACE_SYMBOL`, `API_MOVE_SYMBOL`, `API_ROTATE_SYMBOL`, `API_MODIFY_SYMBOL_VALUE`, `API_MODIFY_SYMBOL_REFERENCE`, `API_CREATE_SYMBOL_LIBARARY`, `API_CREATE_LIB_SYMBOL_PIN`
- **PCB operations:** `API_PCB_TRACK_PARAMS`, `API_PCB_VIA_PARAMS`, `API_PCB_PAD_PARAMS`, `API_MOVE_PCB_PAD_PARAMS`, `API_ROTATE_PCB_PAD`, `API_MODIFY_PAD_NUMBER`, `API_MODIFY_PAD_SIZE`, `API_MODIFY_PAD_DRILL_SIZE`, `API_MODIFY_PAD_DRILL_SHAPE`, `API_SET_PAD_POSITION`
- **PCB queries:** `API_PCB_LAYER_NAME`, `API_PCB_LAYER_NAME_LIST`, `API_PCB_FOOTPRINT_INFO`, `API_PCB_FOOTPRINT_INFO_LIST`, `API_PCB_REFERENCE`, `API_PCB_REFERENCE_LIST`
- **Footprint ops:** `API_MOVE_FOOTPRINT_PARAMS`, `API_MODIFY_FOOTPRINT_REFERENCE`, `API_SET_FOOTPRINT_POSITION`, `API_ROTATE_FOOTPRINT_PARAMS`
- **Frame management:** `API_FRAME_TYPE_PARAMS` (Enum), `API_FRAME_PARAMS`
- **View:** `API_ZOOM_PARAMS`
- **Enums:** `API_PCB_VIA_TYPE`, `API_PCB_LAYER_ID`, `API_PAD_DRILL_SHAPE`, `API_SYMBOL_CATEGORY`

---

## LLM Integration (TypeChat)

The server includes a **unique LLM-in-the-loop** feature via Microsoft's TypeChat:

- `generate_net_labels` takes an XML netlist and uses an LLM (OpenAI-compatible) to generate structured net label placement data
- TypeChat provides schema-validated JSON output, ensuring the LLM response matches `API_PLACE_NETLABELS`
- Configurable via env vars or CLI args: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`
- Default model: `gpt-5-mini` (appears to be a typo or future model, likely meant `gpt-4o-mini`)
- 3-minute timeout for LLM calls

This is significant -- the MCP server itself calls an LLM internally, making it an **agentic MCP server** rather than a pure tool provider.

---

## Code Metrics

| Metric | Value |
|--------|-------|
| Total Python lines | 3,355 |
| `main.py` | 2,404 lines |
| `sdk_api_params.py` | 951 lines |
| MCP tools | 76 |
| TypedDict classes | 52 |
| Enum classes | ~5 |
| Python files | 2 |

---

## Strengths

1. **Deep Native Integration**: Unlike all other analyzed MCP servers that use KiCad's external IPC API or file parsing, Huaqiu's approach is built directly into a KiCad fork. This gives it access to C++ SDK internals that external tools cannot reach (UI management, dialogs, frame operations, symbol library creation).

2. **Largest Tool Surface**: 76 tools is the most of any analyzed server, covering schematic drawing, PCB manipulation, symbol management, frame control, dialog automation, and panel toggles.

3. **Both Schematic AND PCB**: Full coverage of both schematic and PCB operations, including tracks, vias, pads, footprints -- not just schematic-only.

4. **Strong Type System**: 52 TypedDict classes provide rich parameter documentation and validation. Docstrings are extremely detailed with tables, examples, and unit specifications.

5. **LLM-in-the-Loop**: The TypeChat integration for automatic net label generation is innovative -- using an LLM to interpret XML netlists and generate structured placement commands.

6. **NNG Transport**: Using nanomsg (NNG) for IPC is more efficient than HTTP for local communication, with binary framing and lower overhead.

7. **Full Application Control**: Can open/close frames, toggle panels, run ERC checks, open SPICE simulator -- things no other MCP server can do since they don't have access to KiCad's UI layer.

8. **Production-Ready Packaging**: Ships as part of an installable KiCad distribution with embedded frontend (NextChat).

## Weaknesses

1. **Vendor Lock-in**: Requires the Huaqiu KiCad distribution. Won't work with stock KiCad unless the C++ IPC API changes are upstreamed to KiCad mainline. The README mentions targeting KiCad 10 for upstream inclusion.

2. **Windows-Only Distribution**: The installable distribution only provides Windows builds (`kicad-huaqiu-9.0.7-rc3-x86_64.exe`). The IPC socket paths use Windows conventions.

3. **Single-File Architecture**: All 76 tools in one 2,404-line `main.py` with no modular organization. No separation between schematic tools, PCB tools, UI tools, etc.

4. **No Error Recovery**: Many tools check `if KICAD_CLIENT is None` but then fall through to `KICAD_CLIENT.cpp_sdk_action()` anyway (would crash with NoneType error). The pattern is:
   ```python
   if KICAD_CLIENT is None:
       logger.error("Client not initialized")
   return KICAD_CLIENT.cpp_sdk_action(...)  # crashes if None!
   ```
   Missing `return None` after the error check.

5. **No Read Operations for Most Elements**: Heavy on write/modify operations but light on querying existing state. Can query symbol pins, footprint info, and layer names, but cannot query existing wires, labels, text, rectangles, etc.

6. **No Undo/Transaction Support**: No undo mechanism. Placing incorrect components or moving items to wrong positions has no programmatic reversal.

7. **Placeholder Parameters**: Several tools pass empty `params={}` (e.g., `saveAsFrame`, `importNonKicadSchematic`, `importVectorGraphicsFile`, `exportNetlist`) -- they trigger UI dialogs rather than completing operations programmatically.

8. **China-Centric Infrastructure**: PyPI mirror set to Tsinghua University, frontend hosted at `chat.eda.cn`, OpenAI proxy at `aihubmix.com`. International users may face connectivity issues.

9. **Heavy Dependencies**: Pulls in LangChain + ChromaDB (RAG stack) but these don't appear to be used in the current `main.py`. Likely leftover from planned features or the client side.

10. **Inconsistent Naming**: Mix of `camelCase` (`queryCurrentFrameType`, `saveFrame`) and `snake_case` (`create_pcb_track`, `modify_symbol_value`) in tool names. Some TypedDict field names have typos (e.g., `refernce` instead of `reference` in `API_SYMBOL_PIN_LABEL`).

11. **No Tests**: No test files in the repository. No CI/CD configuration visible.

12. **Verbose Docstrings**: While thorough, the docstrings are extremely verbose (sometimes 50+ lines for a simple wrapper function), which inflates the codebase and may overwhelm LLM context windows.

---

## IPC API Coverage Summary

| Domain | Operations | Query/Read |
|--------|-----------|-----------|
| Schematic Drawing | Lines, buses, circles, arcs, beziers, rectangles, tables | None |
| Schematic Labels | Local, global, hierarchical, class labels, common text | None |
| Schematic Symbols | Place, move, rotate, modify value/reference | Pin info, library list |
| Symbol Libraries | Create library, create pin | Library list |
| PCB Tracks/Vias | Create track, create via | None |
| PCB Pads | Create, move, rotate, modify number/size/drill | None |
| PCB Footprints | Move, rotate, set position, modify reference | All footprint info, specific footprint info, layer names |
| Frame Management | Open, close, save, save-as | Query current frame type |
| UI Automation | Dialogs, panels, find/replace, zoom | None |
| Import/Export | Non-KiCad schematic, vector graphics, netlist export | Netlist (XML) |
| Verification | ERC check, SPICE simulator | None |
| Net Labels | Generate (via LLM), place batch | None |

---

## Comparison with Other Approaches

| Aspect | Huaqiu (Built-in) | External MCP Servers (typical) |
|--------|-------------------|-------------------------------|
| KiCad Version | Custom fork (9.0.7-rc3) | Stock KiCad 9.0+ |
| Communication | NNG IPC sockets (direct) | HTTP to KiCad IPC API (port 2137) |
| Access Level | C++ SDK internals + UI layer | Public IPC API only |
| Tool Count | 76 | 10-45 typically |
| UI Control | Full (dialogs, panels, frames) | None |
| PCB Support | Yes (tracks, vias, pads, footprints) | Varies (often schematic-only) |
| Installation | Custom KiCad installer | pip/uv install + config |
| Platform | Windows only (currently) | Cross-platform |
| Upstream Compatible | No (requires fork) | Yes (stock KiCad) |
