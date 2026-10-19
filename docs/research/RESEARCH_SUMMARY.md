# KiCad 5 to KiCad 8 Footprint Format Research — Summary

**Completed**: 2026-03-15
**Status**: ✅ Comprehensive research with actionable recommendations
**Files Created**: 4 documentation files + 1 conversion tool

---

## What Was Researched

1. **Key differences** between KiCad 5 `(module ...)` and KiCad 8 `(footprint ...)` formats
2. **Conversion approaches**: GUI, Python scripts, regex patterns, CLI tools
3. **Automatic conversion**: Does KiCad 8 auto-convert on load/save?
4. **pcbnew.FootprintLoad() compatibility**: Can it read KiCad 5 format?
5. **JLC2KiCad_lib output format**: What format does it generate? Any DRC issues?

---

## Quick Answers

| Question | Answer |
|----------|--------|
| **Do I need to convert KiCad 5 footprints to KiCad 8?** | No — KiCad 8 reads both automatically |
| **Does JLC2KiCad_lib generate compatible footprints?** | Yes — outputs KiCad 6+ format natively |
| **Can pcbnew.FootprintLoad() read KiCad 5?** | Yes — format detection is automatic |
| **Does KiCad 8 auto-convert on save?** | Yes — opens KiCad 5, saves as KiCad 8 |
| **Is this a blocker for kicad-claude?** | No — project already handles both formats |

---

## Files Created

### Documentation (Read These)

1. **../guides/KICAD_5_TO_8_FOOTPRINT_CONVERSION.md** (comprehensive, 13 KB)
   - Full technical breakdown of format differences
   - 5 different conversion methods with code examples
   - JLC2KiCad_lib analysis and DRC compatibility
   - Real-world examples and troubleshooting
   - **Read this for**: Complete understanding of the formats

2. **../guides/KICAD_FORMAT_QUICK_REF.md** (quick reference, 3 KB)
   - One-page comparison table
   - TL;DR conversion methods
   - Compatibility matrix
   - Simple examples
   - **Read this for**: Quick lookup and quick conversion

3. **RESEARCH_FINDINGS_FOOTPRINT_FORMAT.md** (research report, 5 KB)
   - Executive summary of findings
   - Analysis by tool/component
   - Known issues and workarounds
   - Test plan for validation
   - **Read this for**: Project integration and next steps

4. **RESEARCH_SUMMARY.md** (this file)
   - Navigation guide to all resources
   - Quick decision tree
   - Next steps recommendations

### Tools (Use These)

5. **scripts/convert_footprint_kicad5_to_8.py** (conversion utility, 4 KB)
   - Automated batch conversion tool
   - Supports single file or batch directory conversion
   - Format detection and verification
   - Verbose output for debugging
   - **Use this for**: Converting legacy KiCad 5 libraries

---

## Decision Tree: Do I Need to Convert?

```
Do you have legacy KiCad 5 footprints?
├─ NO → You're good! Stop here.
│
└─ YES → Do you want to convert them?
   ├─ NO → You're still good! KiCad 8 reads both formats.
   │       Just use them as-is.
   │
   └─ YES → How do you want to convert?
      ├─ GUI (easiest, 1 minute per file)
      │  → Open in KiCad 8 Footprint Editor
      │  → File > Save
      │  → Done!
      │
      ├─ Automated (best for batch)
      │  → python scripts/convert_footprint_kicad5_to_8.py old.kicad_mod new.kicad_mod
      │
      └─ Manual regex (advanced)
         → See ../guides/KICAD_FORMAT_QUICK_REF.md section "Method 3"
```

---

## Key Findings (TL;DR)

### Format Differences (Syntactic Only)
```
KiCad 5                      KiCad 8
(module SOT-23               (footprint "SOT-23"
  (version 4)                 (version 20240108)
  (pad 1 ...                  (generator "pcbnew")
    (layers F.Cu F.Mask))     (pad "1" ...
                                (layers "F.Cu" "F.Mask"))
```

**Changed**: Keywords, version format, quoting
**Unchanged**: Geometry, layers, electrical properties

### Compatibility Status
✅ KiCad 8 reads KiCad 5 format
✅ JLC2KiCad_lib outputs modern format
✅ pcbnew API handles both formats
✅ layout.py parser supports both
✅ GUI DRC works fine
⚠ CLI DRC has partial support (use GUI instead)

### No Action Required
For **kicad-claude** project:
- JLC2KiCad_lib output: already compatible
- layout.py parser: already dual-format aware
- Existing demo pipeline: works without changes
- DRC validation: use GUI, not kicad-cli

---

## Conversion Methods (Pick One)

### Method 1: KiCad GUI (Recommended for Users)
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/pcbnew old.kicad_mod
# In Editor: File > Save
# Done! Auto-converts to KiCad 8 format
```

### Method 2: Python Script (Best for Batch)
```bash
python scripts/convert_footprint_kicad5_to_8.py old.kicad_mod new.kicad_mod

# Batch convert directory
for f in *.kicad_mod; do
    python scripts/convert_footprint_kicad5_to_8.py "$f"
done
```

### Method 3: One-Liners (Quick & Dirty)
```bash
sed -i '' 's/(module \([^ ]*\)/(footprint "\1"/' file.kicad_mod
sed -i '' 's/(version [0-9])/(version 20240108)/' file.kicad_mod
sed -i '' 's/(pad \([0-9]*\) /(pad "\1" /g' file.kicad_mod
sed -i '' 's/(layer \([A-Z.]*\))/(layer "\1")/g' file.kicad_mod
```

---

## JLC2KiCad_lib Status

| Aspect | Status | Notes |
|--------|--------|-------|
| Footprints | ✅ Compatible | Outputs KiCad 6+ native format |
| Symbols | ✅ Compatible | Outputs KiCad 6+ format |
| 3D Models | ✅ Compatible | STEP + VRML support |
| DRC (GUI) | ✅ Works | No issues with pcbnew GUI DRC |
| DRC (CLI) | ⚠ Partial | May fail on complex footprints |

**Action**: Use JLC2KiCad_lib output directly — no conversion needed.

---

## Integration with kicad-claude

### layout.py Parser
Already handles both formats:
```python
r'(  \((?:footprint|module)\s.*?...'  # Matches both (footprint) and (module)
```

### demo/blinker.py Pipeline
Uses JLC2KiCad_lib directly — no conversion step needed.

### DRC Validation
Use GUI DRC instead of kicad-cli:
```bash
# ✅ Recommended
pcbnew board.kicad_pcb
# Inspect > Design Rule Checker

# ⚠ Alternative (may fail on complex footprints)
kicad-cli pcb check board.kicad_pcb

# ✅ Python DRC (most reliable)
python demo/drc_rules.py render_data.json
```

---

## When to Use Each Resource

### ../guides/KICAD_5_TO_8_FOOTPRINT_CONVERSION.md
**Read if you need**:
- Deep dive into format structure
- All 5 conversion methods with examples
- Full analysis of tool compatibility
- Real-world KiCad 5 → 8 examples
- Detailed troubleshooting

### ../guides/KICAD_FORMAT_QUICK_REF.md
**Read if you need**:
- Quick conversion method lookup
- One-page comparison
- Simple real-world examples
- Troubleshooting quick start

### RESEARCH_FINDINGS_FOOTPRINT_FORMAT.md
**Read if you need**:
- Summary of all findings
- Tool-by-tool compatibility analysis
- Integration strategy for project
- Test plan

### scripts/convert_footprint_kicad5_to_8.py
**Use if you need**:
- Batch convert legacy KiCad 5 libraries
- Automated format detection
- Reliable conversion with verification

---

## Recommendations

### For Immediate Use
✅ **No changes needed** — kicad-claude is already compatible with both formats

### For Documentation
📝 **Optional but recommended**:
- Add format compatibility note to `.agents/CLAUDE.md`
- Link to conversion resources in README
- Note that GUI DRC is preferred over CLI

### For Future Work
- If users report KiCad 5 footprint issues, conversion script is ready
- If DRC failures occur, switch to GUI DRC + Python script
- If symbol generation is needed later, consider pcbnew symbol API (more robust than JLC2KiCad_lib's string concatenation)

---

## What's Next?

### Step 1: Choose Your Option
Pick one based on your needs:

| Your Situation | Do This |
|---|---|
| **Using kicad-claude as-is** | ✅ Nothing — you're all set |
| **Converting legacy KiCad 5 library** | Run `scripts/convert_footprint_kicad5_to_8.py` |
| **Need DRC on JLC2KiCad_lib footprints** | Use pcbnew GUI DRC (Inspect > Design Rule Checker) |
| **Writing docs for users** | Link to ../guides/KICAD_FORMAT_QUICK_REF.md |
| **Troubleshooting format issues** | Check RESEARCH_FINDINGS_FOOTPRINT_FORMAT.md |

### Step 2: Reference These Docs
- **For you**: RESEARCH_FINDINGS_FOOTPRINT_FORMAT.md
- **For users**: ../guides/KICAD_FORMAT_QUICK_REF.md
- **For deep dive**: ../guides/KICAD_5_TO_8_FOOTPRINT_CONVERSION.md

### Step 3: Keep Script Handy
```bash
scripts/convert_footprint_kicad5_to_8.py
```
Available for batch conversion if needed in future.

---

## File Locations

```
the repository root
├── ../guides/KICAD_5_TO_8_FOOTPRINT_CONVERSION.md        (13 KB, comprehensive)
├── ../guides/KICAD_FORMAT_QUICK_REF.md                   (3 KB, quick ref)
├── RESEARCH_FINDINGS_FOOTPRINT_FORMAT.md       (5 KB, findings)
├── RESEARCH_SUMMARY.md                         (this file)
└── scripts/
    └── convert_footprint_kicad5_to_8.py        (4 KB, tool)
```

---

## One-Sentence Summary

**KiCad 8 automatically handles both KiCad 5 and modern footprint formats — no conversion needed for kicad-claude, but tools and documentation are available if users need legacy support.**

---

## Questions?

Refer to:
1. **Quick answer?** → ../guides/KICAD_FORMAT_QUICK_REF.md
2. **How does it work?** → ../guides/KICAD_5_TO_8_FOOTPRINT_CONVERSION.md
3. **Project integration?** → RESEARCH_FINDINGS_FOOTPRINT_FORMAT.md
4. **Convert a file?** → `python scripts/convert_footprint_kicad5_to_8.py`

---

**Research completed by**: kicad-claude analysis
**Date**: 2026-03-15
**Status**: ✅ Ready for use
