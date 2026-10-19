# KiCad Documentation Index

## PCBA Manufacturing Guides

| Guide | Description |
|-------|-------------|
| [JLCPCB_PCBA_GUIDE.md](JLCPCB_PCBA_GUIDE.md) | Complete JLCPCB PCBA reference: file formats, LCSC part numbers, tools, rotation fixes, testing, order process |
| [PCBWAY_PCBA_GUIDE.md](PCBWAY_PCBA_GUIDE.md) | Complete PCBWay PCBA reference: file formats, sourcing modes, fiducials, testing services, JLCPCB comparison |

---

## Footprint Generation Research

### Overview

Complete research and practical guides for programmatically generating KiCad footprints using Python. Five comprehensive documents covering tools, approaches, examples, and reference materials.

**Total lines**: 2,822 lines across 5 documents
**Total size**: ~77KB
**Time to read all**: 30-45 minutes
**Time to get started**: 5 minutes

---

## Documents

### 1. README_FOOTPRINT_RESEARCH.md (369 lines)
**Purpose**: Navigation hub and quick lookup guide
**Read time**: 10 minutes

Use this as your entry point. It provides:
- Quick navigation by use case ("I want to...")
- Tool selection matrix
- 5-minute getting started paths
- Common patterns
- Troubleshooting reference

**Start here if**: You're new to footprint generation or unsure which document to read

---

### 2. KICAD_FOOTPRINT_GENERATORS.md (687 lines)
**Purpose**: Comprehensive technical reference
**Read time**: 20-25 minutes

Deep dive into:
- 10 major tool repositories with full descriptions
- KicadModTree library architecture
- 6 different generation approaches (parametric, template, database, CAD, reverse-engineering)
- Use case decision tree
- Batch processing patterns
- Pro tips and common pitfalls
- Advanced features (multi-variant, 3D models, library organization)

**Read this for**: Complete understanding of the ecosystem, detailed comparisons, architectural decisions

---

### 3. FOOTPRINT_QUICK_REFERENCE.md (272 lines)
**Purpose**: TL;DR version with quick examples
**Read time**: 5-10 minutes

Contains:
- 3 fastest starting paths (Options A, B, C)
- Tool comparison matrix
- Minimal working Python examples
- Key concepts (pad types, shapes, layers)
- Common tasks with solutions
- One-minute setup instructions

**Read this if**: You want to jump in immediately with code

---

### 4. FOOTPRINT_TOOLS_DIRECTORY.md (469 lines)
**Purpose**: Complete tool catalog and reference
**Read time**: 15-20 minutes

Provides:
- All tools with GitHub/GitLab URLs
- Installation commands for each
- Quick description of capabilities
- When to clone/use each tool
- Quick start commands
- License information
- Troubleshooting by tool

**Use this as**: Lookup reference when exploring specific tools

---

### 5. FOOTPRINT_CODE_EXAMPLES.md (1,025 lines)
**Purpose**: Runnable Python code examples
**Read time**: 20-30 minutes (full), 5 minutes (skim)

Contains 7 complete, tested examples:

1. **Basic SMD Resistor** - Minimal example, understand structure
2. **Multiple Resistor Sizes** - Loop-based parametric generation
3. **16-pin DIP Package** - Through-hole IC with pad arrays
4. **BGA Package** - Ball grid arrays with grid generation
5. **YAML Configuration** - Configuration-driven generation approach
6. **Read/Modify Existing** - Programmatic file manipulation
7. **USB Micro-B Connector** - Complex component with mixed pad types

All examples:
- Copy-paste ready
- Fully commented
- Can be run standalone
- Include setup instructions

**Use this for**: Learning by example, templates for your own code

---

## Quick Navigation by Use Case

### "I need to generate many similar components (resistors, capacitors, various sizes)"
1. Read: FOOTPRINT_QUICK_REFERENCE.md → "Option A"
2. Reference: KICAD_FOOTPRINT_GENERATORS.md → "Parametric Generation"
3. Code: FOOTPRINT_CODE_EXAMPLES.md → Example 2 (loop-based)
4. Clone: https://github.com/pointhi/kicad-footprint-generator

### "I want to write custom Python generators from scratch"
1. Read: FOOTPRINT_QUICK_REFERENCE.md → "Option B"
2. Reference: FOOTPRINT_QUICK_REFERENCE.md → "Key Concepts"
3. Install: `pip install KicadModTree`
4. Code: FOOTPRINT_CODE_EXAMPLES.md → Examples 1-5
5. Docs: https://kicad-footprint-generator.readthedocs.io/

### "I need to automate generation from a parts database (JLCPCB, etc.)"
1. Read: FOOTPRINT_QUICK_REFERENCE.md → "Option C"
2. Reference: KICAD_FOOTPRINT_GENERATORS.md → "Datasheet to Footprint Conversion"
3. Tool: FOOTPRINT_TOOLS_DIRECTORY.md → "JLC2KiCad_lib"
4. Clone: https://github.com/TousstNicolas/JLC2KiCad_lib

### "I need to convert CAD drawings to KiCad footprints"
1. Reference: KICAD_FOOTPRINT_GENERATORS.md → "CAD File Conversion"
2. Code: FOOTPRINT_CODE_EXAMPLES.md → Example 7 (structure reference)
3. Tool: FOOTPRINT_TOOLS_DIRECTORY.md → "dxf2kicad_mod"
4. Clone: https://github.com/pandysong/dxf2kicad_mod

### "I want to learn footprint structure"
1. Use: FOOTPRINT_TOOLS_DIRECTORY.md → "footprint-to-script"
2. Code: FOOTPRINT_CODE_EXAMPLES.md → Examples 1-3
3. Read: README_FOOTPRINT_RESEARCH.md → "Key Concepts"
4. Reference: KICAD_FOOTPRINT_GENERATORS.md → "KicadModTree"

### "I need to find the right tool for my specific situation"
1. Reference: KICAD_FOOTPRINT_GENERATORS.md → "Use Case Decision Tree"
2. Compare: FOOTPRINT_QUICK_REFERENCE.md → "Tool Comparison Matrix"
3. Explore: FOOTPRINT_TOOLS_DIRECTORY.md → matching tool section

---

## Key Findings Summary

### Primary Tool
**pointhi/kicad-footprint-generator**
- Most mature, production-tested
- Used for official KiCad libraries
- Combines KicadModTree + parametric YAML configs
- GitHub: https://github.com/pointhi/kicad-footprint-generator
- Mirror: https://gitlab.com/kicad/libraries/kicad-footprint-generator

### Core Library
**KicadModTree** (Python)
- S-expression abstraction for .kicad_mod files
- Install: `pip install KicadModTree`
- Docs: https://kicad-footprint-generator.readthedocs.io/
- Used by all major tools

### Generation Approaches (Best to Worst)
1. **Parametric + YAML** - Most reusable, scalable (best for batch)
2. **Direct Python + KicadModTree** - Most flexible (best for custom)
3. **Database/Datasheet** - Most automated (best for scale)
4. **CAD Conversion** - Best for complex geometry
5. **Reverse Engineering** - Best for learning

### Other Notable Tools
- **JLC2KiCad_lib** - JLCPCB batch automation
- **dxf2kicad_mod** - CAD geometry conversion
- **footprint-to-script** - Reverse engineering
- **atait/kicad-python** - File manipulation library
- **KiCad/kicad-footprint-wizards** - Official interactive wizard

---

## Getting Started (Choose One Path)

### Path A: Established Framework (Recommended for Batch)
```bash
git clone https://github.com/pointhi/kicad-footprint-generator.git
cd kicad-footprint-generator
# Explore scripts/ directory
# Study YAML configs
# Run generators
```

### Path B: Custom Python (Recommended for Control)
```bash
pip install KicadModTree
# Copy Example 1 from FOOTPRINT_CODE_EXAMPLES.md
# Modify and run
python3 my_footprint.py
```

### Path C: Database Automation (Recommended for Scale)
```bash
git clone https://github.com/TousstNicolas/JLC2KiCad_lib.git
cd JLC2KiCad_lib
python3 jlc2kicad.py
```

---

## Document Structure

```
README_FOOTPRINT_RESEARCH.md
├─ Quick navigation by use case
├─ Tool selection matrix
├─ Getting started paths
└─ Common patterns & troubleshooting

KICAD_FOOTPRINT_GENERATORS.md
├─ Executive summary
├─ 10 tool descriptions
├─ Generation approaches
├─ Decision tree
└─ Pro tips

FOOTPRINT_QUICK_REFERENCE.md
├─ 3 quick start options
├─ Tool comparison matrix
├─ Minimal examples
└─ Key concepts

FOOTPRINT_TOOLS_DIRECTORY.md
├─ Tool catalog (10+)
├─ Installation commands
├─ When to use each
├─ Clone commands
└─ License summary

FOOTPRINT_CODE_EXAMPLES.md
├─ 7 complete Python examples
├─ SMD, through-hole, BGA, connectors
├─ YAML-based approach
├─ File manipulation
└─ Testing & validation
```

---

## What You'll Learn

After reading these documents, you will understand:

1. **Tools Available** - 10+ options for different use cases
2. **Generation Approaches** - 6 different ways to generate footprints
3. **Best Practices** - When to use each approach
4. **Implementation** - Copy-paste ready code examples
5. **Architecture** - How KiCad footprints work internally
6. **Workflow** - How to integrate into your development process
7. **Troubleshooting** - Common pitfalls and solutions
8. **Scaling** - How to automate hundreds of footprints

---

## Quick Reference

### Minimal Python Example
```python
from KicadModTree import *
fp = Footprint("MyComponent")
fp.append(Pad(1, PAD_TYPE_SMD, PAD_SHAPE_RECT, [0,0], [1,1], layers=LAYERS_SMD))
fp.save("MyComponent.kicad_mod")
```

### YAML Approach
```yaml
component_0603:
  width: 1.6
  height: 0.8
  pad_width: 0.8
```

### Key Concepts
- **Pad Types**: SMD (surface mount), THU (through-hole), NPTH (non-plated hole)
- **Pad Shapes**: RECT, CIRCLE, OVAL, TRAPEZOID, ROUNDRECT, CUSTOM
- **Layers**: F.Cu (front copper), F.SilkS (silk), F.Fab (body), F.CrtYd (courtyard)
- **Units**: Millimeters (mm)

---

## Validation Checklist

After generating a footprint:
- [ ] File exists and is valid S-expression syntax
- [ ] Opens in KiCad PCBNew without errors
- [ ] Pads positioned correctly
- [ ] Pad sizes match datasheet
- [ ] Silk screen visible but doesn't overlap pads
- [ ] Courtyard clearance adequate (0.25-0.5mm)
- [ ] Text is readable
- [ ] 3D model path correct (if referenced)

---

## Resources

### Official Documentation
- KiCad Footprint Format: https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/
- KicadModTree API: https://kicad-footprint-generator.readthedocs.io/
- KiCad Official Docs: https://docs.kicad.org/

### Main Repositories
- pointhi generator: https://github.com/pointhi/kicad-footprint-generator
- Official KiCad footprints: https://github.com/kicad/kicad-footprints
- KiCad official mirror: https://gitlab.com/kicad/libraries/kicad-footprint-generator

### Community
- KiCad Forum: https://forum.kicad.info/
- Reddit r/KiCad: https://reddit.com/r/KiCad
- GitHub Issues: Individual tool repositories

---

## Statistics

| Metric | Value |
|--------|-------|
| Total lines | 2,822 |
| Total size | ~77KB |
| Documents | 5 |
| Code examples | 7 |
| Tools documented | 10+ |
| Approaches covered | 6 |
| Read time (all) | 30-45 min |
| Time to start | 5 min |
| Lines of code examples | 1,025 |

---

## How to Use This Index

1. **New to footprint generation?** Start with README_FOOTPRINT_RESEARCH.md
2. **Know what you want to do?** Jump to relevant use case section above
3. **Want to code immediately?** Go to FOOTPRINT_CODE_EXAMPLES.md
4. **Looking for specific tool?** Check FOOTPRINT_TOOLS_DIRECTORY.md
5. **Need deep understanding?** Read KICAD_FOOTPRINT_GENERATORS.md
6. **Need quick reference?** Use FOOTPRINT_QUICK_REFERENCE.md

---

## Document Relationships

```
README_FOOTPRINT_RESEARCH
    └─ Use case finder
       ├─ → FOOTPRINT_QUICK_REFERENCE
       ├─ → KICAD_FOOTPRINT_GENERATORS
       ├─ → FOOTPRINT_TOOLS_DIRECTORY
       └─ → FOOTPRINT_CODE_EXAMPLES

FOOTPRINT_QUICK_REFERENCE
    └─ Option B: Python
       └─ → FOOTPRINT_CODE_EXAMPLES

KICAD_FOOTPRINT_GENERATORS
    ├─ Use case decision tree
    │   └─ → FOOTPRINT_QUICK_REFERENCE
    └─ Pro tips
        └─ → FOOTPRINT_CODE_EXAMPLES

FOOTPRINT_TOOLS_DIRECTORY
    └─ Tool lookup
        └─ → FOOTPRINT_CODE_EXAMPLES

FOOTPRINT_CODE_EXAMPLES
    └─ 7 runnable examples
        └─ References all documents
```

---

## Next Steps

1. Choose your use case from README_FOOTPRINT_RESEARCH.md
2. Read the recommended document(s)
3. Copy a code example from FOOTPRINT_CODE_EXAMPLES.md
4. Modify for your component
5. Test in KiCad
6. Iterate

---

## Questions?

See README_FOOTPRINT_RESEARCH.md section "Questions & Troubleshooting"

## License

Individual tools maintain their own licenses:
- pointhi/kicad-footprint-generator: GPLv2+
- KiCad projects: GPLv3+
- Third-party tools: Mostly MIT or GPL

Please respect each project's license.

---

**Research Date**: March 2026
**Last Updated**: March 2026
**Status**: Complete and ready to use

Enjoy generating footprints!
