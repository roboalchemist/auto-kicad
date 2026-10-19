# KiCad Footprint Generation - Quick Reference

## TL;DR

Want to generate KiCad footprints programmatically? Here's the fastest path:

### Option A: Use the established framework (pointhi)
```bash
git clone https://github.com/pointhi/kicad-footprint-generator.git
cd kicad-footprint-generator
# Look at scripts/ directory for examples
# Create your YAML config
# Run generator → get .kicad_mod files
```

### Option B: Use KicadModTree directly
```bash
pip install KicadModTree

# Then write Python:
from KicadModTree import *
kicad_mod = Footprint("MyComponent")
kicad_mod.append(Pad(...))
kicad_mod.save("MyComponent.kicad_mod")
```

### Option C: Batch from part database
```bash
# JLCPCB parts → KiCad library
git clone https://github.com/TousstNicolas/JLC2KiCad_lib.git
# Follow their automation guide
```

---

## Tool Comparison Matrix

| Tool | Best For | Input | Output | Learning Curve |
|------|----------|-------|--------|-----------------|
| **pointhi/kicad-footprint-generator** | Parametric batch, similar components | YAML config | .kicad_mod | Medium |
| **KicadModTree** | Programmatic control, custom logic | Python code | .kicad_mod | Medium |
| **KiCad footprint wizard** | Interactive one-off | GUI | .kicad_mod | Easy |
| **JLC2KiCad_lib** | Batch from JLCPCB database | Part specs | Symbols + footprints | Medium |
| **dxf2kicad_mod** | Complex custom geometry | DXF file | .kicad_mod | Low |
| **footprint-to-script** | Reverse engineering, learning | .kicad_mod file | Python code | Easy |
| **atait/kicad-python** | Custom batch processing | .kicad_mod file | Modified .kicad_mod | Hard |

---

## Minimal Working Examples

### Generate a simple SMD resistor
```python
from KicadModTree import *

kicad_mod = Footprint("R_0603")
kicad_mod.setDescription("Resistor 0603")

# Left pad
kicad_mod.append(Pad(number=1, type=PAD_TYPE_SMD, shape=PAD_SHAPE_RECT,
                     at=[-0.8, 0], size=[0.8, 0.8], layers=LAYERS_SMD))

# Right pad
kicad_mod.append(Pad(number=2, type=PAD_TYPE_SMD, shape=PAD_SHAPE_RECT,
                     at=[0.8, 0], size=[0.8, 0.8], layers=LAYERS_SMD))

# Silk screen
kicad_mod.append(Line(start=[-0.3, -0.4], end=[0.3, -0.4],
                      layer="F.SilkS", width=0.1))

# Text
kicad_mod.append(Text(type="reference", text="R?", at=[0, -1.2],
                      layer="F.SilkS"))
kicad_mod.append(Text(type="value", text="10k", at=[0, 1.2],
                      layer="F.Fab"))

kicad_mod.save("R_0603.kicad_mod")
```

### Generate 10 variants from a loop
```python
from KicadModTree import *

sizes = [
    {"name": "0603", "x": 1.6, "y": 0.8, "pad_w": 0.8, "pad_h": 1.0},
    {"name": "0805", "x": 2.0, "y": 1.25, "pad_w": 1.0, "pad_h": 1.2},
    {"name": "1206", "x": 3.2, "y": 1.6, "pad_w": 1.6, "pad_h": 1.8},
]

for size in sizes:
    fp = Footprint(f"R_{size['name']}")
    x, y = size['x'], size['y']
    pad_w, pad_h = size['pad_w'], size['pad_h']

    # Create pads
    fp.append(Pad(number=1, type=PAD_TYPE_SMD, shape=PAD_SHAPE_RECT,
                  at=[-x/2 - 0.15, 0], size=[pad_w, pad_h], layers=LAYERS_SMD))
    fp.append(Pad(number=2, type=PAD_TYPE_SMD, shape=PAD_SHAPE_RECT,
                  at=[x/2 + 0.15, 0], size=[pad_w, pad_h], layers=LAYERS_SMD))

    # Body outline
    fp.append(RectLine(start=[-x/2, -y/2], end=[x/2, y/2],
                       layer="F.Fab", width=0.1))

    fp.save(f"R_{size['name']}.kicad_mod")
```

### Generate with YAML config (pointhi style)
```yaml
# config.yaml
component: "Resistor"
variants:
  - name: "0603"
    size_x: 1.6
    size_y: 0.8
    pad_width: 0.8
    pad_height: 1.0

  - name: "0805"
    size_x: 2.0
    size_y: 1.25
    pad_width: 1.0
    pad_height: 1.2
```

```python
import yaml
from KicadModTree import *

with open('config.yaml') as f:
    config = yaml.safe_load(f)

for variant in config['variants']:
    fp = Footprint(f"{config['component']}_{variant['name']}")
    # ... generate using variant parameters ...
    fp.save(f"{config['component']}_{variant['name']}.kicad_mod")
```

---

## Key Concepts

### The KicadModTree Library
- Abstracts KiCad's S-expression format
- Handles layer names, coordinate systems, size conversions
- Validates before saving
- Install: `pip install KicadModTree`

### Pad Types
- `PAD_TYPE_SMD` - Surface mount (no hole)
- `PAD_TYPE_THU` - Through-hole (drilling required)
- `PAD_TYPE_NPTH` - Non-plated through-hole (mounting holes, no copper)

### Pad Shapes
- `PAD_SHAPE_RECT` - Rectangle (most common)
- `PAD_SHAPE_CIRCLE` - Circle
- `PAD_SHAPE_OVAL` - Oval
- `PAD_SHAPE_TRAPEZOID` - Trapezoidal (advanced)
- `PAD_SHAPE_ROUNDRECT` - Rounded rectangle
- `PAD_SHAPE_CUSTOM` - Complex custom shape

### Layers
- `F.Cu` - Front copper
- `B.Cu` - Back copper
- `F.SilkS` - Front silk screen (reference text, graphics)
- `B.SilkS` - Back silk screen
- `F.Fab` - Front fabrication layer (body outlines)
- `F.Paste` - Front solder paste (usually auto from pads)
- `F.Mask` - Front solder mask (usually auto from pads)
- `F.CrtYd` - Front courtyard (clearance zone)
- `Edge.Cuts` - PCB edge (for footprint boundary)

### Coordinate System
- Center of footprint is (0, 0)
- X increases rightward, Y increases downward
- Units: millimeters (mm)
- Example: Pin 1 at bottom-left, Pin N at top-right for DIP

---

## Common Tasks

### Task: Generate IC package (BGA, QFP, etc.)
Use **pointhi/kicad-footprint-generator**. Look at `scripts/Package_BGA/`, `scripts/Package_QFP/` for templates.

### Task: Generate resistors in all sizes (0603, 0805, 1206, etc.)
Use **KicadModTree loop** or **YAML config** approach. Vary pad/body dimensions.

### Task: Automate from part database
Use **JLC2KiCad_lib** for JLCPCB parts, or write custom script with **atait/kicad-python**.

### Task: Convert CAD drawing to footprint
Use **dxf2kicad_mod**. Export CAD as DXF, convert, import into KiCad.

### Task: Modify existing footprint
Use **footprint-to-script** to convert to Python, edit, regenerate.

### Task: Create custom geometry (logo, mechanical pocket)
Use **dxf2kicad_mod** (CAD → DXF → footprint) or **KicadModTree with Polygon**.

### Task: Generate 1000+ components from spreadsheet
Use **atait/kicad-python** with CSV/Excel input, loop to batch create/modify.

---

## Debugging Checklist

- [ ] Generated .kicad_mod file exists
- [ ] File syntax is valid S-expression (try opening in text editor)
- [ ] Open in KiCad PCBNew and inspect visually
- [ ] Check pad positions match datasheet
- [ ] Check pad sizes match datasheet
- [ ] Verify silk screen doesn't overlap pads
- [ ] Check courtyard clearance (typically 0.25-0.5mm)
- [ ] Validate against datasheet dimensions
- [ ] Compare side-by-side with official footprint if available

---

## Resources

| Resource | Purpose |
|----------|---------|
| https://github.com/pointhi/kicad-footprint-generator | Full framework + examples |
| https://kicad-footprint-generator.readthedocs.io/ | KicadModTree API docs |
| https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/ | Footprint file format spec |
| https://forum.kicad.info/t/programatically-generating-footprints/ | Community discussions |
| https://github.com/TousstNicolas/JLC2KiCad_lib | JLCPCB automation |
| https://github.com/pandysong/dxf2kicad_mod | DXF conversion |

---

## Next Steps

1. **For parametric batch generation**: Clone pointhi repo, study existing scripts, create your component template
2. **For quick prototyping**: Install KicadModTree, write minimal Python, iterate
3. **For database automation**: Set up JLC2KiCad_lib or write custom pipeline with atait/kicad-python
4. **For learning**: Use footprint-to-script on existing KiCad footprints to see structure

---

## Common Pitfalls

| Mistake | Fix |
|---------|-----|
| Pads overlap silk screen | Move silk screen further away (at least 0.15mm) |
| Pads out of spec | Double-check datasheet, measure in KiCad |
| Courtyard violations | Add clearance (typically 0.25-0.5mm on all sides) |
| Text too small to read | Increase text size to 1.0-1.5mm min |
| 3D model missing | Add `model` field with relative path to `.step` or `.wrl` |
| Can't find component in library | Make sure file is in KiCad library folder and file is named correctly |
| Footprint offset | Center footprint at (0, 0), not at Pin 1 |

---

## One-Minute Setup

```bash
# Install KicadModTree
pip install KicadModTree

# Clone pointhi reference
git clone https://github.com/pointhi/kicad-footprint-generator.git

# Study an example
cat kicad-footprint-generator/scripts/Resistor_SMD/R_0603.yaml

# Copy and modify for your component
# Run generator
```

That's it. You're ready to generate.
