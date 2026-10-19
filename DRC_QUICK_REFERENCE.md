# KiCad DRC Quick Reference Card

## CLI One-Liners

### Basic JSON DRC (all violations)
```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc board.kicad_pcb --format json --severity-all
```

### Report format (human-readable)
```bash
kicad-cli pcb drc board.kicad_pcb --format report
```

### Exit code on violations (for CI/CD)
```bash
kicad-cli pcb drc board.kicad_pcb --severity-all --exit-code-violations; echo "Exit: $?"
```

### Errors only, all details
```bash
kicad-cli pcb drc board.kicad_pcb --format json --severity-error --all-track-errors
```

### With custom units
```bash
kicad-cli pcb drc board.kicad_pcb --format json --units mils --output report.json
```

---

## Python Usage

### Simple wrapper (subprocess)
```python
import subprocess, json
result = subprocess.run([
    'kicad-cli', 'pcb', 'drc', 'board.kicad_pcb',
    '--format', 'json', '--severity-all'
], capture_output=True, text=True)
data = json.loads(result.stdout)
print(f"Violations: {len(data['violations'])}")
```

### Using drc_runner.py (this project)
```python
from demo.drc_runner import KicadDrcRunner, DrcSeverity

runner = KicadDrcRunner()
violations = runner.get_violations('board.kicad_pcb')
print(f"Errors: {runner.error_count('board.kicad_pcb')}")
print(f"Warnings: {runner.warning_count('board.kicad_pcb')}")

# Filter by severity
errors = runner.violations_by_severity('board.kicad_pcb', DrcSeverity.ERROR)
```

### JSON output parsing
```python
import json
data = json.load(open('drc_report.json'))
for violation in data['violations']:
    print(f"{violation['type']}: {violation['description']}")
    for item in violation['items']:
        print(f"  @ ({item['pos_x']}, {item['pos_y']}) on {item['layer']}")
```

---

## Common Violation Types

| Type | Cause | Fix |
|------|-------|-----|
| `clearance` | Traces too close | Increase trace spacing |
| `track_width` | Trace too narrow | Increase trace width |
| `annular_ring` | Via ring too small | Use larger via pad |
| `via_hole_clearance` | Via too close to trace | Move trace or via |
| `copper_to_edge` | Copper near board edge | Reduce copper area near edge |
| `missing_footprint` | Library not found | Add project footprint library |
| `unconnected_items` | Dangling nets | Connect all pads |
| `silkscreen_overlap` | Text/graphics on pads | Move silkscreen away |

---

## Troubleshooting

### "Failed to load board"
**Cause**: KiCad 5 format or missing footprints
**Fix**: Open in KiCad GUI and save (auto-converts to KiCad 8 format)

### "Footprint library not found"
**Cause**: Library path is absolute instead of relative
**Fix**: Use `${KIPRJMOD}` in `fp-lib-table` paths

### "kicad-cli: command not found"
**Cause**: KiCad not installed or not in PATH
**Fix**: Use full path or ensure KiCad 8+ is installed

### JSON parse errors
**Cause**: Board load failed, kicad-cli printed error instead of JSON
**Fix**: Run `kicad-cli pcb drc board.kicad_pcb` without `--format json` to see error

---

## File Locations (macOS)

| Item | Path |
|------|------|
| CLI tool | `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` |
| Python | `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3` |
| pcbnew module | Included with KiCad Python (use kicad python, not system python) |

---

## Environment Setup

```bash
# macOS: Add KiCad tools to PATH
export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"

# Then use shortened commands
kicad-cli pcb drc board.kicad_pcb --format json
```

---

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run DRC
  run: kicad-cli pcb drc board.kicad_pcb --format json --exit-code-violations
```

### GitLab CI
```yaml
drc:
  script:
    - kicad-cli pcb drc board.kicad_pcb --format json --output report.json
  artifacts:
    paths:
      - report.json
```

### Generic Bash
```bash
#!/bin/bash
kicad-cli pcb drc board.kicad_pcb --format json --severity-all > drc.json
python3 -c "import json; data=json.load(open('drc.json')); exit(0 if data['violations']==[] else 1)"
```

---

## JSON Output Structure

```json
{
  "violations": [
    {
      "type": "clearance",
      "severity": "error",
      "description": "Track to track clearance",
      "items": [
        {
          "uuid": "xxx-xxx-xxx",
          "reference": "GND",
          "pos_x": 10.5,
          "pos_y": 20.3,
          "layer": "F.Cu"
        }
      ]
    }
  ]
}
```

---

## Useful jq Filters

```bash
# Count violations by type
jq '.violations | group_by(.type) | map({type: .[0].type, count: length})' drc.json

# Extract only errors
jq '.violations[] | select(.severity == "error")' drc.json

# Get positions of all violations
jq '.violations[].items[] | {pos_x, pos_y, layer}' drc.json

# Check if any errors
jq 'if (.violations | map(select(.severity == "error")) | length) > 0 then "FAIL" else "PASS" end' drc.json
```

---

## Resources in This Repository

- `KICAD_DRC_GUIDE.md` — Comprehensive guide (4000+ lines)
- `demo/drc_runner.py` — Production Python wrapper (ready to use)
- `demo/drc_rules.py` — Custom DRC engine (27 checks)

---

## Version Info

- **KiCad Versions Tested**: 8.x, 9.0.4
- **Platforms**: macOS, Linux, Windows (CLI available on all)
- **Python**: 3.7+ (use KiCad's Python for pcbnew module)
- **Dependencies**: None (subprocess + json are stdlib)
