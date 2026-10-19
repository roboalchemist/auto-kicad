# KiCad Python DRC API Research (KiCad 8.x)

**Date**: March 15, 2026
**Focus**: Programmatic DRC checks using KiCad's pcbnew Python module

---

## 1. Loading Boards Programmatically

### Basic LoadBoard Usage

**Signature**:
```python
BOARD LoadBoard(str filename) -> BOARD
```

**Example**:
```python
import pcbnew

# Load a board from file
board = pcbnew.LoadBoard('/path/to/board.kicad_pcb')
```

**How it works**:
- `LoadBoard()` accepts a file path and returns a `BOARD` object
- File format is automatically detected based on the filename extension
- Supports `.kicad_pcb` format (KiCad 6+)

### Getting the Current Board (in GUI context)

If you're writing a plugin that runs within the PCB Editor GUI:

```python
import pcbnew

# Get the current board being edited
board = pcbnew.GetBoard()
```

**Note**: `GetBoard()` only works inside the KiCad PCB Editor GUI context. For standalone/headless scripts, use `LoadBoard()`.

### Saving Boards

```python
pcbnew.SaveBoard(filename, board)
```

---

## 2. DRC Execution via Python

### WriteDRCReport() - Primary DRC Method

**Signature**:
```python
bool WriteDRCReport(BOARD aBoard, str aFileName, int aUnits, bool aReportAllTrackErrors) -> bool
```

**Parameters**:
- `aBoard`: BOARD object to check
- `aFileName`: Output file path for DRC report (e.g., `"drc_report.txt"`)
- `aUnits`: Unit system (`pcbnew.MM` or `pcbnew.INCHES`)
- `aReportAllTrackErrors`: Boolean; if `True`, reports all track violations; if `False`, reports only first per net

**Returns**: `True` if successful, `False` on failure

**Example**:
```python
import pcbnew

# Load board
board = pcbnew.LoadBoard('example.kicad_pcb')

# Run DRC and generate report file
success = pcbnew.WriteDRCReport(
    board,
    'drc_output.txt',         # Output report file
    pcbnew.MM,                # Use millimeters
    True                      # Report all track errors
)

if success:
    print("DRC report generated: drc_output.txt")
else:
    print("DRC report generation failed")
```

**Important Limitations**:
- `WriteDRCReport()` has reported issues with random assertion failures in KiCad 8.0.1+ when called multiple times from Python scripts
- The function requires that design rule settings are properly initialized (zones must be valid before calling)
- Unlike the DRC GUI dialog, this does NOT automatically fill zones—zones must be pre-filled

**Bug Report**: [KiCad Issue #17504](https://gitlab.com/kicad/code/kicad/-/issues/17504) documents random SIGTRAP crashes when calling `WriteDRCReport()` repeatedly in KiCad 8.0.1.

---

## 3. Accessing DRC Results Programmatically

### Reading Markers from BOARD

Once DRC has run (or been imported), you can access violation markers:

**BOARD Methods**:
```python
int GetMARKERCount(self) -> int
MARKER_PCB GetMARKER(self, int index) -> MARKER_PCB
```

**Example**:
```python
import pcbnew

# Load board
board = pcbnew.LoadBoard('example.kicad_pcb')

# Run DRC
pcbnew.WriteDRCReport(board, 'drc_report.txt', pcbnew.MM, True)

# Access DRC markers
marker_count = board.GetMARKERCount()
print(f"Total DRC markers: {marker_count}")

for i in range(marker_count):
    marker = board.GetMARKER(i)
    # marker is a MARKER_PCB object
    # Contains position, severity, message, etc.
    print(f"Marker {i}: {marker}")
```

**MARKER_PCB Object Properties**:
- `GetPosition()` - Returns marker position as wxPoint
- `GetErrorMessage()` - Returns violation description text
- `GetSeverity()` - Returns severity level
- `GetLayer()` - Returns layer information

### Parsing DRC Report Files

The `WriteDRCReport()` output is a text file. You can parse it programmatically:

```python
import re

def parse_drc_report(filepath):
    """Parse DRC report file for violations"""
    violations = []

    with open(filepath, 'r') as f:
        for line in f:
            # DRC report format varies by KiCad version
            # Example: "D_PAD net1 pad1 clearance violation"
            if 'Error' in line or 'Warning' in line or 'violation' in line.lower():
                violations.append(line.strip())

    return violations

# Use it
success = pcbnew.WriteDRCReport(board, 'drc.txt', pcbnew.MM, True)
violations = parse_drc_report('drc.txt')
print(f"Found {len(violations)} DRC violations")
```

---

## 4. KiCad 5 vs KiCad 8 Footprint Format Differences

### Format Compatibility

**Key Points**:
- **KiCad 6+ use S-expression format** (`.kicad_pcb` files)
- **KiCad 5 uses a different format** (also `.kicad_pcb` but structurally different)
- **LoadBoard() can read KiCad 5 files**, but when saved, they are converted to KiCad 6+ format

### Migration Implications

When loading a KiCad 5 board with `LoadBoard()` in KiCad 8:
```python
# This works—LoadBoard handles format detection
board = pcbnew.LoadBoard('kicad5_design.kicad_pcb')

# When saved, it's converted to KiCad 8 format
pcbnew.SaveBoard('output.kicad_pcb', board)
```

### Footprint Library Changes

**Important**: KiCad 5 footprint libraries are **no longer maintained** as of KiCad 6+.
- If you have KiCad 5 boards with legacy footprints, they must be re-linked to KiCad 6+ libraries
- Python LoadBoard may fail if footprints cannot be resolved

### Python API Changes (KiCad 5 → KiCad 8)

Several API breaking changes occurred:

**Example**: `PAD.GetParent()` behavior changed:
```python
# KiCad 5:
parent = pad.GetParent()  # Returns FOOTPRINT directly

# KiCad 8+:
parent = pad.GetParent()  # Returns BOARD_ITEM_CONTAINER
# Need to cast:
from pcbnew import FOOTPRINT
footprint = FOOTPRINT.Cast(parent)  # Cast to FOOTPRINT
```

---

## 5. Headless DRC (without GUI)

### Current Limitations

**As of KiCad 9.0**:
- The IPC API (new Python interface) does **NOT** support headless operation
- The legacy SWIG-based `pcbnew` module **DOES** support headless use
- **Deprecation Warning**: The SWIG-based Python bindings are deprecated and scheduled for removal in KiCad 10 (planned Feb 2026)

### Headless Example (Legacy SWIG API)

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.9/site-packages')

import pcbnew

def run_drc_headless(board_path, output_path):
    """Run DRC on a board without opening the GUI"""
    try:
        # Load board
        board = pcbnew.LoadBoard(board_path)

        # Run DRC and generate report
        success = pcbnew.WriteDRCReport(
            board,
            output_path,
            pcbnew.MM,
            True
        )

        if success:
            print(f"DRC successful. Report: {output_path}")
            return 0
        else:
            print("DRC failed")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 2

if __name__ == '__main__':
    board = sys.argv[1] if len(sys.argv) > 1 else 'board.kicad_pcb'
    output = sys.argv[2] if len(sys.argv) > 2 else 'drc_report.txt'
    sys.exit(run_drc_headless(board, output))
```

**Run it**:
```bash
python3 run_drc.py myboard.kicad_pcb myboard_drc.txt
```

### Headless Limitations

1. **No access to project file** - DRC may fail if board references project-specific settings
2. **No design rules imported** - Must have default rules or pre-configured project
3. **Multi-threading issues** - `WriteDRCReport()` has reported race conditions in headless mode
4. **No GUI feedback** - No progress indication; may appear hung on large boards

### Workaround: Using kicad-cli (KiCad 8.0.4+)

For more reliable headless DRC, KiCad 8.0.4+ includes `kicad-cli`:

```bash
# Generate DRC report via CLI
kicad-cli pcb drc myboard.kicad_pcb -o drc_report.txt
```

This is more stable than the Python API approach.

---

## 6. Complete Working Example

### Full Headless DRC Script

```python
#!/usr/bin/env python3
"""
Headless DRC runner for KiCad 8.x
Loads a board, runs DRC, and extracts violation details
"""

import sys
import os
from pathlib import Path

# Import pcbnew (adjust path for your KiCad installation)
try:
    import pcbnew
except ImportError:
    print("Error: pcbnew module not found. Check KiCad installation path.")
    sys.exit(1)

def run_drc_and_parse(board_path, output_dir='drc_output'):
    """
    Run DRC on a board and parse results

    Args:
        board_path: Path to .kicad_pcb file
        output_dir: Directory to write DRC report

    Returns:
        dict: {
            'success': bool,
            'marker_count': int,
            'report_file': str,
            'errors': list of str
        }
    """

    results = {
        'success': False,
        'marker_count': 0,
        'report_file': None,
        'errors': []
    }

    # Validate input
    if not os.path.exists(board_path):
        results['errors'].append(f"Board file not found: {board_path}")
        return results

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    report_file = os.path.join(output_dir, 'drc_report.txt')

    try:
        # Load board
        print(f"Loading board: {board_path}")
        board = pcbnew.LoadBoard(board_path)

        # Run DRC
        print("Running DRC...")
        drc_success = pcbnew.WriteDRCReport(
            board,
            report_file,
            pcbnew.MM,  # Use millimeters
            True        # Report all track errors
        )

        if not drc_success:
            results['errors'].append("WriteDRCReport returned False")
            return results

        # Count markers
        marker_count = board.GetMARKERCount()
        print(f"DRC found {marker_count} markers")

        # Extract marker details
        violations = []
        for i in range(marker_count):
            marker = board.GetMARKER(i)
            violation = {
                'index': i,
                'message': marker.GetErrorMessage(),
                'severity': marker.GetSeverity()
            }
            violations.append(violation)

        # Update results
        results['success'] = True
        results['marker_count'] = marker_count
        results['report_file'] = report_file

        print(f"DRC complete. Report: {report_file}")

        return results

    except Exception as e:
        results['errors'].append(f"Exception: {str(e)}")
        return results

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 drc_runner.py <board.kicad_pcb> [output_dir]")
        sys.exit(1)

    board_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'drc_output'

    results = run_drc_and_parse(board_path, output_dir)

    print("\n=== DRC Results ===")
    print(f"Success: {results['success']}")
    print(f"Markers found: {results['marker_count']}")
    print(f"Report file: {results['report_file']}")

    if results['errors']:
        print("Errors:")
        for error in results['errors']:
            print(f"  - {error}")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
```

**Usage**:
```bash
python3 drc_runner.py myboard.kicad_pcb output_dir
```

---

## 7. Known Issues and Workarounds

### Issue 1: DRC Cannot Run via Python API (Historically)

**Historical Problem**: [KiCad Bug #1600081](https://bugs.launchpad.net/kicad/+bug/1600081)
Early versions of KiCad could not run DRC via the Python API at all.

**Current Status**: `WriteDRCReport()` is available in KiCad 8.x, but has issues:

**Workaround**:
- Use `kicad-cli` for production DRC runs
- Test `WriteDRCReport()` before relying on it for critical workflows

### Issue 2: WriteDRCReport() Random Assertion Failures

**Problem**: [KiCad Issue #17504](https://gitlab.com/kicad/code/kicad/-/issues/17504)
`WriteDRCReport()` crashes with random SIGTRAP in KiCad 8.0.1+ when called repeatedly.

**Symptoms**:
- Crashes after ~300-500 iterations
- Stack trace shows `BOX2::Inflate()` with invalid parameters
- Related to multi-threaded DRC processing

**Workaround**:
```python
# Add error handling
try:
    pcbnew.WriteDRCReport(board, 'drc.txt', pcbnew.MM, True)
except Exception as e:
    print(f"WriteDRCReport failed: {e}")
    # Fall back to kicad-cli
    os.system(f"kicad-cli pcb drc {board_path} -o drc.txt")
```

### Issue 3: Net Class Information Lost on Save

**Problem**: Using `LoadBoard()` then `SaveBoard()` causes net class memberships to be reset.

**Impact**: DRC results become unreliable after round-trip.

**Workaround**:
- Load board from file directly into GetBoard() in GUI context
- Or reload the project file after SaveBoard()

### Issue 4: LoadBoard Doesn't Import Project Settings

**Problem**: `LoadBoard()` loads the `.kicad_pcb` file only; design rules come from project (`.kicad_pro`).

**Workaround**:
```python
# If you need project settings, parse the .kicad_pro file too
import json

board_path = 'myboard.kicad_pcb'
project_path = 'myproject.kicad_pro'

# Load project settings
with open(project_path, 'r') as f:
    project_data = json.load(f)

# Extract design rule settings if needed
drc_settings = project_data.get('design_settings', {})

# Load board
board = pcbnew.LoadBoard(board_path)
```

### Issue 5: DRC Exclusions Ignored in Python API

**Problem**: [KiCad Issue #11562](https://gitlab.com/kicad/code/kicad/-/issues/11562)
DRC exclusions marked in the GUI are ignored when running DRC via Python API.

**Workaround**: Manually filter results based on exclusion list from `.kicad_pro`.

---

## 8. Recommended Best Practices

### For Headless DRC (Production)

**✓ Use kicad-cli instead of Python API**:
```bash
kicad-cli pcb drc board.kicad_pcb -o report.txt
```

**Why**:
- More stable and tested
- Properly initializes all design rules from project
- No Python dependency on KiCad internals

### For GUI Plugins

**✓ Use GetBoard() + WriteDRCReport()**:
```python
board = pcbnew.GetBoard()
pcbnew.WriteDRCReport(board, 'report.txt', pcbnew.MM, True)
```

**Why**:
- Board is already fully initialized with project settings
- GetBoard() provides the editor context

### For Custom DRC Logic

**✓ Parse markers manually**:
```python
# After WriteDRCReport or GUI-based DRC
marker_count = board.GetMARKERCount()
for i in range(marker_count):
    marker = board.GetMARKER(i)
    # Process marker...
```

### For Future-Proofing

**⚠ IPC API Coming in KiCad 10+**

The SWIG-based `pcbnew` module will be removed in KiCad 10 (Feb 2026). KiCad 9.0 introduced an **IPC API** (Inter-Process Communication) as the new standard:

```python
# Future approach (KiCad 9+)
import kicad_ipc

# This will replace the pcbnew module
# Details pending as of March 2026
```

---

## 9. Summary Table

| Feature | Available | Notes |
|---------|-----------|-------|
| `LoadBoard()` | ✓ KiCad 5+ | Load `.kicad_pcb` files |
| `WriteDRCReport()` | ✓ KiCad 6.0+ | Run DRC headless (has bugs in 8.0.1+) |
| `GetMARKER()` / `GetMARKERCount()` | ✓ All versions | Access DRC violation markers |
| `GetBoard()` | ✓ GUI only | Get current board in editor |
| Headless GUI-free operation | ✓ With caveats | Design rules not loaded; use `kicad-cli` preferred |
| IPC API | ⚠ KiCad 9.0 beta | Scheduled to replace SWIG bindings in KiCad 10 |

---

## 10. References

### Official Documentation
- [KiCad Pcbnew Python Scripting - Doxygen API Reference (KiCad 6.0)](https://docs.kicad.org/doxygen-python-6.0/namespacepcbnew.html)
- [KiCad PCB Python Bindings - Developer Docs](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html)
- [KiCad 8.0 PCB Editor Documentation](https://docs.kicad.org/8.0/en/pcbnew/pcbnew.html)

### Community Resources
- [KiCad.info Forums - Python Scripting Tutorials](https://forum.kicad.info/t/tutorials-on-python-scripting-in-pcbnew/5333)
- [atait/kicad-python - Cross-version Python API wrapper for KiCad v5-v9](https://github.com/atait/kicad-python)
- [Climbers.net - KiCad v6 Plugin Script Cheatsheet](https://climbers.net/sbc/kicad-plugin-script-cheatsheet/)
- [Programmatic Layout with KiCad and Python - Jeff McBride](https://jeffmcbride.net/programmatic-layout-with-kicad-and-python/)

### Bug Reports
- [KiCad Issue #17504 - WriteDRCReport random assert fail](https://gitlab.com/kicad/code/kicad/-/issues/17504)
- [KiCad Bug #1600081 - DRC unable to be performed via Python scripting API](https://bugs.launchpad.net/kicad/+bug/1600081)
- [KiCad Issue #11562 - DRC exclusions ignored in Python API](https://gitlab.com/kicad/code/kicad/-/issues/11562)

### Code Examples
- [KiCad Source - pcbnew_scripting_helpers.cpp](https://docs.kicad.org/doxygen/pcbnew__scripting__helpers_8cpp_source.html)
- [KiCad Source - drc_engine.h](https://docs.kicad.org/doxygen/drc__engine_8h.html)

---

## Appendix: Python Environment Setup

### macOS (with KiCad.app)

```bash
# Set up Python path for KiCad on macOS
export PYTHONPATH="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.9/site-packages:$PYTHONPATH"

# Or set in script
import sys
sys.path.insert(0, '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.9/site-packages')

import pcbnew
```

### Linux

```bash
# Usually pcbnew is in the system Python path
python3 -c "import pcbnew; print(pcbnew.__file__)"
```

### Windows

```python
# KiCad installs pcbnew in the KiCad bin directory
import sys
sys.path.insert(0, r'C:\Program Files\KiCad\bin')
import pcbnew
```

---

**Last Updated**: March 15, 2026
