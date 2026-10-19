# SKiDL - Analysis Report

## Overview

SKiDL is a Python package for describing electronic circuits programmatically instead of using graphical schematic editors. Users write Python scripts that instantiate parts, create nets, and connect components. SKiDL then outputs netlists for PCB layout tools, primarily KiCad. It is essentially "infrastructure as code" for electronics design.

- **Version**: 2.2.1
- **Author**: Dave Vandenbout
- **License**: MIT
- **Python**: 3.6+
- **Status**: Production/Stable (PyPI)
- **Repository**: github.com/devbisme/skidl
- **Core codebase**: ~31,800 lines of Python (excluding ~225 auto-generated library files totaling ~800K lines)

## Architecture

### Module Structure

```
src/skidl/
  __init__.py          # Public API exports
  skidl.py             # Global entry point (default circuit, config)
  circuit.py           # Circuit container (parts, nets, buses)
  part.py              # Part class (component instantiation)
  pin.py               # Pin class (connection points, drive types)
  net.py               # Net class (electrical connections)
  bus.py               # Bus class (grouped nets)
  network.py           # Series/parallel network operators (& and |)
  node.py              # Hierarchical grouping (SubCircuit, Group)
  interface.py         # Interface class (bundled nets/buses for subsystem I/O)
  schlib.py            # Library loading and caching
  config_.py           # Configuration management (.skidlcfg JSON)
  erc.py               # Electrical Rules Checking
  design_class.py      # PartClass / NetClass for design rule properties
  part_query.py        # Part search and footprint search (~915 lines)
  netlist_to_skidl.py  # Reverse conversion: KiCad netlist -> SKiDL script
  pyspice.py           # SPICE simulation integration via InSpice
  geometry.py          # BBox, Point, Segment, Tx, Vector for layout
  schematics/          # Auto-placement and routing for schematic generation
    place.py           # Autoplacer for symbol arrangement
    route.py           # Autorouter for schematic wires
    net_terminal.py    # Net terminal symbols
    sch_node.py        # Schematic node representation
  tools/               # Backend modules for different ECAD tools
    kicad5/            # KiCad 5 backend
    kicad6/            # KiCad 6 backend
    kicad7/            # KiCad 7 backend
    kicad8/            # KiCad 8 backend
    kicad9/            # KiCad 9 backend
    skidl/             # Native SKiDL format + 225 pre-built Python libs
    spice/             # SPICE backend
  scripts/             # CLI entry points
    netlist_to_skidl_main.py  # netlist_to_skidl CLI
    part_search_cli.py        # skidl-part-search CLI
```

### Design Pattern

SKiDL uses a **global default circuit** pattern via Python builtins:
- `builtins.default_circuit` holds the active Circuit instance
- `builtins.NC` is the global no-connect net
- Module-level functions like `generate_netlist()`, `ERC()`, `reset()` delegate to `default_circuit`
- Circuit supports context manager protocol (`with Circuit() as ckt:`) for isolated circuits

The tool/backend system is plugin-based — each KiCad version and SPICE are separate directories under `tools/` that are auto-discovered at import time. Each backend registers itself with a library suffix and module reference.

## Circuit Design API

### Part

The core class for electronic components. Three destination modes:
- **NETLIST**: Part becomes part of the circuit (default)
- **TEMPLATE**: Part used as a template for copying (`dest=TEMPLATE`)
- **LIBRARY**: Part stored in a library

```python
# Basic instantiation
r1 = Part("Device", "R", value="1K", footprint="R_0805")

# Template + instantiation
r = Part("Device", "R", dest=TEMPLATE)
r1, r2, r3 = r(3, value="10K")  # Create 3 copies

# Pin access
r1[1]           # By number
r1["A"]         # By name
r1.p            # PinNumberSearch helper
r1.n            # PinNameSearch helper
```

Parts support multi-unit components (e.g., op-amps with multiple units in one package).

### Net

Represents electrical connections between pins. Key features:
- Named or auto-named (prefix `N$`)
- Drive strength tracking (NONE through POWER)
- Net class assignment for PCB routing rules
- Multi-segment nets that auto-merge when connected
- `+=` operator for connecting pins

```python
vcc = Net("VCC")
gnd = Net("GND")
vcc += r1[1], mcu["VCC"]
```

### Bus

Groups of related nets for multi-bit signals:

```python
data = Bus("DATA", 8)      # 8-bit bus
data[0] += some_pin         # Individual net access
data[7:0]                   # Slicing
```

### Network (Series/Parallel Operators)

Unique feature: algebraic circuit notation using `&` (series) and `|` (parallel):

```python
vin & r1 & vout & r2 & gnd           # Series voltage divider
vin & (r1 | r2) & gnd                 # Parallel resistors
a & r1 & q1["B C"] & r4 & q2["B C"]  # Multi-pin series chain
```

The `tee()` function creates T-connections within series chains.

### Pin

Detailed pin type system with 14 types (INPUT, OUTPUT, BIDIR, TRISTATE, PASSIVE, PWRIN, PWROUT, etc.) and 8 drive levels (NOCONNECT through POWER). Pin conflict checking uses a matrix of type interactions.

### Hierarchical Design

Three mechanisms for hierarchy:

1. **SubCircuit decorator**: Functions decorated with `@SubCircuit` create hierarchical blocks
2. **Group**: Context manager for grouping components
3. **Interface**: Bundles nets/buses/pins for standardized subsystem connections

```python
@SubCircuit
def voltage_regulator(vin, vout, gnd):
    reg = Part("Regulator_Linear", "AMS1117-3.3")
    vin += reg["VIN"]
    vout += reg["VOUT"]
    gnd += reg["GND"]
```

## Library Management

### SchLib Class

- Loads component libraries from KiCad `.kicad_sym` files (or legacy `.lib`)
- Caching system: in-memory dict cache + optional pickle serialization to disk
- Library search paths configurable via `.skidlcfg` JSON files
- Search paths cascade: `/etc/`, `~/.local/share/skidl/` (or platform equivalent), `./`

### Part Search

Two CLI tools provided:
- `netlist_to_skidl`: Convert KiCad netlist to SKiDL Python script
- `skidl-part-search`: Search across all KiCad libraries for parts by name/description

### Built-in SKiDL Libraries

225 pre-generated Python library files under `tools/skidl/libs/` containing parts as Python objects. These are native SKiDL-format libraries covering standard KiCad component families (74xx, amplifiers, connectors, etc.).

## Netlist Generation

Each KiCad version backend provides:
- `gen_netlist.py` — Generate `.net` netlist file (KiCad S-expression format using `simp_sexp`)
- `gen_xml.py` — Generate XML netlist
- `gen_pcb.py` — Generate `.kicad_pcb` PCB file (delegates to `kinet2pcb` package)
- `gen_schematic.py` — Generate `.kicad_sch` schematic file
- `gen_svg.py` — Generate SVG schematic rendering
- `lib.py` — Library file parsing for that KiCad version
- `bboxes.py` — Bounding box data for symbol drawing

The PCB generation uses the external `kinet2pcb` package which takes a Circuit object and produces a KiCad PCB file directly (no intermediate netlist step needed).

## Electrical Rules Checking (ERC)

Three levels of ERC:

1. **Circuit-level** (`dflt_circuit_erc`): Merges multi-segment nets, runs net and part ERC on all elements
2. **Part-level** (`dflt_part_erc`): Checks for unconnected pins, incorrectly connected NOCONNECT pins
3. **Net-level** (`dflt_net_erc`): Checks pin count (0 or 1 pin nets), pin conflicts between connected pins, drive strength sufficiency

ERC is extensible — each Part, Net, and Circuit has an `erc_list` of check functions. Users can append custom checks or replace defaults. The `erc_assert()` function adds runtime assertions.

Pin conflict detection uses a drive-strength matrix comparing each pair of pins on a net against their type's `min_rcv` and `max_rcv` drive requirements.

## SPICE Simulation Integration

SKiDL integrates with SPICE simulation via:
- `InSpice` package (Python 3.11+, successor to PySpice)
- `from skidl.pyspice import *` reconfigures SKiDL for SPICE mode
- Sets default tool to SPICE, loads PySpice part library
- All SPICE parts injected into module namespace for easy instantiation
- Ground net `gnd = Net("0")` auto-created with fixed name

## Schematic Auto-Generation

The `schematics/` subpackage provides experimental auto-placement and routing:
- **Autoplacer** (`place.py`): Arranges part symbols in a schematic layout
- **Autorouter** (`route.py`): Routes wires between placed symbols
- Uses `geometry.py` for spatial calculations (BBox, Point, Segment, Tx transforms)
- Generates KiCad schematic files or SVG output

## Dependencies

| Package | Purpose |
|---------|---------|
| `kinet2pcb >= 1.1.4` | Direct Circuit-to-PCB generation |
| `simp_sexp >= 0.3.0` | S-expression parsing/generation (KiCad file format) |
| `inspice` | SPICE simulation (Python 3.11+ only) |
| `ply` | Parser generator (for library parsing) |
| `rich` | Terminal output formatting |
| `graphviz` | Circuit graph visualization |
| `deprecation` | API deprecation warnings |

## Code Quality

### Strengths
- Comprehensive docstrings throughout the codebase
- Well-structured class hierarchy with clear separation of concerns
- Extensive pin type and drive strength modeling
- Plugin architecture for tool backends supports KiCad 5-9 + SPICE
- The series/parallel Network operator (`&`, `|`) is genuinely innovative for circuit description
- Reverse conversion (netlist-to-SKiDL) enables migration from schematic-based workflows
- Part template system with copy semantics enables clean parametric design
- Context manager support for isolated circuits
- Platform-aware configuration (XDG on Linux, Library/Application Support on macOS, AppData on Windows)

### Weaknesses
- Very large codebase (~32K lines core + ~800K generated) for what it does
- Global state via `builtins.default_circuit` is fragile and non-thread-safe
- Heavy code duplication across KiCad version backends (kicad5-9 are largely copy-pasted)
- The `future` library import with try/except suggests legacy Python 2 compatibility baggage
- Auto-generated library files (225 Python files) inflate package size significantly
- Schematic auto-generation (placement/routing) is experimental and complex
- Part search requires building a local database — not instant
- SPICE integration limited to Python 3.11+ via InSpice

### LLM Compatibility Assessment
- **High**: The Python-based circuit description is very LLM-friendly — circuits are just code
- **High**: Clear API with consistent patterns (`Part()`, `Net()`, `+=`, `&`)
- **Medium**: Library names must be exact strings matching KiCad libraries
- **Medium**: Complex operator overloading (`&`, `|`, `+=`) may confuse LLMs unfamiliar with SKiDL
- **Low risk**: The global default_circuit pattern means most simple scripts "just work" without explicit Circuit management

## Key Insights for kicad-agent

1. **SKiDL's API is the gold standard for programmatic circuit description** — its Part/Net/Bus model with operator overloading is clean and Pythonic
2. **The series/parallel operators (`&` and `|`) are uniquely powerful** for expressing circuit topology concisely
3. **The template/copy pattern** (`dest=TEMPLATE`, `r(5)` to make 5 copies) is essential for parametric design
4. **ERC is built-in and extensible** — not an afterthought
5. **PCB generation goes through `kinet2pcb`** — SKiDL itself only generates netlists; the PCB step needs an external dependency
6. **Netlist-to-SKiDL conversion** means existing KiCad designs can be imported and modified programmatically
7. **The backend duplication problem** (kicad5 through kicad9 are near-identical) suggests that version-specific backends could be better abstracted
8. **225 pre-built Python component libraries** means SKiDL ships a large subset of KiCad's component database in Python form
