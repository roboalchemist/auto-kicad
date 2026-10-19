#!/usr/bin/env bash
# Render a colored PCB image from render_data.json.
#
# Usage: ./scripts/render.sh [render_data.json] [output.png]
#
# Auto-detects KiCad Python and runs render_pcb.py which handles
# SVG export (pcbnew) + colorization (cairosvg + Pillow via system Python).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$(dirname "$SCRIPT_DIR")"

JSON_FILE="${1:-${DEMO_DIR}/render_data.json}"
OUTPUT="${2:-${DEMO_DIR}/blinker_render.png}"

# Auto-detect KiCad Python
KICAD_PYTHON=""
for candidate in \
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3" \
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3" \
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.8/bin/python3" \
    ; do
    if [ -x "$candidate" ]; then
        KICAD_PYTHON="$candidate"
        break
    fi
done

if [ -z "$KICAD_PYTHON" ]; then
    echo "Error: Could not find KiCad Python. Install KiCad or set KICAD_PYTHON." >&2
    exit 1
fi

if [ ! -f "$JSON_FILE" ]; then
    echo "Error: $JSON_FILE not found. Run do_layout.py first." >&2
    exit 1
fi

"$KICAD_PYTHON" "$SCRIPT_DIR/render_pcb.py" "$JSON_FILE" -o "$OUTPUT"
