# kicad-footprint-generator Analysis

## Overview

**Repository**: pointhi/kicad-footprint-generator (now at gitlab.com/kicad/libraries/kicad-footprint-generator)
**License**: GNU GPLv3+
**Version**: 1.1.2
**Author**: Thomas Pointhuber
**Python**: 2.7 and 3.3+
**Dependencies**: `future`, `pyyaml`

A Python framework (`KicadModTree`) for programmatically generating KiCad footprint files (`.kicad_mod`), plus ~204 generator scripts covering ~45 component categories. A large portion of the official KiCad footprint library was built with this tool.

## Architecture

### Core Design: Scene Graph / Render Tree

The framework follows a **scene-graph pattern** inspired by scripted CAD systems (like OpenSCAD). Everything is a `Node` that forms a tree structure. When serialized, the tree is flattened: specialized nodes decompose into base nodes, and only base nodes are written to the output file.

```
Footprint (root)
  +-- Text (reference)
  +-- Text (value)
  +-- Translation
  |     +-- PadArray  --> [virtual children: Pad, Pad, Pad...]
  +-- RectLine        --> [virtual children: Line, Line, Line, Line]
  +-- ExposedPad      --> [virtual children: Pad (main), Pad (vias), Pad (paste)...]
  +-- Model
```

### Node Hierarchy

**Base class**: `Node` (`KicadModTree/nodes/Node.py`)
- Parent/child tree with `append()`, `extend()`, `remove()`, `insert()`
- Enforces single-parent constraint (no DAG, raises `MultipleParentsError`)
- `serialize()` recursively flattens tree to list of leaf nodes
- `getRealPosition()` walks up tree to apply accumulated transformations
- `calculateBoundingBox()` computes axis-aligned bounding box
- `getRenderTree()` / `getCompleteRenderTree()` for debug visualization
- `copy()` via deepcopy with parent detachment

**Root node**: `Footprint` (`nodes/Footprint.py`)
- Properties: `name`, `description`, `tags`, `attribute`, `maskMargin`, `pasteMargin`, `pasteMarginRatio`
- Defines render order for serialized output

**Base nodes** (directly serialized to `.kicad_mod`):
| Node | File | Purpose |
|------|------|---------|
| `Pad` | `nodes/base/Pad.py` | Pads (THT, SMT, NPTH, connect); supports circle/oval/rect/roundrect/trapezoid/custom shapes |
| `Line` | `nodes/base/Line.py` | Line segments (fp_line) |
| `Arc` | `nodes/base/Arc.py` | Arc segments (fp_arc) |
| `Circle` | `nodes/base/Circle.py` | Circles (fp_circle) |
| `Polygon` | `nodes/base/Polygon.py` | Polygons (fp_poly) |
| `Text` | `nodes/base/Text.py` | Text labels (fp_text) - reference, value, user |
| `Model` | `nodes/base/Model.py` | 3D model references |

**Specialized nodes** (decompose to base nodes via `getVirtualChilds()`):
| Node | Purpose |
|------|---------|
| `Translation` | Applies x/y offset to all children via `getRealPosition()` override |
| `Rotation` | Applies rotation to all children |
| `RectLine` | Rectangle from 4 Lines |
| `RectFill` / `FilledRect` | Filled rectangles |
| `PolygoneLine` | Polyline from connected Line segments |
| `PadArray` | Linear array of Pads with configurable numbering, spacing, start/center, hidden/deleted pins, chamfered first/last |
| `ExposedPad` | Central thermal pad with via grid, paste subdivision, mask handling, bottom pad |
| `ChamferedPad` | Pad with chamfered corners (uses custom pad shape with polygon primitive) |
| `ChamferedPadGrid` | Grid of chamfered pads |
| `RingPad` | Ring-shaped pad |

### Key Design Patterns

1. **Virtual children**: Specialized nodes override `getVirtualChilds()` to return generated base nodes. The serializer only handles base node types, making the system extensible without touching serialization code.

2. **Coordinate transforms**: `Translation` and `Rotation` override `getRealPosition()` which is called during serialization to transform coordinates up the tree chain. This gives proper nested positioning.

3. **RoundRadiusHandler**: Utility class managing rounded rectangle radius calculation with support for ratio-based, maximum-limited, and exact radius specifications. Used by `Pad`, `ChamferedPad`, and `ExposedPad`.

### Data Types

**Vector2D** (`KicadModTree/Vector.py`):
- Flexible construction: `(x, y)`, `[x, y]`, `{'x':..., 'y':...}`, or another `Vector2D`
- Full arithmetic operators (`+`, `-`, `*`, `/`)
- `rotate()`, `round_to()`, `distance_to()`, `to_polar()`, `from_polar()`

**Vector3D** (extends Vector2D):
- Adds z coordinate for 3D model positioning
- `cross_product()`, `dot_product()`

### File Handler / Serialization

`KicadFileHandler` (`KicadModTree/KicadFileHandler.py`):
- Serializes the tree to KiCad's S-expression (sexpr) format
- `_serializeTree()` groups nodes by class name, orders them (Text reference/value first, then alphabetical, then Model last)
- Each base node type has a `_serialize_<Type>()` method
- `SexprSerializer` (in `kicad_util.py`) converts nested Python lists to sexpr strings with proper formatting and newlines
- Default layer widths: SilkS=0.12mm, Fab=0.10mm, CrtYd=0.05mm

**Important**: This serializer outputs **KiCad 5 format** (uses `module`, `fp_line`, `fp_arc` etc.). KiCad 6+ uses a different s-expression format with `footprint` keyword and different attribute names.

### Argument Parser

`ModArgparser` (`KicadModTree/ModArgparser.py`):
- Bridges YAML/CSV data files to generator functions
- Defines expected parameters with types, defaults, required flags
- YAML: root keys become the footprint `name`, child keys are parameters
- CSV: header row defines parameter names
- Calls the generator function once per footprint definition
- Can generate example YAML/CSV templates (`--print_yml`, `--print_csv`)

## YAML Configuration System

### Simple pattern (ModArgparser-based)

```yaml
# Root key = footprint name
L_TDK_SLF6025:
  description: "Inductor, TDK, SLF6025, 6.0mmx6.0mm"
  datasheet: "https://..."
  tags: "Inductor TDK_SLF6025"
  smd_tht: "smd"
  at: [-3.00, 3.00]
  size: [6.00, 6.00]
  pins: [["smd", "1", -2.75, 0, 1.5, 2.2, 0.0], ...]
```

### IPC-compliant pattern (Packages)

More structured YAML with toleranced dimensions for IPC-7351 pad calculations:

```yaml
FileHeader:
  library_Suffix: 'SO'
  device_type: 'SOIC'

SOIC-8_3.9x4.9mm_P1.27mm:
  size_source: 'JEDEC MS-012AA'
  body_size_x:
    nominal: 3.9
    tolerance: 0.1
  body_size_y:
    minimum: 4.8
    maximum: 5.0
  overall_size_x:
    minimum: 5.8
    maximum: 6.2
  lead_width:
    minimum: 0.31
    maximum: 0.51
  pitch: 1.27
  num_pins_x: 0
  num_pins_y: 4
```

Separate `ipc_definitions.yaml` contains IPC-7351 pad size calculation parameters (toe/heel/side extensions, courtyard) for three density levels (least/nominal/most).

## Generator Script Patterns

### Pattern 1: Simple (ModArgparser + YAML)
```python
from KicadModTree import *

def generate(args):
    kicad_mod = Footprint(args["name"])
    kicad_mod.setDescription(args["description"])
    # ... build footprint ...
    KicadFileHandler(kicad_mod).writeFile(args["name"] + ".kicad_mod")

parser = ModArgparser(generate)
parser.add_parameter("name", type=str, required=True)
# ... define parameters ...
parser.run()  # reads YAML/CSV from command line args
```

### Pattern 2: IPC-compliant (Packages)
```python
# Load IPC definitions, device YAML, calculate pad sizes per IPC-7351
# Uses helper libraries: ipc_pad_size_calculators, drawing_tools, etc.
class Gullwing():
    def calcPadDetails(self, device_dimensions, EP_size, ipc_data, ipc_round_base):
        # IPC-7351 formulas: Zmax, Gmin, Xmax with RSS tolerancing
        Gmin_x, Zmax_x, Xmax = ipc_gull_wing(ipc_data, ...)
```

### Usage
```bash
cd scripts/Inductor_SMD
python3 Inductor_SMD.py Inductor_SMD.yml
# Generates .kicad_mod files for each entry in the YAML
```

## Supported Component Categories (~45)

| Category | Examples |
|----------|---------|
| **Passives** | Resistors (SMD/THT), Capacitors (SMD/THT), Inductors (SMD/THT) |
| **IC Packages** | QFP, SOIC, SO, DFN, QFN, LGA, SON, BGA, DIP, PLCC, TO/SOT |
| **Connectors** | Pin headers, sockets, D-Sub, terminal blocks (Phoenix, WAGO, Altech, etc.) |
| **Discrete** | Diodes (SMD/THT), LEDs (SMD/THT), Fuses |
| **Electromechanical** | Buttons/switches, potentiometers, buzzers, crystals, oscillators |
| **Power** | Battery holders, DC-DC converters |
| **Mechanical** | Mounting holes, mounting hardware, shielding |

## Strengths

1. **Mature and battle-tested**: Used to generate a significant portion of KiCad's official footprint library. Extensive coverage of real-world components.

2. **Clean scene-graph architecture**: The node tree with virtual children is elegant -- specialized nodes compose from base nodes without touching serialization. Easy to create custom node types.

3. **IPC-7351 compliance**: The Packages scripts implement proper IPC pad size calculations with RSS tolerancing and three density levels. This is the gold standard for land pattern design.

4. **Data-driven**: YAML/CSV separation of data from code enables bulk generation -- add a new part by adding a YAML entry, not writing new code.

5. **Comprehensive pad support**: Handles roundrect, chamfered, custom-shape pads, exposed pads with thermal via grids and paste subdivision -- these are non-trivial features that many simpler tools lack.

6. **Coordinate transforms**: Translation/Rotation nodes enable grouped positioning, which is critical for complex footprints.

7. **Good test coverage**: Unit tests for vector math, node operations, pad shapes, rotations, exposed pads, and complete footprint generation.

## Weaknesses

1. **KiCad 5 format only**: The serializer outputs `module`/`fp_line`/`fp_arc` format. KiCad 6+ uses a different s-expression schema (`footprint` keyword, different attribute names, zone fill options). This is the most significant limitation for modern use.

2. **Python 2/3 dual support baggage**: Uses `from __future__ import division`, `from builtins import round`, `future` dependency. Modern Python-only code would be cleaner.

3. **No input/parsing**: This is a write-only framework. It cannot read existing `.kicad_mod` files. There's a basic S-expression parser (`parseLispString`) but it's not wired to construct a node tree from an existing file.

4. **Inconsistent script quality**: Some scripts (Packages) are IPC-compliant with proper calculations. Others (Inductor_SMD, connectors) use hardcoded dimensions from YAML without tolerance analysis. Quality varies significantly across the ~204 scripts.

5. **Global sys.path manipulation**: Generator scripts use `sys.path.append()` with relative paths to find the framework and shared tools. No proper packaging or entry points.

6. **Limited documentation**: Docstrings exist on core classes but many specialized features (ExposedPad paste grid options, ChamferedPad circle avoidance) are only documented in keyword argument lists.

7. **No KiCad Library Conventions (KLC) validation**: Generates footprints but doesn't validate compliance with KLC naming, silkscreen, courtyard, or fab layer rules.

8. **Spelling errors in API**: `_childs` (should be `_children`), `muliple` (multiple), some inconsistency in naming (camelCase vs snake_case).

## Key Files Summary

| Path | Purpose |
|------|---------|
| `KicadModTree/__init__.py` | Public API -- exports all nodes, FileHandler, ModArgparser |
| `KicadModTree/nodes/Node.py` | Base Node class with tree operations |
| `KicadModTree/nodes/Footprint.py` | Root Footprint node |
| `KicadModTree/nodes/base/Pad.py` | Pad node (415 lines, most complex base node) |
| `KicadModTree/nodes/specialized/PadArray.py` | Linear pad array with numbering/spacing |
| `KicadModTree/nodes/specialized/ExposedPad.py` | Thermal pad with vias/paste (568 lines) |
| `KicadModTree/nodes/specialized/ChamferedPad.py` | Chamfered corner pads |
| `KicadModTree/KicadFileHandler.py` | S-expression serializer for .kicad_mod |
| `KicadModTree/ModArgparser.py` | YAML/CSV data loading for generator scripts |
| `KicadModTree/Vector.py` | Vector2D/Vector3D math classes |
| `KicadModTree/util/kicad_util.py` | S-expression serializer, float formatting, string quoting |
| `KicadModTree/util/paramUtil.py` | Parameter parsing utilities |
| `scripts/Packages/ipc_definitions.yaml` | IPC-7351 pad calculation constants |
| `scripts/Packages/*/size_definitions/*.yaml` | Per-package-type device dimension databases |

## Relevance for kicad-agent

**High relevance**. This framework demonstrates:
- The complete data model needed for footprint generation (pads, lines, arcs, text, 3D models)
- How IPC-7351 calculations work for land pattern design
- The YAML-driven approach to component parameterization
- Handling of advanced pad types (roundrect, chamfered, custom shape, exposed with thermal vias)
- The s-expression output format for `.kicad_mod` files (though KiCad 5 format -- needs updating for KiCad 6+)

**Key takeaways for our generator**:
1. The node tree / virtual children pattern is worth adopting -- it cleanly separates geometry construction from serialization
2. IPC pad calculations from the Packages scripts should be referenced/ported
3. The YAML configuration pattern (device dimensions with tolerances) is the right data model
4. Need to generate KiCad 6+ format, not the KiCad 5 format this tool uses
5. The ExposedPad implementation with paste subdivision and via grid handling is the most sophisticated component and worth studying closely
