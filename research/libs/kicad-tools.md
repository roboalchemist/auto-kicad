# kicad-tools Analysis Report

## Overview

**Repository**: https://github.com/rjwalters/kicad-tools
**Author**: RJ Walters
**License**: MIT
**Version**: 0.10.3 (Beta)
**Python**: 3.10+
**Build**: hatchling
**Package manager**: uv

kicad-tools is the most comprehensive KiCad automation library found in this survey. It is explicitly designed for AI agent integration, providing structured data access, machine-readable JSON output, programmatic modification of KiCad files, and a purpose-built LLM reasoning interface for PCB layout decisions. It requires no running KiCad instance.

## Architecture

### Scale

- **~216K lines of Python** across 527+ source files in 40+ subpackages
- **231 test files**
- Uses Loom orchestration framework for AI-powered development (8 agent roles: Builder, Judge, Curator, Architect, Hermit, Doctor, Guide, Driver)

### Core Layer: S-Expression Engine (`sexp/`)

The foundation is a custom S-expression parser with:
- `SExp` class using `__slots__` for memory efficiency
- Round-trip editing with format preservation (parse -> modify -> serialize)
- XPath-like queries (`find_all`, `find`, bracket notation `doc["property", "Value"]`)
- Position tracking (line/column) for error reporting
- Pre-compiled character sets for performance
- `Document` wrapper for file-level operations

File I/O is in `core/sexp_file.py` with `load_schematic()`, `load_pcb()`, `load_symbol_lib()`, `save_*()` functions.

### Schema Layer (`schema/`)

Dataclass-based models parsed from S-expressions:

| Model | File | Key Fields |
|-------|------|------------|
| `Schematic` | `schematic.py` | symbols, wires, labels, sheets, title_block, hierarchy |
| `PCB` | `pcb.py` | layers, nets, footprints (with pads), traces, vias, zones |
| `SymbolInstance` | `symbol.py` | reference, value, lib_id, position, properties |
| `BOM` / `BOMItem` | `bom.py` | Bill of materials extraction |
| `Label` / `GlobalLabel` / `HierarchicalLabel` | `label.py` | Net connectivity |
| `Wire` / `Junction` | `wire.py` | Wiring elements |
| `Pad` | `pcb.py` | number, type, shape, position, size, layers, net |

Both `Schematic` and `PCB` support `.load()` / `.save()` class methods plus `from_sexp()` parsing.

### Query Layer (`query/`)

Fluent query API:
```python
sch.symbols.by_reference("U1")
sch.symbols.filter(value="100nF")
pcb.footprints.smd()
```

## Supported KiCad File Formats

| Format | Extension | Read | Write | Notes |
|--------|-----------|------|-------|-------|
| Schematic | `.kicad_sch` | Yes | Yes | Full round-trip, hierarchy traversal |
| PCB | `.kicad_pcb` | Yes | Yes | Full round-trip, layer/net/trace/zone support |
| Symbol Library | `.kicad_sym` | Yes | Yes | Create/edit symbols programmatically |
| Footprint | `.kicad_mod` | Yes | Yes | Parametric generators for common packages |
| Project | `.kicad_pro` | Yes | Yes | Unified project management |
| DRC Report | `.rpt` | Yes | No | Parses kicad-cli DRC output |
| ERC Report | `.rpt` | Yes | No | Parses kicad-cli ERC output |

KiCad 8.0+ file format targeted.

## Parsing Approach

All KiCad files use S-expression format. The parser:
1. Tokenizes input into atoms (strings, numbers, symbols) and parenthesized lists
2. Builds an `SExp` tree preserving original formatting for round-trip fidelity
3. Schema classes extract typed fields from the tree via `from_sexp()` factory methods
4. Modifications update the tree in-place, then serialize back preserving whitespace

## Analysis Capabilities

### Built-in Analysis Modules

| Module | Capability |
|--------|-----------|
| `analysis/complexity.py` | Circuit complexity metrics |
| `analysis/congestion.py` | Routing congestion analysis |
| `analysis/signal_integrity.py` | Signal integrity checks |
| `analysis/thermal.py` | Thermal analysis |
| `analysis/trace_length.py` | Trace length analysis |
| `analysis/net_status.py` | Net connectivity status |
| `validate/` | Pure Python DRC (no kicad-cli), netlist sync, connectivity, BOM placement |
| `drc/` | Parse kicad-cli DRC reports |
| `erc/` | Parse kicad-cli ERC reports |
| `explain/` | Human-readable explanations (16 files) |
| `audit/` | Design audit tools |

### CLI Analysis Commands

- `kct symbols` - List/filter symbols
- `kct nets` - Trace and analyze nets
- `kct bom` - Generate bill of materials
- `kct erc` - Run electrical rules check
- `kct drc` - Run design rules check (requires kicad-cli)
- `kct check` - Pure Python DRC (no kicad-cli)
- `kct placement` - Detect and optimize placement

## Manipulation Capabilities

### Schematic Manipulation

- Add/modify/remove symbols, wires, labels
- Hierarchical sheet management
- Circuit blocks system for reusable subcircuits (see below)
- Symbol library creation/editing

### PCB Manipulation

- Move/rotate components (`kicad-pcb-modify`)
- Add/remove traces, vias, zones
- Autorouting (A* pathfinding)
- Trace optimization (path shortening, via reduction)
- Placement optimization (physics-based + evolutionary)
- Zone filling
- Layout preservation for regeneration

### Circuit Blocks (`schematic/blocks/`)

Pre-built reusable circuit blocks -- a major differentiator:

| Category | Blocks |
|----------|--------|
| Power | LDO, Buck converter, barrel jack, USB power, battery, voltage divider, decoupling |
| MCU | MCU with bypass caps, reset button, boot mode selector |
| Timing | Crystal oscillator, MCLK oscillator |
| Interface | USB (Type-C, Micro-B), SWD/JTAG/Tag-Connect debug headers, I2C pullups, CAN transceiver |
| Analog | Op-amp (buffer/gain), ADC input filter, voltage/temperature sense |
| Motor | Half-bridge, three-phase inverter, current sense, gate driver |
| Protection | ESD, fuse, PTC, reverse polarity, overvoltage clamp, thermal cutoff |
| Indicators | LED with current-limiting resistor |

Each block has typed ports (`PowerPort`, `DataPort`) and a connection validator.

### Footprint Generation (`library/`)

Parametric generators: `create_soic`, `create_qfp`, `create_qfn`, `create_sot`, `create_chip`, `create_dip`, `create_pin_header` with IPC-7351 naming.

### Manufacturing Export (`export/`)

- Gerber files
- BOM (CSV, grouped)
- Assembly/CPL files
- Manufacturer-specific profiles: JLCPCB, OSHPark, PCBWay, Seeed

## AI-Agent Design Patterns

### 1. MCP Server (`mcp/`)

Full Model Context Protocol server (32 source files) using `fastmcp`:
- **Transport**: stdio (Claude Desktop) or HTTP
- **Tools**: `analyze_board`, `get_drc_violations`, `measure_clearance`, `export_gerbers`, `export_bom`, `export_assembly`, `placement_analyze`, `placement_suggestions`, `start_session`, `query_move`, `apply_move`, `commit`, `rollback`, `route_net`, `get_unrouted_nets`
- **Session management**: Stateful sessions with checkpoint/rollback
- **Preference learning**: `PreferenceLearner` that tracks agent decisions and learns patterns
- **Decision tracking**: Records and annotates design decisions for audit trail
- **Tool registry**: Plugin-style tool registration via `TOOL_REGISTRY`

### 2. LLM Reasoning Agent (`reasoning/`)

Purpose-built chain-of-thought reasoning loop:

```
LLM (Strategy) -> Command Interpreter -> PCB Tools (Execution) -> Feedback (Diagnosis)
```

- `PCBReasoningAgent`: Main orchestrator with `get_state()`, `execute()`, `diagnose()`, `is_complete()`, `save()`
- `PCBState`: Complete board state serializable to prompt text
- `CommandInterpreter`: Translates natural language intent to geometric operations
- `DiagnosisEngine`: Generates structured feedback when operations fail
- **Commands**: `PlaceComponentCommand`, `RouteNetCommand`, `DeleteTraceCommand`, `AddViaCommand`, `DefineZoneCommand`
- **Vocabulary**: Typed spatial/routing concepts (`SpatialRegion`, `SpatialRelation`, `NetType`, `ComponentGroup`, `RoutingPriority`)
- **Progress tracking**: `AgentProgress` with routing progress and violation improvement metrics

### 3. Machine-Readable Output

All CLI commands support `--format json` for automation pipelines.

### 4. Intent System (`intent/`)

10 files for parsing design intent from natural language descriptions.

### 5. Constraints System (`constraints/`)

Multi-stage optimization locking with `ConstraintManager`, `LockType`, and violation detection -- supports iterative AI workflows where early decisions are locked while later stages optimize.

## Router Architecture (`router/`)

The largest subpackage (55 files) with a sophisticated autorouter:

| Component | Description |
|-----------|-------------|
| `core.py` | `Autorouter` and `AdaptiveAutorouter` |
| `pathfinder.py` | A* algorithm with `Router` class |
| `grid.py` / `adaptive_grid.py` / `subgrid.py` | Multi-resolution routing grids |
| `heuristics.py` | Pluggable: Manhattan, DirectionBias, CongestionAware, WeightedCongestion, Greedy |
| `net_class.py` | Auto-classify nets (power, clock, audio, digital, high-speed) |
| `diffpair.py` | Differential pair routing |
| `bus.py` | Bus signal routing |
| `escape.py` / `fine_pitch.py` | Dense/fine-pitch package escape routing |
| `parallel.py` | Parallel routing for independent net groups |
| `optimizer/` | Trace optimization (path shortening, via reduction) |
| `global_router.py` | Hierarchical global routing |
| `sparse.py` | Sparse routing graph for performance |
| `zones.py` | Zone filling with thermal relief |
| `layers.py` | Multi-layer support with via management |
| `cache.py` | Routing result caching |
| `cpp_backend.py` | Optional C++ acceleration via nanobind |
| `tuning.py` | Cost parameter auto-tuning |
| `analysis.py` / `failure_analysis.py` | Root cause analysis for routing failures |
| `placement_feedback.py` | Feedback loop between placement and routing |

## Placement Optimization (`optim/`)

20 files with multiple strategies:
- Force-directed physics simulation
- Evolutionary/genetic algorithm (via `cmaes` library)
- Bayesian optimization (optional, via `ax-platform`/`botorch`)
- Hybrid: evolutionary global search + physics refinement

## Hardware Acceleration (`acceleration/`)

Optional GPU acceleration:
- **CUDA**: `cupy-cuda12x` for NVIDIA GPUs
- **Metal**: `mlx` for Apple Silicon
- Kernels for: routing, placement, evolutionary optimization, signal integrity
- Auto-detection of available backends

## Dependencies

### Required
- `rich` >= 13.0 (CLI formatting)
- `numpy` >= 1.24 (router/optimization)
- `pydantic` >= 2.0 (data validation)
- `pyyaml` >= 6.0 (config)
- `cmaes` >= 0.12.0 (evolutionary optimization)

### Optional Extras
- `[drc]`: rtree (spatial indexing)
- `[parts]`: requests (LCSC API)
- `[datasheet]`: markitdown, pdfplumber, PyMuPDF (PDF parsing)
- `[mcp]`: fastmcp (MCP server)
- `[native]`: nanobind, scikit-build-core, cmake, ninja (C++ router)
- `[cuda]`: cupy-cuda12x (NVIDIA GPU)
- `[metal]`: mlx (Apple Silicon GPU)
- `[visualization]`: matplotlib
- `[bayesian]`: ax-platform, botorch (Bayesian optimization)

### Dev
- pytest, pytest-cov, pytest-benchmark, ruff, mypy

## Code Quality

### Strengths
- Comprehensive type hints with mypy checking
- Pydantic models for validation
- ruff for linting and formatting
- pytest with coverage, benchmarks, and timeout markers
- `__slots__` optimization on hot-path classes
- Well-organized module structure with clear `__init__.py` exports
- Extensive docstrings with usage examples
- 231 test files

### Concerns
- **Massive codebase** (216K lines) -- potentially over-engineered for a single-developer project
- Built entirely by AI agents (Loom orchestration) -- quality of individual implementations may vary
- Some module duplication: `optim/` vs `optimize/`, `operations/` vs `pcb/`
- 40+ subpackages creates navigation complexity
- Beta status (0.10.x) despite enormous scope

## Strengths

1. **Best-in-class AI integration**: MCP server, LLM reasoning agent, intent parsing, constraint locking, preference learning -- no other KiCad library comes close
2. **Comprehensive file format support**: Read/write for all major KiCad file types with round-trip fidelity
3. **Circuit blocks**: Reusable, parameterized subcircuit abstractions (power, MCU, interfaces, protection, motor control)
4. **Full PCB workflow**: From schematic creation through routing, DRC, placement optimization, to manufacturing export
5. **Pure Python DRC**: Design rule checking without kicad-cli dependency
6. **Parametric footprint generators**: IPC-7351 compliant footprint creation
7. **Hardware acceleration**: Optional CUDA/Metal GPU support
8. **Machine-readable output**: JSON output on all CLI commands

## Weaknesses

1. **Enormous scope risk**: 216K lines is very ambitious for a beta library; breadth may come at the cost of depth/reliability in individual modules
2. **AI-generated codebase**: Built using Loom agent orchestration -- individual module quality may be inconsistent
3. **Heavy dependency tree**: Required deps include numpy, pydantic, cmaes; optional deps span CUDA, Metal, ML frameworks
4. **Router complexity**: 55-file router package is complex; unclear how well the A* autorouter performs vs commercial tools
5. **Documentation lives in code**: No separate documentation site; README is comprehensive but the 40+ module structure needs a guide
6. **No PyPI download metrics visible**: Unclear adoption level
7. **Single maintainer**: Bus factor of 1

## Relevance to auto-kicad

**High relevance**. kicad-tools is the closest existing project to what auto-kicad aims to build. Key areas of interest:

- **S-expression parser**: The round-trip-preserving parser is directly reusable
- **MCP server pattern**: The tool registry, session management, and preference learning patterns are worth studying
- **Reasoning agent architecture**: The LLM strategy -> command interpreter -> execution -> diagnosis feedback loop is a proven pattern
- **Circuit blocks**: The reusable subcircuit abstraction is a compelling feature for AI-assisted design
- **Constraint locking**: Multi-stage optimization with locked constraints enables iterative AI workflows
- **Router as reference**: Even if not directly reused, the router architecture shows what's possible in pure Python
