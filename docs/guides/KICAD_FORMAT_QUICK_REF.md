# KiCad Format Quick Reference: Footprints (5 vs 8)

**TL;DR**: KiCad 8 reads both formats. To convert: open in KiCad 8 Editor + Save. No explicit conversion needed for JLC2KiCad_lib output.

---

## Quick Comparison

| Aspect | KiCad 5 | KiCad 8 |
|--------|---------|---------|
| **Root** | `(module NAME` | `(footprint "NAME"` |
| **Version** | `(version 4)` | `(version 20240108)` |
| **Generator** | (optional) | `(generator "pcbnew")` |
| **Pad name** | `(pad 1 ...` | `(pad "1" ...` |
| **Layer** | `(layer F.Cu)` | `(layer "F.Cu")` |
| **Net name** | `(net 1 GND)` | `(net 1 "GND")` |
| **Geometry** | ✓ Same | ✓ Same |

---

## Simple Conversion (Manual)

### Method 1: KiCad GUI (1 minute)
```bash
# Open footprint in KiCad 8 Footprint Editor
/Applications/KiCad/KiCad.app/Contents/MacOS/pcbnew old.kicad_mod

# In Editor:
#   File > Save (or Ctrl+S)
#   → Automatically converts format
#   → Done!
```

### Method 2: Python Script (Batch)
```bash
python scripts/convert_footprint_kicad5_to_8.py old.kicad_mod new.kicad_mod

# Verify
/Applications/KiCad/KiCad.app/Contents/MacOS/pcbnew new.kicad_mod
```

### Method 3: Regex Replacement (Quick)
```bash
# One-liner conversions:

# 1. Module → Footprint
sed -i '' 's/^(module \([^ ]*\)/(footprint "\1"/' file.kicad_mod

# 2. Add version (after footprint line)
sed -i '' '/^(footprint/a\
\	(version 20240108)
' file.kicad_mod

# 3. Add generator (if missing)
sed -i '' '/^(footprint/a\
\	(generator "pcbnew")
' file.kicad_mod

# 4. Quote layer names
sed -i '' 's/(layer \([A-Z.]*\))/(layer "\1")/g' file.kicad_mod

# 5. Quote pad numbers
sed -i '' 's/(pad \([0-9]*\) /(pad "\1" /g' file.kicad_mod
```

---

## Programmatic Verification

### Load and Check (Python)
```python
import pcbnew

# KiCad 8 pcbnew loads both KiCad 5 and 8 formats
fp = pcbnew.FootprintLoad("old.kicad_mod", "")

if fp:
    print(f"✓ Loaded: {fp.GetReference()}")
    print(f"  Pads: {fp.GetPadCount()}")
    print(f"  Format compatible with KiCad 8")
else:
    print("✗ Failed to load")
```

### Regex Detection
```python
import re

with open("footprint.kicad_mod") as f:
    content = f.read()

if re.search(r'^\s*\(module\s+', content, re.MULTILINE):
    print("KiCad 5 format (module ...)")
elif re.search(r'^\s*\(footprint\s+', content, re.MULTILINE):
    print("KiCad 8 format (footprint ...)")
```

---

## JLC2KiCad_lib Status

| Library Output | KiCad 8 | DRC |
|---|---|---|
| Symbols (`.kicad_sym`) | ✓ Native | ✓ Works |
| Footprints (`.kicad_mod`) | ✓ Native | ✓ GUI OK, CLI partial |
| 3D Models (`.step`/`.wrl`) | ✓ Works | N/A |

**Action**: None required. Use JLC2KiCad_lib output directly.

---

## DRC Notes

### GUI DRC (Recommended)
```bash
# Open board in KiCad 8 GUI
pcbnew board.kicad_pcb

# Inspect > Design Rule Checker
# → JLC2KiCad_lib footprints work fine
```

### CLI DRC (Partial Support)
```bash
# May fail on complex footprints
kicad-cli pcb check board.kicad_pcb

# Workaround: use Python DRC instead
python demo/drc_rules.py render_data.json
```

---

## Real-World Examples

### Before (KiCad 5)
```lisp
(module SOT-23-5
  (version 4)
  (layer F.Cu)
  (attr smd)
  (pad 1 smd roundrect (at -1.1 0.95) (size 1.06 0.65)
    (layers F.Cu F.Paste F.Mask))
)
```

### After (KiCad 8)
```lisp
(footprint "SOT-23-5"
  (version 20240108)
  (generator "pcbnew")
  (layer "F.Cu")
  (attr smd)
  (pad "1" smd roundrect
    (at -1.1 0.95)
    (size 1.06 0.65)
    (layers "F.Cu" "F.Paste" "F.Mask")
  )
)
```

---

## Compatibility Matrix

| Scenario | Works? | Steps |
|----------|--------|-------|
| KiCad 5 `.kicad_mod` in KiCad 8 Editor | ✓ | Just open — auto-converts on save |
| `pcbnew.FootprintLoad(KiCad5)` | ✓ | Python detects format automatically |
| JLC2KiCad_lib in KiCad 8 PCB | ✓ | Use directly, no conversion |
| GUI DRC on JLC2KiCad_lib | ✓ | Works out of box |
| CLI DRC on JLC2KiCad_lib | ⚠ | May fail; use GUI or Python DRC |
| kicad-claude layout.py parser | ✓ | Regex supports both formats |

---

## Troubleshooting

### Footprint won't load in KiCad 8
- Symptom: "Cannot load footprint" error
- Solution:
  ```bash
  python scripts/convert_footprint_kicad5_to_8.py bad.kicad_mod fixed.kicad_mod
  ```

### DRC reports errors on valid JLC2KiCad_lib footprint
- Symptom: CLI DRC fails, GUI DRC works
- Solution: Use GUI DRC or Python DRC script

### Pad numbers missing after conversion
- Symptom: Regex conversion loses pad numbering
- Solution: Use KiCad 8 Editor to re-save (preserves all data)

---

## References

- **Full documentation**: `KICAD_5_TO_8_FOOTPRINT_CONVERSION.md`
- **Conversion script**: `scripts/convert_footprint_kicad5_to_8.py`
- **Parser**: `demo/layout.py` (supports both formats natively)
