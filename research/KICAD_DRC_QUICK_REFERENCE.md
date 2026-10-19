# KiCad DRC Python API - Quick Reference Card

## Import & Setup

```python
import sys
import pcbnew

# macOS path setup
sys.path.insert(0, '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.9/site-packages')

# Linux: usually already in path
# Windows: sys.path.insert(0, r'C:\Program Files\KiCad\bin')
```

---

## Core Functions

### Load Board
```python
board = pcbnew.LoadBoard('path/to/board.kicad_pcb')
```
**Returns**: `BOARD` object | **Throws**: Exception if file not found

---

### Run DRC & Generate Report
```python
success = pcbnew.WriteDRCReport(
    board,           # BOARD object
    'report.txt',    # Output filename
    pcbnew.MM,       # Units: MM or INCHES
    True             # Report all track errors
)
```
**Returns**: `bool` (True if successful) | **Status**: ⚠ Buggy in KiCad 8.0.1+

---

### Count DRC Violations
```python
count = board.GetMARKERCount()
```
**Returns**: `int` | **Status**: ✓ Stable

---

### Get Single Violation Marker
```python
marker = board.GetMARKER(index)  # 0-based index
msg = marker.GetErrorMessage()
```
**Returns**: `MARKER_PCB` object | **Status**: ✓ Stable

---

### Save Board
```python
pcbnew.SaveBoard('path/to/output.kicad_pcb', board)
```

---

### Get Current Board (GUI Only)
```python
board = pcbnew.GetBoard()  # Only works in PCB Editor context
```

---

## Complete Minimal Example

```python
import pcbnew

# 1. Load board
board = pcbnew.LoadBoard('test.kicad_pcb')

# 2. Run DRC
pcbnew.WriteDRCReport(board, 'drc.txt', pcbnew.MM, True)

# 3. Check results
marker_count = board.GetMARKERCount()
print(f"Found {marker_count} violations")

# 4. Iterate violations
for i in range(marker_count):
    marker = board.GetMARKER(i)
    print(f"  {i}: {marker.GetErrorMessage()}")
```

---

## Units

```python
pcbnew.MM          # Millimeters
pcbnew.INCHES      # Inches (2.54mm/inch)
```

---

## Error Handling Template

```python
import pcbnew
import os

try:
    board = pcbnew.LoadBoard('board.kicad_pcb')

    success = pcbnew.WriteDRCReport(
        board,
        'drc.txt',
        pcbnew.MM,
        True
    )

    if success:
        marker_count = board.GetMARKERCount()
        print(f"DRC found {marker_count} violations")
    else:
        print("WriteDRCReport failed")

except FileNotFoundError as e:
    print(f"File not found: {e}")
except Exception as e:
    print(f"Error: {e}")
    # Fallback to kicad-cli
    os.system("kicad-cli pcb drc board.kicad_pcb -o drc.txt")
```

---

## Batch Processing Template

```python
from pathlib import Path
import pcbnew

for board_path in Path('.').glob('*.kicad_pcb'):
    print(f"Processing {board_path.name}...", end=' ')

    try:
        board = pcbnew.LoadBoard(str(board_path))
        pcbnew.WriteDRCReport(
            board,
            f'{board_path.stem}_drc.txt',
            pcbnew.MM,
            True
        )
        marker_count = board.GetMARKERCount()
        print(f"✓ {marker_count} violations")
    except Exception as e:
        print(f"✗ {e}")
```

---

## MARKER_PCB Methods

```python
marker = board.GetMARKER(0)

# Get error message
msg = marker.GetErrorMessage()  # str

# Get severity
severity = marker.GetSeverity()  # int

# Get position
pos = marker.GetPosition()  # wxPoint with .x, .y

# Get layer (if applicable)
layer = marker.GetLayer()
```

---

## Production DRC (Recommended)

**Use `kicad-cli` instead** for reliability:

```bash
kicad-cli pcb drc board.kicad_pcb -o drc_report.txt
```

Why:
- ✓ More stable (no random crashes)
- ✓ Loads project settings correctly
- ✓ No Python dependency
- ✓ Battle-tested in GUI

---

## Known Issues

| Issue | Workaround |
|-------|-----------|
| **WriteDRCReport() random crashes** | Add try-catch, use kicad-cli fallback |
| **DRC exclusions ignored** | Parse markers, manually filter results |
| **Design rules not loaded (headless)** | Use kicad-cli or load `.kicad_pro` settings |
| **Net classes reset on save** | Don't use LoadBoard→SaveBoard roundtrip |

---

## Python Version Requirements

- **KiCad 6.0+**: Python 3.6+
- **KiCad 8.x**: Python 3.9+
- **KiCad 9.x**: Python 3.10+

Check your KiCad version:
```bash
kicad --version
```

---

## File Paths (by OS)

| OS | pcbnew Module Location |
|---|---|
| **macOS** | `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.x/site-packages/` |
| **Linux** | `/usr/lib/python3/dist-packages/` (varies by distro) |
| **Windows** | `C:\Program Files\KiCad\bin\` (varies by installation) |

---

## Deprecation Notice

⚠ **SWIG Python bindings (pcbnew) are deprecated** and scheduled for removal in **KiCad 10 (Feb 2026)**.

KiCad 9.0+ provides an **IPC API** as the replacement (still in development).

---

## References

- [Official Doxygen API](https://docs.kicad.org/doxygen-python-6.0/namespacepcbnew.html)
- [Developer Docs](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html)
- [Bug: WriteDRCReport Crashes](https://gitlab.com/kicad/code/kicad/-/issues/17504)
- [kicad-python Wrapper](https://github.com/atait/kicad-python)

---

## One-Liner Examples

```python
# Load and check board
import pcbnew; board = pcbnew.LoadBoard('x.kicad_pcb'); pcbnew.WriteDRCReport(board, 'drc.txt', pcbnew.MM, True); print(board.GetMARKERCount())

# Count violations in all boards
from pathlib import Path; import pcbnew; [print(f"{p.name}: {(b:=pcbnew.LoadBoard(str(p))).GetMARKERCount()}") for p in Path('.').glob('*.kicad_pcb')]
```

---

**Last Updated**: March 15, 2026
