## What changed

## Why

## Verification
- [ ] `cd harness && .venv/bin/pytest tests -q`
- [ ] `npm --prefix harness/web run build`
- [ ] Board changes: both DRC engines clean (`kicad-cli pcb drc`, `demo/drc_rules.py`)
- [ ] UI changes: ran the relevant `harness/web/e2e/` walkthrough and checked the console

## Notes for reviewers
