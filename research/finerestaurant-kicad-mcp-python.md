# Finerestaurant/kicad-mcp-python Analysis

**Repository**: [Finerestaurant/kicad-mcp-python](https://github.com/Finerestaurant/kicad-mcp-python)
**Author**: anthonypark (anthonypark6904@gmail.com)
**Version**: 0.1.0
**License**: MIT
**Language**: Python (>=3.10)
**Lines of Code**: ~700 (application code, excluding kicad-python submodule)

---

## Architecture Overview

This MCP server takes an **IPC-API-first approach**, communicating with a running KiCad instance via KiCad's official `kicad-python` (kipy) library over its IPC protocol. Unlike file-parsing approaches, it requires KiCad to be running with its IPC server enabled (`Tools -> External Plugin -> Start Server`).

### High-Level Architecture

```
MCP Client (Claude/VSCode)
    |  stdio
    v
FastMCP Server (main.py)
    |
    +-- AnalyzeTools (BoardAnalyzer)
    |       |-- get_board_status (returns item data + screenshot)
    |       |-- get_items_by_type
    |       |-- get_item_type_args_hint
    |
    +-- ManipulationTools
            |-- CreateItemFlowManager (3-step wizard)
            |-- EditItemFlowManager (3-step wizard)
            |-- MoveItemFlowManager (3-step wizard)
            |-- RemoveItemFlowManager (1-step)
    |
    +-- kicad-python (kipy) -- IPC-API --> Running KiCad Instance
    +-- kicad-cli (subprocess) --> SVG export --> cairosvg --> JPG screenshot
```

### Key Design Pattern: ActionFlowManager

The central architectural innovation is the **ActionFlowManager** - a multi-step wizard pattern for complex operations. Each manipulation (create, edit, move) is broken into sequential steps:

1. **Step 1**: Discovery - returns available item types
2. **Step 2**: Configuration - returns required arguments/schema for the chosen type
3. **Step 3**: Execution - performs the actual operation

Each step is registered as a separate MCP tool. The response includes `next_action` metadata guiding the AI to call the next step. This is effectively a guided conversation flow where the AI progressively gathers required parameters.

### KiCad Communication

Two distinct communication channels:

1. **IPC-API via kipy**: All read/write operations on board objects (footprints, tracks, vias, etc.) go through `kipy.KiCad().get_board()`. This uses protobuf messages over a local socket to a running KiCad process.

2. **CLI subprocess**: Screenshot generation shells out to `kicad-cli pcb export svg`, then converts SVG -> PNG -> JPG via cairosvg and Pillow, returning base64-encoded image data.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| MCP Framework | `mcp` (FastMCP) v1.9.3+ |
| KiCad Interface | `kicad-python` (kipy) - git submodule, IPC-API |
| Protobuf | `google.protobuf` (via kipy) for board item serialization |
| Screenshot | `kicad-cli` (subprocess) + `cairosvg` + `Pillow` |
| Config | `python-dotenv` for env vars |
| Package Manager | Poetry |
| Transport | stdio |

---

## Complete MCP Tool Inventory

### Analyze Tools (BoardAnalyzer)

| Tool | Signature | Description |
|------|-----------|-------------|
| `get_board_status` | `() -> [dict, ImageContent]` | Returns comprehensive board state: all items grouped by type + JPG screenshot. Core situational awareness tool. |
| `get_items_by_type` | `(item_type: str) -> dict` | Returns items of a specific type as `{id: item}` dict. Types: Arc, BoardGraphicShape, BoardText, BoardTextBox, Dimension, Field, Footprint3DModel, FootprintInstance, Net, Pad, Track, Via, Zone |
| `get_item_type_args_hint` | `(item_type: str) -> dict` | Returns the protobuf schema/args configuration for a given item type. Used to discover what fields are available. |

### Manipulation Tools - Create Item Flow (3 steps)

| Tool | Signature | Description |
|------|-----------|-------------|
| `create_item_step_1` | `() -> dict_keys` | Returns available item types (discovery step, skippable) |
| `create_item_step_2` | `(item_type: str) -> dict` | Returns argument schema for the chosen item type |
| `create_item_step_3` | `(item_type: str, args: dict) -> str` | Creates the item on the board, returns item ID |

### Manipulation Tools - Edit Item Flow (3 steps)

| Tool | Signature | Description |
|------|-----------|-------------|
| `edit_item_step_1` | `() -> dict_keys` | Returns available item types (discovery step, skippable) |
| `edit_item_step_2` | `(item_type: str) -> dict` | Returns item list + argument schema for the type |
| `edit_item_step_3` | `(item_id: str, args: Dict) -> str` | Edits the specified item's properties, returns result |

### Manipulation Tools - Move Item Flow (3 steps)

| Tool | Signature | Description |
|------|-----------|-------------|
| `move_item_step_1` | `() -> dict_keys` | Returns available item types (discovery step, skippable) |
| `move_item_step_2` | `(item_type: str) -> dict` | Returns items of the chosen type |
| `move_item_step_3` | `(item_id: str, args: Dict) -> str` | Moves item by offset. Track: `{start, end}` tuples. Others: `{xy_nm, angle}` |

### Manipulation Tools - Remove Item (1 step)

| Tool | Signature | Description |
|------|-----------|-------------|
| `remove_item_step_1` | `(item_ids: list[str]) -> str` | Removes items by their KIID values |

**Total: 13 MCP tools** (3 analyze + 10 manipulate)

---

## Supported Board Item Types

The protobuf type mapping supports 12 item types (with Group commented out as not yet in kipy):

| Type Name | Protobuf Class | KiCad Object Type | Required Args |
|-----------|---------------|-------------------|---------------|
| Arc | `board_types_pb2.Arc` | `KOT_PCB_ARC` | start, end, center, angle |
| BoardGraphicShape | `board_types_pb2.BoardGraphicShape` | `KOT_PCB_SHAPE` | shape |
| BoardText | `board_types_pb2.BoardText` | `KOT_PCB_TEXT` | text |
| BoardTextBox | `board_types_pb2.BoardTextBox` | `KOT_PCB_TEXTBOX` | textbox |
| Dimension | `board_types_pb2.Dimension` | `KOT_PCB_DIMENSION` | text, text_position |
| Field | `board_types_pb2.Field` | `KOT_PCB_FIELD` | name, text |
| Footprint3DModel | `board_types_pb2.Footprint3DModel` | None | filename, position, offset |
| FootprintInstance | `board_types_pb2.FootprintInstance` | `KOT_PCB_FOOTPRINT` | position, definition |
| Net | `board_types_pb2.Net` | None | code, name |
| Pad | `board_types_pb2.Pad` | `KOT_PCB_PAD` | type |
| Track | `board_types_pb2.Track` | `KOT_PCB_TRACE` | start, end |
| Via | `board_types_pb2.Via` | `KOT_PCB_VIA` | position |
| Zone | `board_types_pb2.Zone` | `KOT_PCB_ZONE` | name, layers, outline |

---

## Flow Manager Workflows

### Create Item Workflow
```
create_item_step_1()           --> list of types (Arc, Track, Via, ...)
create_item_step_2(type)       --> field schema from protobuf descriptor
create_item_step_3(type, args) --> board.create_items(wrapper) --> item_id
                                   [then: get_board_status for verification]
```

### Edit Item Workflow
```
edit_item_step_1()               --> list of types
edit_item_step_2(type)           --> {args: schema, item_list: {id: item}}
edit_item_step_3(item_id, args)  --> updates proto fields via CopyFrom, board.update_items()
                                     [then: get_board_status for verification]
```

### Move Item Workflow
```
move_item_step_1()               --> list of types
move_item_step_2(type)           --> {id: item} for chosen type
move_item_step_3(item_id, args)  --> offset position/angle, board.update_items()
                                     [then: get_board_status for verification]
```

The `get_board_status` tool (with screenshot) is intended to be called before and after each action for visual verification, creating a pre/post comparison loop.

---

## IPC-API Integration Details

### Connection Model
- Each tool invocation calls `KiCad().get_board()` to get a fresh board reference
- No persistent connection caching between calls (each call re-initializes)
- The `initialize_kicad()` / `initialize_board()` method is called before every tool execution via the `add_tool` wrapper

### Protobuf Handling
The `convert_proto.py` module provides the bridge between string type names and protobuf:
- **Type registry** (`KICAD_TYPE_MAPPING`): Maps string names to proto class, wrapper class, and KiCadObjectType enum
- **Schema introspection** (`convert_proto_to_dict`): Recursively walks protobuf descriptors to generate JSON-like schema dicts, including nested messages and enums
- **Object construction** (`convert_to_object`): Recursively builds protobuf messages from plain dicts, handling nested messages, repeated fields, and enums

### KiCad Version Compatibility
- Targets KiCad 9.0.0+ (IPC-API was introduced in KiCad 9)
- Has workarounds for missing `get_items_by_id` in KiCad <9.0.4 (manually iterates all items)
- Comments indicate future features expected in 9.0.4+

---

## Screenshot Pipeline

```
board.name --> PCB_PATHS env lookup --> .kicad_pcb file path
    --> kicad-cli pcb export svg (subprocess, layers: F.Cu, B.Cu, F.SilkS, B.SilkS, F.Mask, B.Mask)
    --> cairosvg.svg2png()
    --> PIL Image.convert('RGB').save(JPEG)
    --> base64 encode
    --> MCP ImageContent response
```

The screenshot requires:
1. `KICAD_CLI_PATH` env var pointing to the kicad-cli binary
2. `PCB_PATHS` env var with comma-separated .kicad_pcb file paths
3. Board name must match a filename in PCB_PATHS

---

## Code Quality Assessment

### Strengths

1. **Official IPC-API usage**: Uses KiCad's sanctioned integration path (`kicad-python`/kipy), which is the most forward-compatible approach. Other projects parse .kicad_pcb files directly.

2. **Visual verification loop**: The `get_board_status` screenshot before/after pattern gives the AI visual feedback, a significant advantage for spatial reasoning about PCB layouts.

3. **Progressive discovery**: The 3-step flow pattern lets the AI discover available types and schemas before committing to an action, reducing errors from incorrect parameters.

4. **Protobuf schema introspection**: Automatically generates argument schemas from protobuf descriptors rather than hardcoding them, meaning new KiCad types are partially supported automatically.

5. **Real-time interaction**: Because it talks to a running KiCad instance, changes appear immediately in the KiCad GUI - the user can watch the AI work.

6. **Graceful shutdown**: Comprehensive signal handling and cleanup registry for server lifecycle.

### Weaknesses

1. **No schematic support**: Schematic module directories exist but are empty stubs. Only PCB board manipulation is implemented.

2. **No persistent board reference**: Every tool call re-creates `KiCad().get_board()`. This is wasteful and could cause issues if the board state changes between the init and the actual operation.

3. **State leakage via instance variables**: `EditItemFlowManager` and `MoveItemFlowManager` store `self.item_type_cache` between step 2 and step 3 calls. If the AI calls step 3 without step 2, or interleaves calls between different flow managers, this will break silently.

4. **Single-item operations only**: TODOs explicitly note that batch editing/moving is not yet supported. Each item must be moved/edited individually, which is very slow for complex layouts.

5. **Requires running KiCad**: Cannot work on .kicad_pcb files offline. KiCad must be open with IPC server enabled, which limits headless/CI usage.

6. **Hardcoded screenshot layers**: The SVG export always uses the same 6 layers. No way to customize which layers appear in the screenshot.

7. **Test coverage is minimal**: Single test that only checks `create_server()` returns a non-None object with a `run` method. No tool execution tests.

8. **MCP tool registration is hacky**: Directly accesses `self.mcp._tool_manager._tools` (private attribute) to register tools, bypassing the public API. This will break on MCP SDK updates.

9. **No error recovery in flows**: If step 3 of a flow fails, there's no rollback or retry guidance. The `next_action` metadata always points forward.

10. **Dead code**: `jpg_path_2 = 'test.jpg'` in kicad_cli.py, unused `pprint` import, stub cleanup handlers that log but do nothing.

11. **No DRC/ERC integration**: Cannot run design rule checks or electrical rule checks.

12. **No netlist or footprint library support**: Cannot search footprint libraries, cannot work with netlists or BOMs.

---

## File Structure

```
kicad-mcp-python/
  main.py                          # Entry point: create_server().run(stdio)
  pyproject.toml                   # Poetry config, deps
  kicad-python/                    # Git submodule (kipy - KiCad IPC-API)
  kicad_mcp_python/
    __init__.py                    # Version only
    server.py                      # FastMCP creation, cleanup registry, signal handling
    core/
      mcp_manager.py               # ToolManager + ResourceManager base classes
      ActionFlowManager.py         # Multi-step wizard pattern, extends ToolManager
    pcb/
      pcbmodule.py                 # PCBTool base class (board init via kipy)
      tools/
        __init__.py                # Exports ManipulationTools, AnalyzeTools
        analyze_tool.py            # BoardAnalyzer: get_board_status, get_items_by_type, get_item_type_args_hint
        manipulate_tool.py         # Create/Edit/Move/Remove FlowManagers (10 tools)
      prompts/__init__.py          # Empty stub
      resources/__init__.py        # Empty stub
    schematic/                     # Empty stubs (future)
      tools/__init__.py
      prompts/__init__.py
      resources/__init__.py
    utils/
      convert_proto.py             # Protobuf <-> dict conversion, type registry, schema introspection
      kicad_cli.py                 # KiCadPCBConverter: SVG export via kicad-cli, convert to JPG
    tests/
      test_server.py               # Single smoke test
```

---

## Summary

Finerestaurant/kicad-mcp-python is the only KiCad MCP server that uses the **official IPC-API** (via `kicad-python`/kipy), which communicates with a running KiCad instance over protobuf. This gives it real-time board manipulation and visual feedback (screenshots) that file-parsing approaches cannot match. The multi-step flow manager pattern is a thoughtful UX design that guides the AI through complex operations.

However, it is early-stage (v0.1.0) with significant gaps: no schematic support, no DRC/ERC, no footprint library search, minimal tests, and some architectural fragilities (state leakage, private API access). The requirement for a running KiCad instance with IPC server enabled limits its use cases compared to file-based approaches.

**Best suited for**: Interactive PCB manipulation where visual verification matters and KiCad is already running.
**Not suited for**: Headless/CI workflows, schematic work, or large-scale batch operations.
