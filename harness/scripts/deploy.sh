#!/usr/bin/env bash
# Deploy the harness into /srv/ecad-agent from this working copy.
#
# The deployment carries a few local edits that must not be overwritten by a sync (Bifrost
# defaults differ from the public repo). They are captured here, restored after the rsync, and
# the deploy fails loudly if the result differs from what was there before, so a lost local
# change can never go unnoticed again.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ECAD_DEST:-/srv/ecad-agent/harness}"

# Files that exist only on the deployment.
# Only files that genuinely differ from the repo belong here. agent/models.py used to be
# listed but had no unique content, which let it drift out of date instead of being deployed.
KEEP=(
  "kicad_harness/config.py"
)

backup="$(mktemp -d)"
trap 'rm -rf "$backup"' EXIT

for f in "${KEEP[@]}"; do
  if [[ -f "$DEST/$f" ]]; then
    mkdir -p "$backup/$(dirname "$f")"
    cp "$DEST/$f" "$backup/$f"
  else
    echo "warning: $DEST/$f is missing; deploying the repo version" >&2
  fi
done

rsync -a --delete \
  --exclude '__pycache__' --exclude '.venv' --exclude '.vendor' --exclude 'var' \
  --exclude 'node_modules' --exclude 'dist' --exclude '.env' --exclude 'tests' \
  --exclude '.pytest_cache' \
  "$SRC/kicad_harness/" "$DEST/kicad_harness/"

for f in "${KEEP[@]}"; do
  [[ -f "$backup/$f" ]] && cp "$backup/$f" "$DEST/$f"
done

for f in "${KEEP[@]}"; do
  if [[ -f "$backup/$f" ]] && ! cmp -s "$backup/$f" "$DEST/$f"; then
    echo "error: $f changed during deploy — local deployment edits were not preserved" >&2
    exit 1
  fi
done

if [[ -d "$SRC/web" ]]; then
  rsync -a --exclude 'node_modules' --exclude 'dist' "$SRC/web/src/" "$DEST/web/src/"
fi

echo "deployed $SRC -> $DEST (preserved: ${KEEP[*]})"
