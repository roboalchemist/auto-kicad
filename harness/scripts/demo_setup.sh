#!/usr/bin/env bash
# Create (or recreate) a demo design: the blinker board with the "LED on the left" goal and one
# must-fix review comment, so headless and browser end-to-end runs start from the same state.
#   harness/scripts/demo_setup.sh [design-name] [goal-file]
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${1:-blinker-demo}"
GOAL="${2:-$HERE/examples/goal-led-left.json}"
K="$HERE/.venv/bin/kicad-harness"
HOME_DIR="${HARNESS_HOME:-$HERE/var}"

if [ -d "$HOME_DIR/workspaces/$NAME" ]; then
  echo "Removing existing demo design $NAME"
  rm -rf "$HOME_DIR/workspaces/$NAME"
  "$HERE/.venv/bin/python" - "$NAME" <<'PY'
import sys
from kicad_harness import config
from kicad_harness.store.db import Store
name = sys.argv[1]
store = Store(config.get())
with store.tx() as conn:
    for table in ("threads", "runs", "version_meta", "agent_history", "steering"):
        conn.execute(f"DELETE FROM {table} WHERE design = ?", (name,))
PY
fi

"$K" init "$NAME" --from "$HERE/tests/fixtures/blinker.kicad_pcb" --goal "$GOAL"
"$K" comment "$NAME" --ref D1 --severity must_fix --tag placement \
  --body "The LED has to be visible from the left side of the enclosure - move it to the left edge."
"$K" goal "$NAME"
