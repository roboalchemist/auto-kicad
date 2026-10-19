# KiCad Footprint Generation Tools & Scripts Research

## Executive Summary

KiCad footprint generation has multiple approaches ranging from GUI wizards to fully programmatic Python frameworks. The primary ecosystem revolves around **KicadModTree**, a Python library that programmatically creates `.kicad_mod` files (S-expression format). For batch operations and parametric design, **pointhi/kicad-footprint-generator** is the most mature and widely-used framework.

---

## Core Repositories & Tools

### 1. pointhi/kicad-footprint-generator
**Repository**: https://github.com/pointhi/kicad-footprint-generator
**Mirror (Official)**: https://gitlab.com/kicad/libraries/kicad-footprint-generator
**Documentation**: https://kicad-footprint-generator.readthedocs.io/

The de-facto standard for footprint generation. Used by KiCad's official library team.

**Key Components:**
- **KicadModTree library** - Core Python framework for programmatic footprint creation
- **scripts/** directory - Pre-built Python generators for hundreds of component types
- **YAML/TOML configs** - Parametric definitions for footprint families
- **Produces**: `.kicad_mod` files ready for use in KiCad

**What it can generate:**
- SMD passive components (R, L, C in various sizes)
- IC packages (BGA, QFP, DIP, TQFP, LQFP, SOIC, etc.)
- Connectors (headers, USB, D-Sub, RJ45, etc.)
- Specialized components (crystals, transformers, antennas)
- Custom geometry through parametric definitions

**Example workflow:**
```bash
git clone https://github.com/pointhi/kicad-footprint-generator.git
cd kicad-footprint-generator/scripts
# Find or create YAML config for your component
python3 generate_footprints.py <your-config>.yaml
# Output: .kicad_mod files in output/ directory
```

**Strengths:**
- Mature, production-tested (used for KiCad official libraries)
- Extensive existing generators as examples
- Excellent documentation
- Highly parametric and extensible
- S-expression native (no conversion needed)

---

### 2. KiCad/kicad-footprint-wizards
**Repository**: https://github.com/KiCad/kicad-footprint-wizards
**Status**: Official KiCad project

Interactive GUI-based footprint generation built into KiCad's PCBNew.

**Features:**
- Launch from PCBNew's "Footprint Wizard" plugin system
- Python-based plugin architecture
- Generators for common components:
  - BGA packages
  - QFP packages
  - DIP packages
  - Generic pads and pad arrays
  - SMD components

**When to use:**
- One-off footprint generation (interactive)
- Learning footprint structure visually
- Quick prototyping before automation

**Strengths:**
- Built into KiCad (no external tools)
- Visual feedback during creation
- Good for non-programmers

**Limitations:**
- Interactive only (not batch)
- Less customization than scripted approach

---

### 3. TousstNicolas/JLC2KiCad_lib
**Repository**: https://github.com/TousstNicolas/JLC2KiCad_lib

Batch generator for JLCPCB parts. Converts component specs from JLCPCB's database into both symbols and footprints.

**Use case**: Automated bulk footprint creation from part databases

**What it does:**
- Parses JLCPCB part specs (dimensions, pin counts, package types)
- Generates coordinated symbol + footprint pairs
- Batch processes hundreds of components
- Creates complete libraries ready for schematics

**Example workflow:**
```bash
# Uses JLCPCB's API to fetch part data
# Generates KiCad symbol and footprint files
```

**Best for:**
- Building complete component libraries from procurement databases
- Keeping symbol/footprint/part number in sync
- Organizations using JLCPCB for manufacturing

---

### 4. mignon-p/footprint-to-script
**Repository**: https://github.com/mignon-p/footprint-to-script

**Unique capability**: Reverse engineer existing footprints → Python code

**What it does:**
- Takes a `.kicad_mod` file (existing footprint)
- Generates Python/KicadModTree code that recreates it
- Output is human-readable and editable

**Use case:** Understanding and modifying existing footprints

**Workflow:**
```
Existing .kicad_mod → Python script → Edit script → Regenerate modified .kicad_mod
```

**Why useful:**
- Learn footprint structure by example
- Quickly modify base footprints
- Create custom variants

---

### 5. pandysong/dxf2kicad_mod
**Repository**: https://github.com/pandysong/dxf2kicad_mod

**Purpose**: Convert CAD geometry (DXF) to KiCad footprints

**Input**: DXF drawing (from CAD, Inkscape, etc.)
**Output**: `.kicad_mod` file with geometry on silk/copper/edge layers

**Best for:**
- Converting mechanical designs to footprints
- Complex custom geometries (logos, mechanical pockets)
- Architectural/mechanical component integration

---

### 6. atait/kicad-python
**Repository**: https://github.com/atait/kicad-python

**Purpose**: Python library for reading/writing KiCad files programmatically

**Capabilities:**
- Parse existing `.kicad_mod` files
- Modify footprint properties
- Direct S-expression manipulation
- Batch processing

**Use case**: Custom automation scripts for footprint batch processing or modification

**Example:**
```python
from kicad.pcbnew import Footprint
fp = Footprint.from_file('existing.kicad_mod')
# Modify, add pads, etc.
fp.save('modified.kicad_mod')
```

---

### 7. polymurph/kicadpy
**Repository**: https://github.com/polymurph/kicadpy
**Description**: "Kicad Script Toolbox" - Python utilities for KiCad automation

Similar to `atait/kicad-python` but with additional convenience functions.

---

### 8. rjwalters/kicad-tools
**Repository**: https://github.com/rjwalters/kicad-tools
**Description**: Standalone Python tools for parsing/generating KiCad files

Another library option for programmatic file manipulation.

---

### 9. Thunderbird2086/ergogen-footprint-generator
**Repository**: https://github.com/Thunderbird2086/ergogen-footprint-generator
**Specialized**: Keyboard PCB footprints

Domain-specific generator for mechanical keyboard PCBs.

---

## Core Technology: KicadModTree

**What it is**: A Python library that abstracts away S-expression complexity

**Install:**
```bash
pip install KicadModTree
```

**What S-expressions are**: KiCad's native format for footprints
```lisp
(kicad_footprint "R1206"
  (layer "F.Cu")
  (fp_text reference "R" (at 0 0))
  ...
)
```

**KicadModTree advantage**: No need to write S-expressions by hand
```python
from KicadModTree import *
kicad_mod = Footprint("R1206")
kicad_mod.setDescription("Resistor 1206")
kicad_mod.append(Pad(...))
kicad_mod.append(Text(...))
kicad_mod.save("R1206.kicad_mod")
```

**Key features:**
- Pad creation (SMD and through-hole)
- Silk screen graphics (lines, arcs, text)
- Copper layer shapes
- 3D model references
- Automatic layer assignment
- Validation before output

**Documentation**: https://kicad-footprint-generator.readthedocs.io/en/latest/KicadModTree.html

---

## Generation Approaches

### Approach 1: Parametric + YAML Configuration (Recommended for batch)

**Pattern:**
1. Define parameters in YAML: pad count, pitch, size, layer, etc.
2. Python script reads YAML
3. Uses parameters to generate footprint via KicadModTree
4. Produces `.kicad_mod` file

**Tools:** pointhi/kicad-footprint-generator

**Pros:**
- Non-programmers can create variants (edit YAML)
- Version control friendly
- Highly reusable
- Scalable to hundreds of footprints

**Cons:**
- Setup overhead for new component family
- Need to understand structure upfront

**Example:**
```yaml
# resistor_0603.yaml
name: "R_0603"
description: "Resistor 0603"
size_x: 1.6
size_y: 0.8
pad_x: 0.8
pad_y: 1.0
```

```python
# generate.py
config = load_yaml('resistor_0603.yaml')
fp = create_smd_resistor(config)
fp.save(f"{config['name']}.kicad_mod")
```

---

### Approach 2: Direct Python + KicadModTree

**Pattern:**
1. Write Python script directly using KicadModTree API
2. No configuration file (logic embedded in code)
3. More programmatic control

**Tools:** KicadModTree directly

**Pros:**
- Full programming capabilities (loops, conditionals, functions)
- No configuration format to learn
- Direct control

**Cons:**
- Python skill required
- Less reusable (tied to specific script)

**Example:**
```python
from KicadModTree import *

kicad_mod = Footprint("MyComponent")
for i in range(48):  # Generate 48 pads dynamically
    x = (i % 8) * 2.0
    y = (i // 8) * 2.0
    kicad_mod.append(Pad(number=i+1, type=PAD_TYPE_SMD,
                          at=[x, y], shape=PAD_SHAPE_RECT,
                          size=[0.5, 0.5]))
kicad_mod.save("MyComponent.kicad_mod")
```

---

### Approach 3: Database/Datasheet Parsing

**Pattern:**
1. Parse component specs from CSV, datasheet, API
2. Extract pad count, pitch, dimensions
3. Map to footprint template
4. Generate batch

**Tools:** JLC2KiCad_lib, custom scripts with atait/kicad-python

**Best for:** Bulk library creation from procurement data

**Example data sources:**
- JLCPCB component database (API available)
- CSV exports from part suppliers
- Datasheet scans with OCR
- Electronic part lookup databases

---

### Approach 4: CAD Geometry Conversion

**Pattern:**
1. Design in CAD tool (FreeCAD, DraftSight, Inkscape)
2. Export as DXF
3. Convert DXF to KiCad footprint

**Tools:** dxf2kicad_mod

**Best for:**
- Mechanical components with custom geometry
- Logos, mechanical pockets
- Complex shapes hard to code

---

### Approach 5: Footprint Reverse Engineering

**Pattern:**
1. Start with existing `.kicad_mod` file
2. Convert to Python code
3. Edit/modify Python
4. Regenerate

**Tools:** footprint-to-script

**Best for:**
- Learning by example
- Quick customizations
- Creating variants

---

## Batch Processing & Automation

### Pattern: Parametric Multi-Variant Generation

Generate multiple footprint variants from single template:

```python
from KicadModTree import *

pad_sizes = [
    {"name": "0603", "x": 1.6, "y": 0.8},
    {"name": "0805", "x": 2.0, "y": 1.25},
    {"name": "1206", "x": 3.2, "y": 1.6},
]

for size in pad_sizes:
    kicad_mod = Footprint(f"R_{size['name']}")
    # Create with size parameters
    # ... add pads, silk, etc.
    kicad_mod.save(f"R_{size['name']}.kicad_mod")
```

### Pattern: Bulk Library Generation

Generate complete library from manifest:

```python
import csv
from KicadModTree import *

with open('components.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        fp = generate_footprint(row['part_type'], row['params'])
        fp.save(f"output/{row['reference']}.kicad_mod")
```

### Pattern: Library Organization

```
my_library/
  resistors/
    R_0603.kicad_mod
    R_0805.kicad_mod
    R_1206.kicad_mod
  capacitors/
    C_0603.kicad_mod
    C_0805.kicad_mod
  connectors/
    USB_Micro.kicad_mod
    Header_2x5.kicad_mod
```

---

## Use Case Decision Tree

```
Need to generate footprints?
│
├─ Many variants of similar components?
│  └─> Use pointhi/kicad-footprint-generator + YAML parametric
│
├─ Convert parts from JLCPCB database?
│  └─> Use JLC2KiCad_lib
│
├─ Complex custom geometry (CAD)?
│  └─> Use dxf2kicad_mod
│
├─ Learn by modifying existing footprints?
│  └─> Use footprint-to-script
│
├─ Programmatic batch processing (custom)?
│  └─> Use KicadModTree directly or atait/kicad-python
│
└─ One-off interactive generation?
   └─> Use KiCad footprint wizard (built-in)
```

---

## Practical Getting-Started Examples

### Example 1: Generate a simple resistor footprint

```python
#!/usr/bin/env python3
from KicadModTree import *

# Create footprint object
kicad_mod = Footprint("R_0603")

# Properties
kicad_mod.setDescription("Resistor 0603 (1.6mm x 0.8mm)")
kicad_mod.setTags("resistor")

# Courtyard
kicad_mod.append(RectLine(start=[-1.0, -0.5], end=[1.0, 0.5],
                          layer="F.CrtYd", width=0.05))

# Silk screen
kicad_mod.append(Line(start=[-0.15, -0.4], end=[0.15, -0.4],
                      layer="F.SilkS", width=0.1))
kicad_mod.append(Line(start=[-0.15, 0.4], end=[0.15, 0.4],
                      layer="F.SilkS", width=0.1))

# Pads
kicad_mod.append(Pad(number=1, type=PAD_TYPE_SMD, shape=PAD_SHAPE_RECT,
                     at=[-0.8, 0], size=[0.8, 0.8], layers=LAYERS_SMD))
kicad_mod.append(Pad(number=2, type=PAD_TYPE_SMD, shape=PAD_SHAPE_RECT,
                     at=[0.8, 0], size=[0.8, 0.8], layers=LAYERS_SMD))

# Reference designator
kicad_mod.append(Text(type="reference", text="R?", at=[0, -1.2],
                      layer="F.SilkS", size=[1, 1], thickness=0.15))

# Value designator
kicad_mod.append(Text(type="value", text="10k", at=[0, 1.2],
                      layer="F.Fab", size=[1, 1], thickness=0.15))

# Save
kicad_mod.save("R_0603.kicad_mod")
```

### Example 2: Batch generate multiple IC packages

```python
#!/usr/bin/env python3
from KicadModTree import *

def create_soic_footprint(pin_count, pitch=1.27):
    """Generate SOIC package footprint"""
    name = f"SOIC_{pin_count}"
    kicad_mod = Footprint(name)

    # Body dimensions (approximate)
    body_w = 3.9
    body_h = pin_count * pitch / 2 + 1.0

    # Pads
    for i in range(pin_count):
        y = (i - pin_count/2) * pitch + pitch/2

        # Left side
        kicad_mod.append(Pad(number=i+1, type=PAD_TYPE_SMD,
                             shape=PAD_SHAPE_RECT,
                             at=[-body_w/2 - 0.6, y],
                             size=[0.6, 0.35],
                             layers=LAYERS_SMD))

        # Right side
        kicad_mod.append(Pad(number=pin_count+1-i, type=PAD_TYPE_SMD,
                             shape=PAD_SHAPE_RECT,
                             at=[body_w/2 + 0.6, y],
                             size=[0.6, 0.35],
                             layers=LAYERS_SMD))

    # Silk screen
    kicad_mod.append(Line(start=[-body_w/2, -body_h/2],
                          end=[body_w/2, -body_h/2],
                          layer="F.SilkS", width=0.1))

    # Mark pin 1
    kicad_mod.append(Circle(center=[-body_w/2 - 0.5, -body_h/2 + 0.3],
                            radius=0.2, layer="F.SilkS", width=0.1))

    return kicad_mod

# Generate series
for pin_count in [8, 14, 16, 20]:
    fp = create_soic_footprint(pin_count)
    fp.save(f"SOIC_{pin_count}.kicad_mod")
```

### Example 3: Batch from YAML config (pointhi style)

```yaml
# components.yaml
resistors:
  0603:
    x: 1.6
    y: 0.8
    pad_x: 0.8
    pad_y: 1.0
  0805:
    x: 2.0
    y: 1.25
    pad_x: 1.0
    pad_y: 1.2
  1206:
    x: 3.2
    y: 1.6
    pad_x: 1.6
    pad_y: 1.8
```

```python
import yaml
from KicadModTree import *

with open('components.yaml') as f:
    config = yaml.safe_load(f)

for component_type, variants in config.items():
    for variant_name, params in variants.items():
        fp_name = f"{component_type[0].upper()}_{variant_name}"
        kicad_mod = Footprint(fp_name)

        # Generate based on params
        x, y = params['x'], params['y']
        pad_x, pad_y = params['pad_x'], params['pad_y']

        # Create body outline
        kicad_mod.append(RectLine(start=[-x/2, -y/2], end=[x/2, y/2],
                                  layer="F.Fab", width=0.1))

        # Create pads
        kicad_mod.append(Pad(number=1, type=PAD_TYPE_SMD,
                             shape=PAD_SHAPE_RECT,
                             at=[-x/2 - 0.2, 0],
                             size=[pad_x, pad_y],
                             layers=LAYERS_SMD))
        kicad_mod.append(Pad(number=2, type=PAD_TYPE_SMD,
                             shape=PAD_SHAPE_RECT,
                             at=[x/2 + 0.2, 0],
                             size=[pad_x, pad_y],
                             layers=LAYERS_SMD))

        kicad_mod.save(f"output/{fp_name}.kicad_mod")
        print(f"Generated {fp_name}.kicad_mod")
```

---

## Documentation & Learning Resources

| Resource | URL |
|----------|-----|
| **KiCad Official Footprint Format** | https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/ |
| **KicadModTree Documentation** | https://kicad-footprint-generator.readthedocs.io/ |
| **pointhi Generator Examples** | https://github.com/pointhi/kicad-footprint-generator/tree/main/scripts |
| **KiCad Forum - Programmatic Generation** | https://forum.kicad.info/t/programatically-generating-footprints/55850 |
| **KiCad Official Docs** | https://docs.kicad.org/ |

---

## Summary Table: Tool Selection

| Situation | Recommended Tool | Reason |
|-----------|-----------------|--------|
| Generate 100+ resistor variants | pointhi generator + YAML | Parametric, scalable, maintainable |
| Quick batch from JLCPCB database | JLC2KiCad_lib | Purpose-built, automates symbol+footprint |
| Learn footprint structure | footprint-to-script + modify | Concrete examples, educational |
| Complex custom geometry | dxf2kicad_mod | CAD-native input |
| One-off interactive generation | KiCad footprint wizard | Built-in, no setup required |
| Bulk programmatic processing | atait/kicad-python or KicadModTree | Maximum flexibility |
| Official library generation | pointhi generator (KiCad's choice) | Production-tested, standard |
| Custom organization/workflow | KicadModTree directly | Full control, custom logic |

---

## KiCad Footprint File Format (.kicad_mod)

All generators ultimately produce S-expression `.kicad_mod` files.

**Structure:**
```lisp
(kicad_footprint "Footprint_Name"
  (layer "F.Cu")

  (fp_text reference "R?" (at 0 -1.2))
  (fp_text value "10k" (at 0 1.2))

  (fp_line (start -0.8 0) (end 0.8 0) (layer "F.SilkS") (width 0.1))

  (pad "1" smd rect (at -0.8 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "2" smd rect (at 0.8 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask"))
)
```

**Key sections:**
- `fp_text` - Reference designator and value labels
- `fp_line`, `fp_circle`, `fp_poly` - Silk screen graphics
- `pad` - Electrical pads
- `fp_line` on `"F.Fab"` - Copper body outline
- Comments: Reference the component datasheet

All tools here abstract this, so you rarely write S-expressions directly.

---

## Pro Tips

1. **Start with similar existing footprints** - Use `footprint-to-script` to convert them, then modify
2. **Version control your configs** - Store YAML/Python configs in git, not generated `.kicad_mod` files
3. **Validate against datasheet** - Always cross-check generated dimensions with component datasheet
4. **Test in PCBNew** - Load and inspect generated footprints before using in real designs
5. **Use 3D models** - Reference `.step` or `.wrl` files for visual validation
6. **Document constraints** - Add comments explaining pad sizes, clearances, design assumptions
7. **Create templates** - Develop reusable generator functions for component families
8. **Batch verify** - Script to check all generated footprints against a datasheet database

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Pads overlap with silk screen | Adjust silk screen offset, or reduce pad size |
| Courtyard violations | Increase courtyard margin (typically 0.25-0.5mm) |
| 3D model not showing | Verify `.step`/`.wrl` file exists, path is relative |
| Pad mask too small | Increase solder mask expansion (typically 0.05-0.1mm) |
| Text overlaps pads | Adjust text position, reduce text size, or move to different layer |
| Import into KiCad fails | Validate S-expression syntax (use `footprint-to-script` to check) |

---

## Conclusion

KiCad footprint generation is mature and flexible. For most use cases, **pointhi/kicad-footprint-generator** provides the best combination of power, maturity, and community support. For specialized scenarios (JLCPCB integration, CAD conversion, reverse engineering), dedicated tools provide excellent solutions.

Choose your tool based on:
- **Scale** (one-off vs hundreds)
- **Source** (parametric, database, CAD, existing)
- **Customization** (how much control you need)
- **Automation** (batch vs interactive)
