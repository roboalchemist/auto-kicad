# KiCad Python DRC API Research Summary

**Research Date**: March 15, 2026
**KiCad Focus**: Version 8.x
**Topic**: Programmatic Design Rule Checking (DRC) using Python

## Files in This Directory

### 1. `KICAD_PYTHON_DRC_RESEARCH.md`
**Comprehensive reference document** covering:
- Loading boards with `LoadBoard()` 
- Running DRC via `WriteDRCReport()`
- Accessing DRC violation markers (`GetMARKER()`, `GetMARKERCount()`)
- KiCad 5 vs 8 footprint format compatibility
- Headless DRC (GUI-free operation)
- Known issues and workarounds
- Official documentation links

**Key Findings**:
- `WriteDRCReport()` is available in KiCad 6.0+ but has random crash bugs in 8.0.1+
- `GetMARKER()`/`GetMARKERCount()` methods allow reading DRC violations
- Headless operation supported but limited (design rules not loaded)
- `kicad-cli pcb drc` is more stable for production headless DRC

### 2. `KICAD_DRC_CODE_EXAMPLES.py`
**Practical Python code snippets** with 6 ready-to-use examples:

```python
example_basic_drc(board_path)              # 1. Generate DRC report
example_read_markers(board_path)           # 2. Read violation markers
example_parse_drc_report(report_file)      # 3. Parse report file
example_batch_drc(board_dir)               # 4. Batch process multiple boards
example_robust_drc(board_path)             # 5. Full pipeline with error handling
example_drc_with_fallback(board_path)      # 6. Fallback to kicad-cli
```

All examples include error handling and detailed comments.

## Quick Start

### Load a Board and Run DRC

```python
import pcbnew

# Load board
board = pcbnew.LoadBoard('myboard.kicad_pcb')

# Run DRC
success = pcbnew.WriteDRCReport(
    board,
    'drc_report.txt',  # Output file
    pcbnew.MM,         # Units
    True               # Report all errors
)

# Read markers
marker_count = board.GetMARKERCount()
print(f"DRC found {marker_count} violations")

for i in range(marker_count):
    marker = board.GetMARKER(i)
    print(marker.GetErrorMessage())
```

### Python Environment Setup

**macOS**:
```bash
export PYTHONPATH="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.9/site-packages:$PYTHONPATH"
python3 script.py
```

**Linux**: Usually in system path already

**Windows**:
```python
import sys
sys.path.insert(0, r'C:\Program Files\KiCad\bin')
```

## Key API Functions

| Function | Purpose | Status |
|----------|---------|--------|
| `LoadBoard(path)` | Load `.kicad_pcb` file | ✓ Stable |
| `WriteDRCReport(board, path, units, all_errors)` | Run DRC, write report | ⚠ Has bugs in 8.0.1+ |
| `GetMARKERCount()` | Count DRC violations | ✓ Stable |
| `GetMARKER(index)` | Get violation marker | ✓ Stable |
| `SaveBoard(path, board)` | Save board to file | ✓ Stable |
| `GetBoard()` | Get current board (GUI only) | ✓ GUI context only |

## Important Limitations

1. **No Headless Project Settings**
   - `LoadBoard()` doesn't load design rules from `.kicad_pro`
   - DRC results may be unreliable without proper project context
   - Workaround: Use `kicad-cli` for production DRC

2. **Random Crashes in WriteDRCReport()**
   - KiCad 8.0.1+ crashes with SIGTRAP when called multiple times
   - [Issue #17504](https://gitlab.com/kicad/code/kicad/-/issues/17504)
   - Workaround: Add exception handling, retry with fallback

3. **DRC Exclusions Ignored**
   - Exclusions from GUI are not applied in Python API
   - [Issue #11562](https://gitlab.com/kicad/code/kicad/-/issues/11562)

4. **Format Compatibility**
   - KiCad 5 boards can be loaded but converted to KiCad 6+ format on save
   - Footprint libraries must be updated (KiCad 5 libs not maintained)

## Recommended Approach

### For Production DRC Automation
**Use `kicad-cli` instead of Python API**:
```bash
kicad-cli pcb drc board.kicad_pcb -o report.txt
```

**Why**: More stable, properly initializes project settings, no Python dependency

### For GUI Plugins
**Use `GetBoard()` + `WriteDRCReport()`**:
```python
board = pcbnew.GetBoard()  # Get current board from editor
pcbnew.WriteDRCReport(board, 'report.txt', pcbnew.MM, True)
```

**Why**: Board is fully initialized with project settings

### For Custom DRC Logic
**Parse markers manually**:
```python
for i in range(board.GetMARKERCount()):
    marker = board.GetMARKER(i)
    # Process violation...
```

## Future: IPC API (KiCad 10+)

The SWIG-based `pcbnew` module is **deprecated** and scheduled for removal in **KiCad 10 (Feb 2026)**.

KiCad 9.0 introduced an **IPC API** as the replacement:
- More stable, language-agnostic
- Better long-term support
- Details still in development as of March 2026

## References

### Official Docs
- [Doxygen Python API (KiCad 6.0)](https://docs.kicad.org/doxygen-python-6.0/namespacepcbnew.html)
- [KiCad PCB Bindings (Dev Docs)](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html)
- [KiCad 8.0 PCB Editor Manual](https://docs.kicad.org/8.0/en/pcbnew/pcbnew.html)

### Bug Reports
- [Issue #17504 - WriteDRCReport random crashes](https://gitlab.com/kicad/code/kicad/-/issues/17504)
- [Issue #11562 - DRC exclusions ignored](https://gitlab.com/kicad/code/kicad/-/issues/11562)
- [Bug #1600081 - DRC via Python API](https://bugs.launchpad.net/kicad/+bug/1600081)

### Community
- [atait/kicad-python - Cross-version wrapper](https://github.com/atait/kicad-python)
- [KiCad.info Forums - Python Scripting](https://forum.kicad.info/t/tutorials-on-python-scripting-in-pcbnew/5333)

## Usage Examples

### Example: Run DRC on Board
```bash
python3 -c "
import pcbnew
board = pcbnew.LoadBoard('test.kicad_pcb')
pcbnew.WriteDRCReport(board, 'drc.txt', pcbnew.MM, True)
print(f'Violations: {board.GetMARKERCount()}')
"
```

### Example: Batch Process All Boards in Directory
```python
from pathlib import Path
import pcbnew

for board_path in Path('.').glob('*.kicad_pcb'):
    board = pcbnew.LoadBoard(str(board_path))
    pcbnew.WriteDRCReport(board, f'{board_path.stem}_drc.txt', pcbnew.MM, True)
    print(f'{board_path.name}: {board.GetMARKERCount()} violations')
```

---

**Last Updated**: March 15, 2026
**Researcher**: Claude Code
