# KiCad Footprint Generation Tools - Complete Directory

## Primary Tools

### 1. KicadModTree Library
- **GitHub**: https://github.com/pointhi/kicad-footprint-generator (contains library)
- **PyPI**: `pip install KicadModTree`
- **Documentation**: https://kicad-footprint-generator.readthedocs.io/en/latest/KicadModTree.html
- **Language**: Python
- **License**: GPLv2+
- **Stars**: 1.8k+
- **Status**: Active, production-grade
- **Use**: Core Python library for generating .kicad_mod files programmatically
- **Best for**: Direct programmatic control, custom scripts, automation

**Key files:**
- `KicadModTree/__init__.py` - Main API
- `KicadModTree/Footprint.py` - Footprint class
- `KicadModTree/Modules/Pad.py` - Pad creation
- `KicadModTree/Modules/Line.py`, `Circle.py`, `Polygon.py` - Graphics

**Minimal example:**
```python
from KicadModTree import Footprint, Pad, PAD_TYPE_SMD, PAD_SHAPE_RECT, LAYERS_SMD

fp = Footprint("MyPart")
fp.append(Pad(1, PAD_TYPE_SMD, PAD_SHAPE_RECT, [0,0], [1,1], layers=LAYERS_SMD))
fp.save("MyPart.kicad_mod")
```

---

### 2. pointhi/kicad-footprint-generator
- **GitHub**: https://github.com/pointhi/kicad-footprint-generator
- **GitLab Mirror (Official KiCad)**: https://gitlab.com/kicad/libraries/kicad-footprint-generator
- **Documentation**: https://kicad-footprint-generator.readthedocs.io/
- **Language**: Python
- **License**: GPLv2+
- **Stars**: 1.8k+ (GitHub)
- **Status**: Active, heavily maintained
- **Use**: Parametric footprint generation framework
- **Best for**: Batch generation of similar components, parametric design

**Key components:**
- `KicadModTree/` - The library (also published on PyPI)
- `scripts/` - Pre-built generators for 100+ component types
  - `Resistor_SMD/` - SMD resistor variants
  - `Capacitor_SMD/` - SMD capacitor variants
  - `Package_BGA/` - BGA packages
  - `Package_QFP/` - QFP/TQFP/LQFP packages
  - `Package_DIP/` - DIP packages
  - `Connectors/` - Various connector types
  - And many more...
- `*.yaml` or `*.yml` config files - Parameter definitions
- `generate_<component>.py` - Script to generate from config

**Clone and explore:**
```bash
git clone https://github.com/pointhi/kicad-footprint-generator.git
cd kicad-footprint-generator/scripts
ls -la  # See available component types
cat Resistor_SMD/R_0603.yaml  # View YAML config example
python3 generate_resistor_smd.py  # Run generator
```

**Used by:** KiCad's official library, thousands of projects

---

### 3. KiCad/kicad-footprint-wizards
- **GitHub**: https://github.com/KiCad/kicad-footprint-wizards
- **Language**: Python
- **License**: GPLv3+
- **Status**: Official KiCad project, maintained
- **Use**: Interactive GUI-based footprint generation
- **Best for**: One-off interactive generation, non-programmers

**How to use:**
1. Open KiCad PCBNew
2. Tools → Footprint Wizard
3. Select component type (BGA, QFP, DIL, etc.)
4. Adjust parameters in GUI
5. Generate

**Built-in wizards:**
- BGA array wizard
- QFP package wizard
- DIP package wizard
- Generic Pad Array wizard
- SMD Pad Array wizard

**Key files:**
- `plugins/Footprint_Wizards/` - Wizard implementations
- Each wizard is a Python plugin

---

## Specialized Tools

### 4. TousstNicolas/JLC2KiCad_lib
- **GitHub**: https://github.com/TousstNicolas/JLC2KiCad_lib
- **Language**: Python
- **License**: MIT
- **Stars**: 1.2k+
- **Status**: Active
- **Use**: Batch generation from JLCPCB component database
- **Best for**: Automated library creation from parts database

**What it does:**
- Fetches component specs from JLCPCB API
- Generates both symbols (.kicad_sym) and footprints (.kicad_mod)
- Creates complete synchronized libraries
- Handles datasheet mapping

**Usage:**
```bash
git clone https://github.com/TousstNicolas/JLC2KiCad_lib.git
cd JLC2KiCad_lib
python3 jlc2kicad.py  # Follow prompts
```

**Output:** Organized library folders with symbols and footprints

**Best for:** Organizations using JLCPCB for manufacturing, bulk part automation

---

### 5. pandysong/dxf2kicad_mod
- **GitHub**: https://github.com/pandysong/dxf2kicad_mod
- **Language**: Python
- **License**: MIT
- **Status**: Active
- **Use**: Convert DXF files to KiCad footprints
- **Best for**: Complex custom geometry, CAD-sourced designs

**Input:** DXF file (from AutoCAD, FreeCAD, Inkscape, etc.)
**Output:** .kicad_mod file with geometry

**Usage:**
```bash
python3 dxf2kicad_mod.py input.dxf output.kicad_mod
```

**Good for:**
- Logos and custom graphics
- Mechanical mounting features
- Complex edge cuts
- Architectural components

---

### 6. mignon-p/footprint-to-script
- **GitHub**: https://github.com/mignon-p/footprint-to-script
- **Language**: Python
- **License**: MIT
- **Status**: Active
- **Use**: Reverse engineering - convert .kicad_mod to Python code
- **Best for**: Learning, modifying existing footprints

**What it does:**
- Reads existing .kicad_mod file
- Generates Python code using KicadModTree that recreates it
- Human-readable output that can be edited and regenerated

**Usage:**
```bash
python3 footprint_to_script.py existing_footprint.kicad_mod output.py
# Edit output.py
python3 output.py  # Regenerate modified footprint
```

**Workflow:**
1. Find similar existing footprint
2. Convert to Python code
3. Edit parameters
4. Regenerate
5. Iterate

---

### 7. atait/kicad-python
- **GitHub**: https://github.com/atait/kicad-python
- **Language**: Python
- **License**: MIT
- **Status**: Active
- **Use**: Library for reading/writing KiCad files
- **Best for**: Programmatic batch processing, custom modifications

**Capabilities:**
- Parse .kicad_mod files as Python objects
- Modify footprint properties
- Direct S-expression manipulation
- Batch processing pipelines

**Install:**
```bash
pip install kicad-python
```

**Example:**
```python
from kicad.pcbnew import Footprint
fp = Footprint.from_file('existing.kicad_mod')
# Modify, add pads, change properties, etc.
fp.save('modified.kicad_mod')
```

**Use cases:**
- Batch rename footprints
- Adjust pad sizing across library
- Convert footprint libraries
- Custom transformations

---

### 8. polymurph/kicadpy
- **GitHub**: https://github.com/polymurph/kicadpy
- **Language**: Python
- **License**: GPL
- **Status**: Maintained
- **Use**: Kicad Script Toolbox
- **Best for**: KiCad automation and scripting

Similar to atait/kicad-python but with additional convenience functions.

---

### 9. rjwalters/kicad-tools
- **GitHub**: https://github.com/rjwalters/kicad-tools
- **Language**: Python
- **License**: MIT
- **Status**: Maintained
- **Use**: Parsing and generating KiCad files
- **Best for**: File manipulation utilities

Another option for programmatic file handling.

---

### 10. Thunderbird2086/ergogen-footprint-generator
- **GitHub**: https://github.com/Thunderbird2086/ergogen-footprint-generator
- **Language**: Python
- **Status**: Active
- **Use**: Mechanical keyboard footprint generation
- **Best for**: Keyboard PCB designs

Specialized generator for keyboard-specific components.

---

## KiCad Official Resources

### KiCad Footprint Generator (Official)
- **GitLab**: https://gitlab.com/kicad/libraries/kicad-footprint-generator
- **Used for**: Generating official KiCad footprint libraries
- **Access**: Same as pointhi/kicad-footprint-generator (often synced)

### KiCad Official Footprint Libraries
- **GitHub**: https://github.com/kicad/kicad-footprints
- **GitLab**: https://gitlab.com/kicad/libraries/kicad-footprints
- **Content**: Official, production-tested footprints
- **Generated with**: pointhi/kicad-footprint-generator

### KiCad Documentation
- **Footprint Format Spec**: https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/
- **Official Docs**: https://docs.kicad.org/
- **PCBNew Manual**: https://docs.kicad.org/latest/en/pcbnew/pcbnew.html

---

## Library References & Collections

### kitspace/kicad_footprints
- **GitHub**: https://github.com/kitspace/kicad_footprints
- **Purpose**: Aggregates footprints from multiple sources
- **Use**: Find examples, reference implementations

### KiCad Forum
- **URL**: https://forum.kicad.info/
- **Relevant threads**:
  - https://forum.kicad.info/t/programatically-generating-footprints/55850
  - https://forum.kicad.info/t/is-there-a-python-package-for-modifying-kicad_mod-files/29278

### Electronics Design Tools
- **devbisme/kicad-3rd-party-tools**: https://github.com/devbisme/kicad-3rd-party-tools
- Directory of third-party KiCad tools and integrations

---

## Quick Start Commands

### Clone and explore pointhi generator
```bash
git clone https://github.com/pointhi/kicad-footprint-generator.git
cd kicad-footprint-generator
pip install -r requirements.txt
cd scripts/Resistor_SMD
python3 generate_resistor_smd.py
# Output: Generated/*.kicad_mod
```

### Install KicadModTree directly
```bash
pip install KicadModTree
# Now you can use it in your Python scripts
```

### Clone JLC2KiCad
```bash
git clone https://github.com/TousstNicolas/JLC2KiCad_lib.git
cd JLC2KiCad_lib
python3 jlc2kicad.py
```

### Try dxf2kicad conversion
```bash
git clone https://github.com/pandysong/dxf2kicad_mod.git
cd dxf2kicad_mod
python3 dxf2kicad_mod.py your_design.dxf output.kicad_mod
```

### Reverse engineer a footprint
```bash
git clone https://github.com/mignon-p/footprint-to-script.git
cd footprint-to-script
python3 footprint_to_script.py existing.kicad_mod output.py
```

---

## Comparison: What to Clone First?

### I want to generate similar components in bulk
→ Clone **pointhi/kicad-footprint-generator**

### I want to write custom Python generators
→ Install **KicadModTree** (pip install)

### I want to automate from JLCPCB parts
→ Clone **TousstNicolas/JLC2KiCad_lib**

### I want to convert CAD drawings
→ Clone **pandysong/dxf2kicad_mod**

### I want to learn by modifying existing footprints
→ Clone **mignon-p/footprint-to-script**

### I want to batch process footprints programmatically
→ Clone **atait/kicad-python** or **polymurph/kicadpy**

---

## Community & Resources

### Forums & Discussions
- **KiCad Info Forum**: https://forum.kicad.info/
- **Reddit r/KiCad**: https://reddit.com/r/KiCad
- **EEVblog Forum**: https://eevblog.com/forum/kicad/

### Documentation
- **KiCad Official**: https://docs.kicad.org/
- **KiCad Dev Docs**: https://dev-docs.kicad.org/
- **KicadModTree ReadTheDocs**: https://kicad-footprint-generator.readthedocs.io/

### YouTube Tutorials
- Search: "KiCad footprint generator tutorial"
- Search: "KiCad footprint wizard"
- Search: "KicadModTree Python"

### GitHub Discussions
- KiCad Footprint Generator issues/discussions: https://github.com/pointhi/kicad-footprint-generator/issues
- JLC2KiCad issues: https://github.com/TousstNicolas/JLC2KiCad_lib/issues

---

## File Format Reference

All tools ultimately produce `.kicad_mod` files (S-expression format):

```lisp
(kicad_footprint "Footprint_Name"
  (layer "F.Cu")
  (descr "Description")
  (tags "tag1 tag2")

  (fp_text reference "R?" (at 0 -1.2) (layer "F.SilkS"))
  (fp_text value "10k" (at 0 1.2) (layer "F.Fab"))

  (fp_line (start -0.8 -0.4) (end 0.8 -0.4) (layer "F.SilkS") (width 0.1))
  (fp_line (start -0.8 0.4) (end 0.8 0.4) (layer "F.SilkS") (width 0.1))

  (pad "1" smd rect (at -0.8 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "2" smd rect (at 0.8 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask"))
)
```

**Learn format**: https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/

---

## Troubleshooting by Tool

### pointhi generator not working
- Check Python version (3.6+)
- Install dependencies: `pip install -r requirements.txt`
- Check YAML syntax (use `yamllint`)
- Look at existing examples in `scripts/`

### KicadModTree import error
- Install: `pip install KicadModTree`
- Check Python path: `python3 -c "from KicadModTree import *"`

### JLC2KiCad_lib hangs
- Check internet connection (fetches from JLCPCB API)
- Try with fewer parts first
- Check GitHub issues for known problems

### dxf2kicad_mod output looks wrong
- Verify DXF layer mappings
- Check coordinate system in DXF
- Try with simple geometry first

### footprint-to-script doesn't parse
- Ensure .kicad_mod is valid (try in KiCad)
- Check KiCad version compatibility
- File might be corrupted (try another footprint)

---

## License Summary

| Tool | License |
|------|---------|
| pointhi/kicad-footprint-generator | GPLv2+ |
| KiCad/kicad-footprint-wizards | GPLv3+ |
| KicadModTree | GPLv2+ |
| JLC2KiCad_lib | MIT |
| dxf2kicad_mod | MIT |
| footprint-to-script | MIT |
| atait/kicad-python | MIT |
| polymurph/kicadpy | GPL |
| rjwalters/kicad-tools | MIT |

---

## Next Steps

1. **Explore**: Visit https://github.com/pointhi/kicad-footprint-generator and explore `scripts/` directory
2. **Learn**: Read https://kicad-footprint-generator.readthedocs.io/en/latest/KicadModTree.html
3. **Try**: Install KicadModTree (`pip install KicadModTree`) and write a simple generator
4. **Reference**: Bookmark https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/ for format details
5. **Share**: Contribute generators back to pointhi or KiCad official libraries

---

## Quick Links Summary

| What | URL |
|------|-----|
| Main generator framework | https://github.com/pointhi/kicad-footprint-generator |
| PyPI KicadModTree | https://pypi.org/project/KicadModTree/ |
| KicadModTree docs | https://kicad-footprint-generator.readthedocs.io/ |
| Official KiCad libraries | https://github.com/kicad/kicad-footprints |
| KiCad format spec | https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/ |
| JLCPCB automation | https://github.com/TousstNicolas/JLC2KiCad_lib |
| DXF conversion | https://github.com/pandysong/dxf2kicad_mod |
| Reverse engineering | https://github.com/mignon-p/footprint-to-script |
| File manipulation | https://github.com/atait/kicad-python |
| KiCad forum | https://forum.kicad.info/ |
