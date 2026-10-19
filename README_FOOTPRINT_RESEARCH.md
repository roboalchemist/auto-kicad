# KiCad Footprint Generation Research - Complete Documentation

This directory contains comprehensive research and practical guides for programmatically generating KiCad footprints using Python.

## Documents Overview

### 1. **KICAD_FOOTPRINT_GENERATORS.md** (Main Reference)
Comprehensive overview of footprint generation approaches, tools, and technologies.

**Contains:**
- Executive summary
- 10 major tool repositories with descriptions
- KicadModTree library details
- 6 different generation approaches (parametric, template, datasheet, etc.)
- Use case decision tree
- Batch processing patterns
- Pro tips and troubleshooting

**Read this first** if you're new to KiCad footprint generation.

---

### 2. **FOOTPRINT_QUICK_REFERENCE.md** (TL;DR)
Quick reference guide with minimal examples and decision matrix.

**Contains:**
- Three fastest-path options (pointhi, KicadModTree, JLC2KiCad)
- Tool comparison matrix
- Minimal working examples
- Common tasks and solutions
- Debugging checklist
- One-minute setup

**Read this** if you want to get started immediately.

---

### 3. **FOOTPRINT_TOOLS_DIRECTORY.md** (Tool Catalog)
Complete directory of all KiCad footprint tools with links and quick summaries.

**Contains:**
- 10+ tool repositories with URLs
- Installation commands
- License information
- Quick start commands for each tool
- When to clone/use each tool
- Community resources

**Use this** to find and explore specific tools.

---

### 4. **FOOTPRINT_CODE_EXAMPLES.md** (Runnable Code)
Complete, runnable Python examples demonstrating footprint generation.

**Contains:**
- Example 1: Basic SMD resistor (minimal example)
- Example 2: Multiple resistor sizes from loop (parametric)
- Example 3: 16-pin DIP through-hole IC
- Example 4: BGA (Ball Grid Array) package
- Example 5: YAML-based configuration approach
- Example 6: Reading/modifying existing footprints
- Example 7: USB Micro-B connector
- Installation & dependencies
- Testing in KiCad
- Common modifications

**Use these** as templates for your own footprint generation scripts.

---

## Quick Navigation

### I want to...

**Generate many similar components (resistors, capacitors, etc.)**
1. Read: FOOTPRINT_QUICK_REFERENCE.md → "Option A"
2. Explore: FOOTPRINT_TOOLS_DIRECTORY.md → "pointhi/kicad-footprint-generator"
3. Code: Clone pointhi, study `scripts/` directory

**Write custom Python generators**
1. Read: FOOTPRINT_QUICK_REFERENCE.md → "Option B"
2. Code: FOOTPRINT_CODE_EXAMPLES.md → Examples 1-2
3. Reference: KICAD_FOOTPRINT_GENERATORS.md → "KicadModTree" section

**Automate from part database (JLCPCB)**
1. Read: FOOTPRINT_QUICK_REFERENCE.md → "Option C"
2. Explore: FOOTPRINT_TOOLS_DIRECTORY.md → "JLC2KiCad_lib"
3. Code: Clone and follow their documentation

**Convert CAD drawings to footprints**
1. Explore: FOOTPRINT_TOOLS_DIRECTORY.md → "pandysong/dxf2kicad_mod"
2. Code: FOOTPRINT_CODE_EXAMPLES.md → Example 7 (reference structure)

**Learn footprint structure**
1. Read: FOOTPRINT_QUICK_REFERENCE.md → "Key Concepts"
2. Explore: FOOTPRINT_TOOLS_DIRECTORY.md → "footprint-to-script"
3. Code: FOOTPRINT_CODE_EXAMPLES.md → Examples 1-3

**Find the right tool for my use case**
1. Read: KICAD_FOOTPRINT_GENERATORS.md → "Use Case Decision Tree"
2. Reference: FOOTPRINT_QUICK_REFERENCE.md → Tool Comparison Matrix
3. Explore: FOOTPRINT_TOOLS_DIRECTORY.md → specific tool

---

## Key Findings

### Primary Tools

| Tool | Best For | Get Started |
|------|----------|-------------|
| **pointhi/kicad-footprint-generator** | Parametric batch, production use | Clone repo, study `scripts/` |
| **KicadModTree** | Direct Python control, custom logic | `pip install KicadModTree` |
| **JLC2KiCad_lib** | JLCPCB database automation | Clone repo, run script |
| **KiCad footprint wizard** | Interactive one-off generation | Already in KiCad, use GUI |
| **footprint-to-script** | Learn by reverse engineering | Clone repo, run on existing .kicad_mod |

### Core Technology

All tools ultimately generate `.kicad_mod` files (S-expression format). **KicadModTree** is the de facto Python standard:

```python
from KicadModTree import *
fp = Footprint("MyComponent")
fp.append(Pad(...))
fp.save("MyComponent.kicad_mod")
```

### Generation Approaches

1. **Parametric + YAML** (most reusable)
   - Define parameters in YAML
   - Python reads YAML, generates footprints
   - Best for: families of similar components

2. **Direct Python + KicadModTree** (most flexible)
   - Write Python logic directly
   - Full programming capabilities
   - Best for: custom components, complex logic

3. **Database/Datasheet** (most scalable)
   - Parse part specs from CSV/API/datasheet
   - Batch generate hundreds of footprints
   - Best for: automated library creation

4. **CAD Conversion** (for complex geometry)
   - Design in CAD, export DXF
   - Convert to KiCad footprint
   - Best for: mechanical components, logos

5. **Reverse Engineering** (for learning)
   - Convert existing footprint to Python
   - Edit and regenerate
   - Best for: understanding, quick customization

---

## Getting Started (5 minutes)

### Path 1: Use existing framework
```bash
git clone https://github.com/pointhi/kicad-footprint-generator.git
cd kicad-footprint-generator/scripts
# Explore examples, create your YAML config
```

### Path 2: Write Python directly
```bash
pip install KicadModTree
# Use code from FOOTPRINT_CODE_EXAMPLES.md as template
python3 generate_my_footprint.py
```

### Path 3: Quick interactive generation
1. Open KiCad PCBNews
2. Tools → Footprint Wizard
3. Select component type, adjust parameters, generate

---

## Key Resources

### Official Documentation
- **KiCad Footprint Format**: https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/
- **KicadModTree API**: https://kicad-footprint-generator.readthedocs.io/
- **KiCad Official Docs**: https://docs.kicad.org/

### Main Repositories
- **pointhi generator**: https://github.com/pointhi/kicad-footprint-generator
- **KiCad official mirror**: https://gitlab.com/kicad/libraries/kicad-footprint-generator
- **Official KiCad footprints**: https://github.com/kicad/kicad-footprints

### Community
- **KiCad Forum**: https://forum.kicad.info/
- **Reddit r/KiCad**: https://reddit.com/r/KiCad
- **GitHub discussions**: Various tool repos

---

## Common Patterns

### Pattern 1: Loop-based parametric generation
```python
sizes = [
    {"name": "0603", "w": 1.6, "h": 0.8},
    {"name": "0805", "w": 2.0, "h": 1.25},
]

for size in sizes:
    fp = Footprint(f"R_{size['name']}")
    # Generate using size['w'], size['h']
    fp.save(f"R_{size['name']}.kicad_mod")
```

### Pattern 2: Configuration file (YAML)
```yaml
resistor_0603:
  width: 1.6
  height: 0.8
  pad_width: 0.8
```
```python
config = load_yaml('config.yaml')
for name, params in config.items():
    fp = generate(name, params)
    fp.save(f"{name}.kicad_mod")
```

### Pattern 3: Batch from database
```python
for part in fetch_jlcpcb_parts():
    fp = generate_from_datasheet(part)
    fp.save(f"{part.reference}.kicad_mod")
```

---

## File Organization

```
kicad-claude/
├── README_FOOTPRINT_RESEARCH.md          (This file - Navigation guide)
├── KICAD_FOOTPRINT_GENERATORS.md         (Comprehensive reference)
├── FOOTPRINT_QUICK_REFERENCE.md          (TL;DR quick start)
├── FOOTPRINT_TOOLS_DIRECTORY.md          (Tool catalog & links)
└── FOOTPRINT_CODE_EXAMPLES.md            (7 runnable examples)
```

---

## Validation Checklist

After generating a footprint, verify:

- [ ] File exists and is valid S-expression syntax
- [ ] Opens in KiCad PCBNew without errors
- [ ] Pads positioned correctly (check against datasheet)
- [ ] Pad sizes match datasheet specifications
- [ ] Silk screen visible but doesn't overlap pads
- [ ] Courtyard clearance adequate (0.25-0.5mm typical)
- [ ] Text is readable (minimum 1.0mm)
- [ ] 3D model path correct (if referenced)
- [ ] All layers present (F.Cu, F.SilkS, F.Fab, F.CrtYd)

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| "Can't import KicadModTree" | `pip install KicadModTree` |
| Pads overlap silk screen | Move silk at least 0.15mm away |
| Courtyard violations | Increase clearance (0.25-0.5mm) |
| Footprint won't import | Check S-expression syntax, try with footprint-to-script |
| Dimensions don't match datasheet | Double-check datasheet, measure in KiCad |
| 3D model not showing | Verify file path, use relative paths |

---

## Next Steps

1. **Choose your approach**
   - Parametric batch? → Use pointhi generator
   - Custom Python? → Use KicadModTree + Examples
   - Database automation? → Use JLC2KiCad_lib
   - One-off? → Use KiCad wizard

2. **Read relevant documentation**
   - Start with FOOTPRINT_QUICK_REFERENCE.md
   - Dive deeper with KICAD_FOOTPRINT_GENERATORS.md

3. **Run an example**
   - Pick one from FOOTPRINT_CODE_EXAMPLES.md
   - Modify parameters
   - Generate and test in KiCad

4. **Build your workflow**
   - Combine patterns from code examples
   - Test with real footprints
   - Iterate based on KiCad feedback

5. **Contribute back**
   - Share improvements to pointhi or KiCad official libraries
   - Document your generators for others
   - Join the community discussions

---

## Questions & Troubleshooting

### "Which tool should I use?"
See FOOTPRINT_QUICK_REFERENCE.md → "Tool Comparison Matrix" and KICAD_FOOTPRINT_GENERATORS.md → "Use Case Decision Tree"

### "How do I get started fastest?"
Follow the 5-minute guide above, or pick one of the three options in FOOTPRINT_QUICK_REFERENCE.md

### "What are best practices?"
See KICAD_FOOTPRINT_GENERATORS.md → "Pro Tips" section

### "My footprint doesn't work"
See the "Validation Checklist" and "Common Pitfalls" sections above

### "I need a specific example"
Check FOOTPRINT_CODE_EXAMPLES.md for 7 complete examples covering different component types

### "Where can I find similar footprints to reference?"
- KiCad official libraries: https://github.com/kicad/kicad-footprints
- pointhi generator scripts: https://github.com/pointhi/kicad-footprint-generator/tree/main/scripts
- kitspace collection: https://github.com/kitspace/kicad_footprints

---

## Document Version & Maintainer

**Created**: March 2026
**Research Method**: Tavily web search, GitHub repository exploration
**Scope**: Comprehensive footprint generation tools, approaches, and practical guides

---

## License & Attribution

This research document is provided as-is. Individual tools and repositories have their own licenses:
- pointhi/kicad-footprint-generator: GPLv2+
- KiCad projects: GPLv3+
- Most third-party tools: MIT or GPL

Please respect each project's license when using or contributing.

---

## Summary

KiCad footprint generation is well-supported by a mature ecosystem:

1. **Framework**: KicadModTree (Python library)
2. **Best overall**: pointhi/kicad-footprint-generator (production-grade)
3. **Approaches**: 5+ ways to generate (parametric, database, CAD, etc.)
4. **Ease**: From interactive wizards to full programmatic control
5. **Scale**: From one-off footprints to thousands of automated components

**Start with**: FOOTPRINT_QUICK_REFERENCE.md and pick your path (A, B, or C)

**Dive deeper with**: FOOTPRINT_CODE_EXAMPLES.md to see working code

**Reference always**: KICAD_FOOTPRINT_GENERATORS.md for comprehensive details

Happy generating!
