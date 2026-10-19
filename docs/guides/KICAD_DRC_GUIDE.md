# KiCad DRC (Design Rule Check) — Complete Programmatic Guide

Research and implementation guide for running KiCad DRC from the command line and Python API, with focus on KiCad 8.x/9.x.

## Quick Reference

### Minimal CLI Command
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc board.kicad_pcb --format json --severity-all
```

### Minimal Python Example
```python
import subprocess, json
result = subprocess.run([
    '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
    'pcb', 'drc', 'board.kicad_pcb',
    '--format', 'json', '--severity-all'
], capture_output=True, text=True)
data = json.loads(result.stdout)
print(f"Violations: {len(data['violations'])}")
```

---

## Part 1: kicad-cli pcb drc

### Availability & Installation

**KiCad Versions Supported**: 8.0+, 9.x (tested on 9.0.4)

**Platform Locations**:

| OS | Path |
|----|------|
| macOS | `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` |
| Linux | `/usr/bin/kicad-cli` or `which kicad-cli` |
| Windows | `C:\Program Files\KiCad\kicad-cli.exe` |

**Version Check**:
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli --version
# Output: 9.0.4
```

### Command Syntax & Help

```
Usage: kicad-cli pcb drc [OPTIONS] INPUT_FILE

Runs the Design Rules Check (DRC) on the PCB and creates a report

Positional arguments:
  INPUT_FILE              Input .kicad_pcb file (required)

Optional arguments:
  -h, --help              Shows help message and exits

  -o, --output OUTPUT_FILE
                          Output file path
                          default: stdout (printed to terminal)
                          format determined by --format flag

  -D, --define-var KEY=VALUE
                          Overrides or adds project variables
                          can be used multiple times:
                          -D key1=val1 -D key2=val2

  --format FORMAT         Output format: 'json' or 'report'
                          default: "report" (human-readable text)
                          json: structured JSON for parsing

  --all-track-errors      Report all errors for each track
                          without flag: multiple errors on same segment consolidated
                          with flag: every violation on every segment reported

  --schematic-parity      Test for parity between PCB and schematic
                          requires .kicad_sch in same project directory
                          checks: net connectivity, reference designator match

  --units UNITS           Report units: 'in', 'mm', 'mils'
                          default: "mm"
                          note: internal calculations always metric, only output changes

  --severity-all          Report all violations (errors + warnings + exclusions)
  --severity-error        Report DRC error-level violations ONLY
  --severity-warning      Report DRC warning-level violations ONLY
  --severity-exclusions   Report excluded DRC violations ONLY
                          flags can be combined: --severity-error --severity-warning

  --exit-code-violations  Return nonzero exit code if ANY violations exist
                          useful for CI/CD scripts and automation
                          exit code 0: no violations
                          exit code 1: violations found
                          exit code 3: failed to load board
```

### Usage Examples

#### Example 1: Basic JSON Output
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc demo/blinker.kicad_pcb \
  --format json --severity-all
```

Output to stdout (JSON), can be piped to file:
```bash
... --format json --severity-all > drc_report.json
```

#### Example 2: Human-Readable Report
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc demo/blinker.kicad_pcb \
  --format report
```

#### Example 3: Exit Code for CI/CD
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc demo/blinker.kicad_pcb \
  --severity-all --exit-code-violations

if [ $? -eq 0 ]; then
  echo "DRC passed"
else
  echo "DRC violations found"
fi
```

#### Example 4: Custom Units and Output File
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc demo/blinker.kicad_pcb \
  --format json --units mils --output drc_report.json --severity-all
```

#### Example 5: Errors Only, All Track Details
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc demo/blinker.kicad_pcb \
  --format json --severity-error --all-track-errors --output errors_only.json
```

#### Example 6: With Schematic Parity Check
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc demo/blinker.kicad_pcb \
  --format json --schematic-parity --output drc_with_parity.json
```

#### Example 7: Project Variables Override
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc demo/blinker.kicad_pcb \
  --format json \
  -D CLEARANCE_MIN=0.2mm \
  -D VIA_MIN_SIZE=0.3mm \
  -D TRACE_MIN_WIDTH=0.15mm
```

### JSON Output Format

The JSON output includes a complete record of all DRC violations. Here's the structure:

```json
{
  "version": 1,
  "violations": [
    {
      "type": "clearance",
      "severity": "error",
      "description": "Track to track clearance",
      "items": [
        {
          "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
          "reference": "GND or net name",
          "pos_x": 10.5,
          "pos_y": 20.3,
          "layer": "F.Cu"
        },
        {
          "uuid": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
          "reference": "VCC or net name",
          "pos_x": 10.7,
          "pos_y": 20.2,
          "layer": "F.Cu"
        }
      ]
    },
    {
      "type": "via_hole_clearance",
      "severity": "warning",
      "description": "Via hole clearance",
      "items": [...]
    },
    {
      "type": "unconnected_items",
      "severity": "error",
      "description": "Unconnected pad",
      "items": [
        {
          "uuid": "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
          "reference": "U1.1 or net name",
          "pos_x": 5.0,
          "pos_y": 15.0
        }
      ]
    }
  ],
  "unconnected_items": [
    {
      "uuid": "...",
      "reference": "Net name",
      "pos_x": 5.0,
      "pos_y": 15.0
    }
  ]
}
```

### Violation Types

| Type | Description | Typical Severity |
|------|-------------|------------------|
| `clearance` | Insufficient spacing between traces | error |
| `via_hole_clearance` | Via hole too close to trace or pad | warning/error |
| `track_width` | Track width below DRC minimum | error |
| `annular_ring` | Via annular ring below minimum | error |
| `copper_to_edge` | Copper feature too close to board edge | warning/error |
| `via_through_hole` | Via connects to wrong layers | error |
| `unconnected_items` | Dangling pads or net segments | warning/error |
| `missing_footprint` | Referenced footprint not found in library | error |
| `silkscreen_overlap` | Silkscreen overlaps pads or vias | warning |
| `coupler_clearance` | Differential pair spacing insufficient | warning |
| `hole_clearance` | Drill hole clearance violation | error |
| `net_conflict` | Net assignment conflict | error |
| `pth_inside_courtyard` | PTH pad inside courtyard boundary | warning |

---

## Part 2: Python Scripting

### Environment Setup

KiCad includes a Python interpreter with the `pcbnew` module. Use **KiCad's Python**, not your system Python:

```bash
# macOS (KiCad.app)
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3

# Linux (system Python, if kicad module installed)
python3

# Windows
"C:\Program Files\KiCad\python.exe"
```

### Option A: Subprocess Wrapper (Recommended)

Use `subprocess` to call `kicad-cli` from your Python script:

```python
#!/usr/bin/env python3
"""Simple DRC runner via subprocess."""

import json
import subprocess
import sys
from pathlib import Path

def run_drc(pcb_file):
    """Run DRC and return parsed JSON."""
    kicad_cli = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')

    result = subprocess.run([
        str(kicad_cli), 'pcb', 'drc',
        str(pcb_file),
        '--format', 'json',
        '--severity-all'
    ], capture_output=True, text=True)

    if result.returncode not in [0, 1]:  # 0=OK, 1=violations (still valid)
        print(f"Error running DRC: {result.stderr}")
        sys.exit(1)

    return json.loads(result.stdout)

if __name__ == '__main__':
    data = run_drc('demo/blinker.kicad_pcb')

    violations = data.get('violations', [])
    print(f"Total violations: {len(violations)}")

    for v in violations:
        print(f"  {v['severity'].upper()}: {v['type']} - {v['description']}")
        for item in v.get('items', [])[:1]:  # Show first occurrence
            print(f"    at ({item['pos_x']}, {item['pos_y']})")
```

**Advantages**:
- Works with any Python version (system Python, venv, pyenv, etc.)
- Most reliable
- Easy to integrate with CI/CD tools
- No dependency on KiCad Python API changes

**Disadvantages**:
- Subprocess overhead (minor)
- Can't directly access board objects

### Option B: Direct pcbnew Module (Advanced)

For custom DRC checks, use KiCad's `pcbnew` module:

```python
#!/usr/bin/env python3
"""Direct board analysis using pcbnew."""

import sys
from pathlib import Path

# Add KiCad Python path (macOS)
sys.path.insert(0, '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.11/site-packages')

import pcbnew

def analyze_board(pcb_file):
    """Load board and analyze footprints, tracks, pads."""

    # Load board
    board = pcbnew.LoadBoard(pcb_file)
    if not board:
        print(f"Failed to load {pcb_file}")
        return False

    print(f"Board: {board.GetFileName()}")
    print(f"Board size: {board.GetBoardEdgesBoundingBox()}")

    # Get all footprints
    footprints = board.GetFootprints()
    print(f"\nFootprints: {len(footprints)}")
    for fp in footprints:
        print(f"  {fp.GetReference()}: {fp.GetFPID()} at ({fp.GetPosition()})")

    # Get all tracks
    tracks = board.GetTracks()
    print(f"\nTracks: {len(tracks)}")
    for track in tracks[:5]:  # First 5
        width = pcbnew.ToMM(track.GetWidth())
        print(f"  Net: {track.GetNetname()}, Width: {width:.3f}mm")

    # Get design rules
    rules = board.GetDesignSettings()
    print(f"\nDesign Rules:")
    print(f"  Min track width: {pcbnew.ToMM(rules.GetMinClearance()):.3f}mm")
    print(f"  Min via size: {pcbnew.ToMM(rules.GetViasMinSize()):.3f}mm")

    return True

if __name__ == '__main__':
    analyze_board('demo/blinker.kicad_pcb')
```

**Advantages**:
- Direct board object access
- Can implement custom DRC checks
- More powerful analysis

**Disadvantages**:
- Requires KiCad's Python (specific versions)
- Steep learning curve (no formal API docs)
- Limited to interactive use (can't be backgrounded easily)

---

## Part 3: Handling KiCad 5 vs 8 Footprint Format Issues

### The Problem

KiCad PCB file format changed between versions:

- **KiCad 5**: Uses `(module ...)` syntax in `.kicad_pcb` files
- **KiCad 8+**: Uses `(footprint ...)` syntax

When you load a KiCad 5 PCB with KiCad 8's `kicad-cli`, it may fail if the footprints are in KiCad 5 format.

### Symptom: "Failed to load board"

```bash
$ /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc board.kicad_pcb --format json
Failed to load board
```

No detailed error message. The board simply won't load.

### Root Causes

1. **JLC2KiCad_lib** — JLCPCB component footprints (often in KiCad 5 format)
2. **Custom footprints** created with older KiCad versions
3. **Third-party libraries** not updated for KiCad 8+
4. **Footprint library references** pointing to obsolete paths

### Diagnostic Steps

1. **Check if the board opens in KiCad GUI**:
   ```bash
   # macOS
   /Applications/KiCad/KiCad.app/Contents/MacOS/pcbnew board.kicad_pcb
   ```
   If the GUI opens the board fine but CLI fails → format conversion issue.

2. **Check PCB file header**:
   ```bash
   head -5 board.kicad_pcb
   # KiCad 8+ output:
   # (kicad_pcb (version 20240108) ...)
   # KiCad 5 output:
   # (kicad_pcb (version 20171130) ...)
   ```

3. **Check for old-style footprints**:
   ```bash
   grep -c "^[[:space:]]*(module " board.kicad_pcb
   # Non-zero = KiCad 5 footprints present
   ```

### Solution 1: Upgrade PCB File (Best)

Open the board in KiCad 8+ GUI and save it:

```bash
# macOS
/Applications/KiCad/KiCad.app/Contents/MacOS/pcbnew board.kicad_pcb
# File > Save (auto-upgrades format to KiCad 8+)
```

The GUI will automatically convert footprint format and update all references.

### Solution 2: Re-export Footprints from Libraries

If custom footprints are the issue:

1. In KiCad GUI, open **Preferences > Footprint Libraries Manager**
2. For each custom library, right-click > **Regenerate Library** (creates KiCad 8 format)
3. Re-export the board with new footprints

### Solution 3: Programmatic Conversion (Partial)

For automated conversion, create a migration script:

```python
#!/usr/bin/env python3
"""Convert KiCad PCB file from version 5 to 8 format."""

import re
from pathlib import Path

def migrate_pcb_v5_to_v8(input_file, output_file):
    """
    Basic migration: updates version number and (module -> (footprint.

    WARNING: This is a simplified conversion. Full KiCad 5->8 migration
    has many subtle changes. For production, use KiCad GUI migration.
    """
    content = Path(input_file).read_text()

    # Update version number (if KiCad 5)
    content = re.sub(r'\(version 20171130\)', '(version 20240108)', content)
    # KiCad 8 version numbers: 20240108 or later

    # This is NOT sufficient for full migration.
    # Use the KiCad GUI "Import Legacy Project" for reliable conversion.

    Path(output_file).write_text(content)
    print(f"Partial migration: {input_file} -> {output_file}")
    print("WARNING: Please verify with KiCad GUI and re-save to complete migration.")

migrate_pcb_v5_to_v8('board_old.kicad_pcb', 'board_new.kicad_pcb')
```

**Note**: Full migration requires KiCad's internal converters. Always verify with the GUI afterwards.

### Solution 4: Use Older kicad-cli Version (Not Recommended)

If you must work with KiCad 5 format, keep KiCad 5 installed:

```bash
# Use specific version
/Applications/KiCad5/KiCad.app/Contents/MacOS/kicad-cli pcb drc board.kicad_pcb --format json
```

But this defeats the purpose of upgrading. Best practice: migrate boards to KiCad 8+.

---

## Part 4: Custom & Non-Standard Footprints

### Common Issues

When running DRC with custom footprints:

```
Failed to load board
Missing footprint: C_Custom_0805
Footprint library not found: /path/to/custom.pretty
```

### Fix 1: Verify Footprint Library Paths

Check the PCB file for library definitions (usually at the end):

```bash
tail -20 board.kicad_pcb | grep -A10 "footprint_libs"
```

Should contain:

```lisp
(footprint_libs
  (version 20210606)
  (provider kicad)
  (lib (name "custom") (type KiCad) (uri "${KIPRJMOD}/footprints/custom.pretty") (options ""))
)
```

Key: Use `${KIPRJMOD}` for relative paths (portable).

### Fix 2: Organize Footprints in Project Directory

Standard structure:

```
my_project/
├── board.kicad_pcb
├── board.kicad_sch
├── footprints/
│   ├── custom.pretty/
│   │   ├── my_footprint.kicad_mod
│   │   ├── another_footprint.kicad_mod
│   └── JLC.pretty/
│       ├── C0805.kicad_mod
│       └── R0805.kicad_mod
└── fp-lib-table
```

Create `fp-lib-table` in project root:

```lisp
(fp_lib_table
  (version 7)
  (lib (name "custom") (type KiCad) (uri "${KIPRJMOD}/footprints/custom.pretty") (options "") (descr "Custom footprints"))
  (lib (name "JLC") (type KiCad) (uri "${KIPRJMOD}/footprints/JLC.pretty") (options "") (descr "JLCPCB components"))
)
```

### Fix 3: Use Project Variables in DRC Command

If footprints use variable paths:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc board.kicad_pcb \
  --format json \
  -D KIPRJMOD="$(pwd)" \
  -D CUSTOM_FOOTPRINT_PATH="/path/to/custom.pretty"
```

### Fix 4: Substitute Missing Footprints (Temporary Testing)

For testing DRC without complete footprint libraries:

```python
#!/usr/bin/env python3
"""Temporarily replace missing footprints with placeholder."""

import re
from pathlib import Path

def substitute_missing_footprints(pcb_file, output_file):
    """Replace unknown footprints with a generic placeholder."""
    content = Path(pcb_file).read_text()

    # Find all unique footprint names
    fp_pattern = r'\(footprint "([^"]+)"'
    footprints = set(re.findall(fp_pattern, content))

    # Known good footprints (whitelist)
    known_footprints = {'C0805', 'R0805', 'SOIC-8', 'QFP-100'}

    # Replace unknown ones
    for fp_name in footprints:
        if fp_name not in known_footprints and not fp_name.startswith('Placeholder'):
            # Replace with generic placeholder
            content = re.sub(
                rf'\(footprint "{re.escape(fp_name)}"',
                f'(footprint "Placeholder"',
                content
            )
            print(f"Substituted: {fp_name} -> Placeholder")

    Path(output_file).write_text(content)
    print(f"Output: {output_file}")

substitute_missing_footprints('board.kicad_pcb', 'board_substituted.kicad_pcb')
```

### Fix 5: Embed Footprints in PCB (Portable)

Make the PCB self-contained with embedded footprints:

```bash
# In KiCad 8+ GUI:
# File > Save with footprints embedded (or equivalent menu item)

# Or via CLI (if supported):
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export board.kicad_pcb \
  --footprints-embedded
```

This creates a standalone `.kicad_pcb` file with all footprints inline.

---

## Part 5: Complete Wrapper Class

Production-ready Python class for DRC operations:

```python
#!/usr/bin/env python3
"""KiCad DRC wrapper for production use."""

import json
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

class DrcSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    EXCLUSION = "exclusion"

@dataclass
class DrcViolationItem:
    """Single violation instance."""
    uuid: str
    reference: str
    pos_x: float
    pos_y: float
    layer: Optional[str] = None

@dataclass
class DrcViolation:
    """Grouped DRC violation."""
    violation_type: str
    severity: DrcSeverity
    description: str
    items: List[DrcViolationItem]

class KicadDrcRunner:
    """Runs KiCad DRC and parses results."""

    DEFAULT_KICAD_CLI_PATHS = [
        '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',  # macOS
        '/usr/bin/kicad-cli',  # Linux
        'C:\\Program Files\\KiCad\\kicad-cli.exe',  # Windows
    ]

    def __init__(self, kicad_cli_path: Optional[str] = None):
        """Initialize with kicad-cli path."""
        if kicad_cli_path:
            self.kicad_cli = Path(kicad_cli_path)
        else:
            # Try to find kicad-cli
            self.kicad_cli = self._find_kicad_cli()

        if not self.kicad_cli or not self.kicad_cli.exists():
            raise FileNotFoundError(f"kicad-cli not found at {self.kicad_cli}")

    def _find_kicad_cli(self) -> Optional[Path]:
        """Search for kicad-cli in standard locations."""
        for path in self.DEFAULT_KICAD_CLI_PATHS:
            p = Path(path)
            if p.exists():
                return p
        return None

    def run(self, pcb_file: str, severity: str = 'all',
            units: str = 'mm', all_errors: bool = False,
            schematic_parity: bool = False) -> dict:
        """
        Run DRC and return raw JSON output.

        Args:
            pcb_file: Path to .kicad_pcb file
            severity: 'all', 'error', 'warning', or 'exclusions'
            units: 'mm', 'in', or 'mils'
            all_errors: Report all errors per segment
            schematic_parity: Check PCB/schematic parity

        Returns:
            Raw parsed JSON dict from kicad-cli
        """
        cmd = [str(self.kicad_cli), 'pcb', 'drc', str(pcb_file),
               '--format', 'json', f'--severity-{severity}', '--units', units]

        if all_errors:
            cmd.append('--all-track-errors')
        if schematic_parity:
            cmd.append('--schematic-parity')

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode not in [0, 1]:  # 1 = violations found (still valid)
            raise RuntimeError(f"DRC failed with code {result.returncode}: {result.stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse DRC JSON: {e}")

    def get_violations(self, pcb_file: str) -> List[DrcViolation]:
        """Get violations as structured objects."""
        raw = self.run(pcb_file)
        violations = []

        for viol_data in raw.get('violations', []):
            items = [
                DrcViolationItem(
                    uuid=item.get('uuid', ''),
                    reference=item.get('reference', ''),
                    pos_x=item.get('pos_x', 0),
                    pos_y=item.get('pos_y', 0),
                    layer=item.get('layer')
                )
                for item in viol_data.get('items', [])
            ]

            violations.append(DrcViolation(
                violation_type=viol_data.get('type', 'unknown'),
                severity=DrcSeverity(viol_data.get('severity', 'warning')),
                description=viol_data.get('description', ''),
                items=items
            ))

        return violations

    def error_count(self, pcb_file: str) -> int:
        """Count errors."""
        violations = self.get_violations(pcb_file)
        return sum(1 for v in violations if v.severity == DrcSeverity.ERROR)

    def warning_count(self, pcb_file: str) -> int:
        """Count warnings."""
        violations = self.get_violations(pcb_file)
        return sum(1 for v in violations if v.severity == DrcSeverity.WARNING)

    def summary(self, pcb_file: str) -> dict:
        """Get summary statistics."""
        violations = self.get_violations(pcb_file)

        by_type = {}
        for v in violations:
            if v.violation_type not in by_type:
                by_type[v.violation_type] = {'error': 0, 'warning': 0, 'exclusion': 0}
            by_type[v.violation_type][v.severity.value] += 1

        return {
            'total_violations': len(violations),
            'error_count': self.error_count(pcb_file),
            'warning_count': self.warning_count(pcb_file),
            'by_type': by_type
        }

# Usage
if __name__ == '__main__':
    try:
        drc = KicadDrcRunner()
        violations = drc.get_violations('demo/blinker.kicad_pcb')

        print(f"Total violations: {len(violations)}")
        for v in violations:
            print(f"  [{v.severity.value.upper()}] {v.violation_type}: {v.description}")
            if v.items:
                item = v.items[0]
                print(f"    @ ({item.pos_x}, {item.pos_y}) {item.layer}")

        summary = drc.summary('demo/blinker.kicad_pcb')
        print(f"\nSummary: {summary['error_count']} errors, {summary['warning_count']} warnings")

        sys.exit(0 if summary['error_count'] == 0 else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

---

## Part 6: CI/CD Integration

### Bash Script

```bash
#!/bin/bash
# ci_drc_check.sh — Run DRC as part of CI/CD pipeline

set -euo pipefail

BOARD_FILE="${1:?Usage: $0 <board.kicad_pcb>}"
KICAD_CLI="/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
OUTPUT_JSON="${BOARD_FILE%.kicad_pcb}_drc_report.json"

echo "Running DRC on $BOARD_FILE..."

# Run DRC
"$KICAD_CLI" pcb drc "$BOARD_FILE" \
  --format json \
  --severity-all \
  --units mm \
  --output "$OUTPUT_JSON" \
  --exit-code-violations || DRC_EXIT=$?

DRC_EXIT=${DRC_EXIT:-0}

echo "DRC report saved to $OUTPUT_JSON"

# Parse results
if command -v jq &>/dev/null; then
    ERRORS=$(jq '.violations | map(select(.severity == "error")) | length' "$OUTPUT_JSON")
    WARNINGS=$(jq '.violations | map(select(.severity == "warning")) | length' "$OUTPUT_JSON")

    echo "Results: $ERRORS errors, $WARNINGS warnings"

    if [ "$ERRORS" -gt 0 ]; then
        echo "DRC FAILED - Errors found:"
        jq '.violations[] | select(.severity == "error") | {type, description}' "$OUTPUT_JSON"
        exit 1
    fi

    if [ "$WARNINGS" -gt 0 ]; then
        echo "DRC warnings (non-blocking):"
        jq '.violations[] | select(.severity == "warning") | .type' "$OUTPUT_JSON"
    fi
else
    echo "jq not found; skipping result parsing"
fi

exit 0
```

### GitHub Actions Workflow

```yaml
name: KiCad DRC Check

on:
  push:
    paths:
      - '**.kicad_pcb'
      - '**.kicad_sch'
  pull_request:

jobs:
  drc:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install KiCad
        run: brew install kicad

      - name: Run DRC
        run: |
          kicad-cli pcb drc demo/blinker.kicad_pcb \
            --format json \
            --severity-all \
            --output drc_report.json

      - name: Parse DRC Report
        run: |
          python3 << 'EOF'
          import json
          with open('drc_report.json') as f:
              data = json.load(f)
          errors = len([v for v in data['violations'] if v['severity'] == 'error'])
          if errors > 0:
              print(f"::error::DRC found {errors} errors")
              exit(1)
          EOF

      - name: Upload DRC Report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: drc_report
          path: drc_report.json
```

---

## Troubleshooting Summary

| Problem | Symptom | Solution |
|---------|---------|----------|
| Board won't load | "Failed to load board" | Upgrade PCB to KiCad 8 format (open in GUI, save) |
| Missing footprints | "Footprint library not found" | Use `${KIPRJMOD}` in library paths, organize locally |
| Library path not found | DRC fails, no board load | Verify `fp-lib-table`, run from correct directory |
| Wrong KiCad version | CLI doesn't exist | Install correct KiCad version |
| Python module not found | Import pcbnew fails | Use `/Applications/KiCad/.../python3`, add to PATH |
| JSON parsing errors | Invalid JSON output | Upgrade kicad-cli, check stderr for load failures |
| Exit code confusion | Can't tell pass/fail | Use `--exit-code-violations` flag (returns 0 or 1) |

---

## References

- **KiCad CLI Documentation**: https://docs.kicad.org (search "kicad-cli pcb drc")
- **KiCad GitHub Source**: https://github.com/KiCad/kicad-source-mirror
- **KiCad Python Scripting**: Built-in, minimal external docs (check doxygen)
- **KiCad File Format**: `.kicad_pcb` is S-expression based, parseable with regex or s-exp libraries

---

## Files in This Repository

- `/demo/drc_rules.py` — Standalone DRC engine (alternative, 27 checks)
- `/demo/layout.py` — BoardLayout class with DRC integration points
- `/demo/blinker.py` — Example pipeline including DRC validation

---

## Notes for kicad-claude Project

This guide is specific to the `kicad-claude` project's use case: programmatic PCB design and validation without the KiCad GUI. Key takeaways:

1. **Always use `kicad-cli pcb drc --format json`** for integration with Python pipelines
2. **Subprocess wrapper is more reliable** than direct `pcbnew` API for production
3. **Footprint libraries must be project-relative** (`${KIPRJMOD}`) for portability
4. **Pre-migrate any KiCad 5 boards** to KiCad 8+ before automated DRC runs
5. **Use `--exit-code-violations`** in CI/CD pipelines for pass/fail detection
6. **Parse JSON output with Python/jq** to extract specific violation types

For the `/demo/drc_rules.py` pipeline, this guide enables automated validation before manufacturing.
