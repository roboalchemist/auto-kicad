# Worklog

## 2026-03-15 — PCB redesign, DRC engine, design review framework

### What was done
- Redesigned 555 timer LED blinker PCB layout following all `.agents/rules/pcb-*.md` rules
- Board went from 30x24mm (720mm²) to 21x18mm (378mm²), 71.7% compactness
- Fixed silkscreen: removed body outlines from footprints, moved ref des text beside components, fixed text sizes to JLCPCB minimums (1.0mm height, 0.15mm thickness)
- Fixed pad overlaps and via-to-pad clearance violations (verified via pcbnew API)
- Fixed `layout.py` to generate KiCad 8 format (`footprint` not `module`), add UUIDs, strip duplicate board outlines

### DRC engine (`drc_rules.py`)
- Built Python DRC engine matching JLCPCB `.kicad_dru` rules from https://github.com/labtroll/KiCad-DesignRules
- Uses pcbnew API for accurate pad/silkscreen bounding box geometry
- 27 automated checks across 8 rule files, each violation citing the source rule file and section
- Checks: pad/via clearance, track width, hole sizes, annular ring, track crossings, silkscreen (text size, pad clearance, text overlap), 90-degree bends, tombstoning risk, return via proximity, bypass cap presence/distance, copper balance, fiducials, test points, power connector, mounting holes, corner radii, board edge clearance
- Integrated into `do_layout_v2.py` pipeline (runs as KiCad Python subprocess)

### Design review framework
- Ran 8-agent parallel review (`/pcb-review` pattern) covering placement, routing, power, DFM, EMC, thermal, test/debug, mechanical
- Created `/pcb-review` slash command (`.agents/commands/pcb-review.md`)
- Added `reference/review.md` to pcb-design skill with agent prompt template and 12-domain checklist
- Most review findings now caught automatically by `drc_rules.py`

### Key challenges
- kicad-cli DRC cannot load boards with JLC2KiCad_lib footprints (KiCad 5 `module` format, even after pcbnew round-trip). Workaround: use pcbnew Python API directly for pad geometry, custom DRC in Python.
- KiCad Python (3.9) doesn't support `str | None` union syntax — must run layout scripts with system Python, DRC with KiCad Python as subprocess
- SOIC-8 pin routing is inherently tight at 1.27mm pitch — 3W rule violations unavoidable at IC pin exits
- Silkscreen ref des positioning requires per-footprint tuning to avoid pad overlap while staying within board edge

### What's left (from DRC report: 3 errors, 24 warnings)
- **Errors**: D1 pad edge clearance (1.3mm), missing VCC bypass cap on U1 pins 4/8
- **Warnings**: 90-degree bends (9), tombstoning risk (4), return via proximity (2), bypass cap distance (2), copper balance (2), missing fiducials/test points/connector/mounting holes/corner radii (5)

## 2026-03-15 — DRC fix iteration, 12-domain review, C3 bypass cap

### 12-domain parallel review
- Ran full `/pcb-review` with 12 parallel sub-agents across all rule domains
- Domains: Placement, Routing, Power, DFM, EMC, Thermal, Silkscreen, Test/Debug, Mechanical, Copper Pours, BOM/Components, Stackup
- Results: Thermal, Copper Pours, Stackup, BOM, EMC all PASS. Critical issues in Placement (C2 distance), Power (missing bypass cap), Routing (90° bends, crossings), Test/Debug (edge clearance)

### Fixes applied
- **Added C3 (100nF VCC bypass cap)** near U1 pin 8 — switched from `BoardLayout.__init__()` to `BoardLayout.new_board()` to add components not in original netlist. Fixed `new_board()` to parse pad info from footprints.
- **Board expanded** from 21x18mm (378mm²) to 25x20mm (500mm²) — needed for C3 placement + edge clearance
- **Relocated C2** from (17, 7) to (13.5, 5) — within 3mm of U1 pin 5 (was 9.6mm)
- **Eliminated F.Cu crossings** — OUTPUT routed 45° below U1 pin row to avoid VCC U1.4 stub; VCC U1.8 routed to C3 via B.Cu instead of F.Cu
- **Added GND return vias** adjacent to THRESHOLD signal vias (within 1mm)
- **Added board ID text** "555-BLINKER v2" on silkscreen
- **Moved C3 ref text** LEFT in post-processing to avoid U1 pad overlap

### Key challenges
- **VCC/GND B.Cu crossing unavoidable on 2-layer** — VCC bus (left side) and GND bus (right side) must cross to reach U1.4 (bottom-right). Would be resolved by ground pour or 4-layer stackup.
- **C3 placement vs silkscreen** — C0805 ref text at (+3, 0) relative to component always points toward U1 when C3 is to the left. Per-component ref text positioning requires post-processing regex.
- **Via-pad clearance cascade** — moving components to fix one clearance creates new clearances with vias from adjacent components. Iterative process of adjusting via stub directions.
- **new_board() missing pad data** — BoardLayout.new_board() didn't parse pad info from .kicad_mod files, causing `get_pad_position()` to fail. Added pad regex parsing in layout.py.

### Current DRC (3 errors, 13 warnings)
- **Errors**: B.Cu VCC/GND crossing (inherent 2-layer), C3 silkscreen near U1 pads (shared footprint limitation)
- **Warnings**: Tombstoning risk (4), decoupling cap distance from U1.4 (9.7mm), THRESHOLD bypass distance, copper balance (2), missing production features (fiducials, test points, connector, corner radii, mounting holes)

### Improvements from previous iteration
| Metric | Before | After |
|--------|--------|-------|
| DRC errors | 3 | 3 (different: B.Cu inherent + silkscreen vs pad overlap + missing cap) |
| DRC warnings | 24 | 13 |
| VCC bypass cap | Missing | C3 added within 3mm of U1.8 |
| C2 distance to pin 5 | 9.6mm | 2.9mm |
| F.Cu crossings | 3 | 0 |
| 90° bends | 9 | 0 on F.Cu (B.Cu inherent from 45° routing) |
| Board size | 21x18mm | 25x20mm |
| Components | 7 | 8 (added C3) |
| Return vias | 2 (far) | 2 (adjacent, <1mm) |

## 2026-10-16 — Honest DRC, re-routed demo board, BoardLayout generalized

### What was found
- The repo was renamed from `kicad-claude`, but `demo/render_data*.json` still had an absolute `footprint_dir` under the old path. `drc_rules.py` then loaded zero pads and reported **0 errors, exit 0**; with the path fixed it reported 8 errors. `render.sh` drew boards without pads, also silently.
- The editable JLC2KiCadLib install pointed at the old path too, so `blinker.py` couldn't import it.
- kicad-cli DRC (KiCad 10.0.3) *does* work on the demo board, and it found **real shorts at U1**: THRESHOLD crossing pads 3 and 5, OUTPUT crossing pad 4. It also flagged two GND "return vias" connected on B.Cu only, and C3's reference text on U1's pads.
- `drc_rules.py` missed those shorts. Its track-to-pad check read pad sizes from keys that didn't exist, so every pad was a 1mm circle, and it ignored layers, so B.Cu tracks under F.Cu pads showed up as false shorts.
- `layout.py` hard-coded the blinker's 7 net names (any other net silently became net 0). It wrote pad angles unrotated for rotated footprints: KiCad stores pad/text angles in board orientation, so D1's pads were wrong. It also couldn't load boards whose footprints use `(property "Reference" ...)`, which is every board `blinker.py` now produces.
- `research/huaqiu-kicad-mcp-server` was a gitlink with no `.gitmodules` entry, so `git submodule update --init` died partway.

### What was done
- `.gitmodules` entry added; reinstalled JLC2KiCadLib editable from `research/libs/JLC2KiCad_lib`; `blinker.py` runs again (netlist unchanged apart from skidl's random tags).
- `render_data` now stores `footprint_dir` relative to the JSON file. `drc_rules.py` exits 2 when it can't load pcbnew or a footprint (no more 0805 guesses), and `render_pcb.py` refuses to draw a board with missing footprints.
- `drc_rules.py` track-to-pad clearance now uses each pad's rotated bounding box and copper layers.
- `layout.py`: dynamic nets; rotation-aware pad/text angles; KiCad 5–10 board loading (incl. KiCad 10's name-only `(net "X")` format, from board version 20251028); append-only saves for boards it didn't generate; outline replacement no longer corrupts multi-line `gr_rect`; pad nets injected into KiCad 5 one-line pads.
- `do_layout_v2.py` re-routed: C3 moved between pins 8 and 1, R2 and C1 rotated 180°, everything on F.Cu except one B.Cu VCC link (15 vias → 2). The dead silkscreen post-processing (it targeted `fp_text`, which the KiCad 9 footprints don't use) is gone; placement keeps reference text clear instead. The script exits 1 when either DRC engine reports an error or can't run.

### Key challenges
- drc_rules.py only knows default reference-text positions (render_data has no text data), so silkscreen fixes have to come from placement/rotation, not post-processing the .kicad_pcb.
- Inside a placed footprint, KiCad keeps pad/text x/y in the footprint's frame but angles in board orientation. Verified by saving a rotated footprint with pcbnew and reading the file.
- When kicad-cli loads a dangling track, it renames the track's net to the net of the pad it touches. A "wrong net" in pcbnew can be a geometry mistake, not a writer bug.

### Current DRC (kicad-cli 0E/0W, drc_rules.py 0E/13W)
- **Warnings**: tombstoning risk (4), U1.4 6.9mm from nearest VCC cap, timing cap C1 9.1mm from U1.6, copper balance (2), missing fiducials / test points / power connector / corner radii / mounting holes

| Metric | Before | After |
|--------|--------|-------|
| kicad-cli errors | 7 (3 shorts) | 0 |
| drc_rules.py errors | 8 (6 false, real shorts missed) | 0 |
| Vias | 15 | 2 |
| Track length | — | 106.7mm (77% directness) |
| C3 pad to U1 pin (VCC 8 / GND 1) | 4.1mm / 5.5mm | 2.6mm / 2.6mm |

## 2026-10-16 — Framework research for the agent harness

### What was done
- Researched the stack for an agent harness with a visible loop, click-to-comment, and versioned designs. The result is in `research/agent-harness-2026.md`: Pydantic AI → AG-UI → CopilotKit; KiCad SVG plus pick overlay; git versions; anchored comments.
- Ran two spikes against `claude-haiku-5-5` and KiCad 10.0.3. The code and recorded streams are in `research/spikes/2026-10-16/`.

### Key challenges
- "agent-kit" was ambiguous: OpenAI AgentKit, Inngest AgentKit, Coinbase AgentKit. The library the user meant was **CopilotKit**.
- CopilotKit only supports connecting the browser straight to your own AG-UI backend in production (`selfManagedAgents`) on the Enterprise tier. The free path is its MIT Node `CopilotRuntime` in front of the Python service.
- Pydantic AI 2.57 pins `ag-ui-protocol<1`, while `ag-ui-langgraph` and CopilotKit 1.79 use AG-UI 1.0. They need separate venvs, and the browser path is still unverified.
- KiCanvas parses KiCad 10's name-only `(net "X")` as no net, and its selection event isn't exposed to the host page. Overlaying our own hit shapes on `kicad-cli` SVG gives exact picks with UUIDs instead.
- `kicad-cli pcb render` camera:
  - px/mm = zoom × height / (1.0355 × max board dimension).
  - `--pivot` is in cm from the board centre, +Y up.
  - Avoid `--pan`.
- Generated demo boards share pad UUIDs across instances of the same footprint (C1/C2/C3, R1/R2/R3), which makes DRC name the wrong part. Any anchor scheme needs per-instance UUIDs.
- zsh expands `?` in an unquoted URL. Quote URLs in curl commands, e.g. `curl "https://api.anthropic.com/v1/models?limit=30"`.

## 2026-10-16 — Harness build: engine, store, agent, headless e2e (branch `harness-v1`)

### What was done
- Built and merged `harness-store` (98d5dbf), `harness-engine` (bd774b4 → edf6d69) and the web scaffold (`harness-web`, 00ace65 → 02f3a49) into `harness-v1`. Store: git-versioned workspace with trailer commits, review threads with entity anchors + carry-forward, run/AG-UI event log, steering messages. Engine: pcbnew worker (KiCad Python 3.9) over JSON-lines RPC, kicad-cli wrappers, 2D crop renders with highlight/labels/pins, 3D renders framed in mm, Shapely measurements, Freerouting 2.5.0 via vendored Java 25, content-hash artifact cache.
- Agent with 26 tools (placement, routing, outline, zones, pad nets, silkscreen, DRC/goal checks, render_view with model-visible images), supervised approvals, mid-run steering via a side-channel table + `before_model_request` hook, goal-loop output validator. Server: 33 routes (/agui + REST + SSE). CLI: 9 commands.
- Full backend suite on merged `harness-v1`: **170 tests pass** (33s), including the agent/server tests that were blocked until the engine landed.
- **Headless e2e with the real model**: `kicad-harness run blinker-demo` (claude-sonnet-5 via OpenRouter) exited 0 with `goal_met: true` — DRC 0E/0W, 0 unconnected, D1 in the left-edge region, R3 1.19 mm from D1, board 25×25 mm, must-fix thread addressed. 17 git versions (outline → moves → rip-up → Freerouting autoroute → silkscreen fixes), each with a descriptive trailer.

### Key challenges
- Engine render specs are per-mode and strictly validated (2D: side/center/view_mm/px_per_mm/width_px/highlight/labels/pins; 3D: side/center/view_mm/rotate/quality/width/height). The agent initially sent a combined spec; also `kicad-cli` 3D "front" is an edge-on view, so the agent defaults 3D to "top" (7c85785).
- The Anthropic key used early in development was stale (401 direct from api.anthropic.com). Working route: an OpenAI-compatible provider against OpenRouter (`HARNESS_MODEL=openai:anthropic/claude-sonnet-5` with `OPENAI_BASE_URL`); it needs the `openai` package on top of pydantic-ai-slim (extra declared, 4191128). Gemini was verified as a fallback.
- Tool-server restarts killed long-running subagent sessions twice; committing early and often kept the losses small (engine work was recovered from its worktree uncommitted, then committed and merged).

## 2026-10-16 (later) — Harness web UI merged, B1 fixed, browser e2e verified

### What was done
- Merged `harness-web` (12 commits, e333bb8 → 81414d1): the full CopilotKit UI. Board viewer (KiCad SVG + pick-index overlay, hover tooltip, zoom/pan, front/back, 3D tab, diff overlay), Review tab (Fictiv-style composer: entity pick → tags, severity, free tag → thread; pins on the board; thread cards with anchor + status actions), Versions tab (view / compare / restore / branch), Agent tab (CopilotChat + Run goal + steering + supervised approvals + tool cards), Activity tab (run replay), Goal tab (criteria + JSON editor).
- **Fixed the one real backend blocker (B1)**: every web-UI run died ~2 ms in with `RUN_ERROR: Cannot set a custom run output_type when the agent has output validators`. Cause: pydantic-ai 2.57's AG-UI adapter composes `[agent.output_type, DeferredToolRequests]` at run level whenever frontend tools are present, and validator-agents reject any run-level output_type. Our agent already has `[str, DeferredToolRequests]`, so the composition is redundant. Fix: `kicad_harness/agui_compat.py`, a version-guarded (2.57.x-only) patch of `Agent._prepare_output_schema` that keeps the agent's own schema for validator-agents, imported by `server.py`. Regression tests in `tests/test_agui_compat.py`. The subagent's `web/e2e/serve_patched.py` runtime shim is no longer needed for verification.
- **Fixed a real UX race**: the viewer mode buttons called `import("./store.ts").then(st => st.setMode(m))`. Because that module load is async, clicking Comment and then a pad quickly made `handlePick` see the stale `select` mode, silently dropping the comment anchor (the "composer never appears" flake). Static import now.
- Full suite after the merge and fixes: **172 tests pass** (33.9 s).
- **Browser e2e with a real model** (chromium, Playwright, `web/e2e/agent.mjs` then `web/e2e/walk.mjs`):
  - Agent: streamed chat; tool cards for focus_view/highlight/design_summary/check/query/render_view and edits with version links; an autonomous goal run made ~30 tool calls over 33 versions and reached **all 6 criteria** (drc 0, routed 0, D1 in the left region, R3 1.31 mm from D1, board 30×20, no open threads); mid-run steering was queued and delivered; the supervised approval card paused on `set_board_outline` and resumed on Approve; compare/diff rendered.
  - Board: 14 flows — overlay/hover, click-to-comment with tags + Must fix, thread pins and cards, measure (8.2971 mm with nearest points), select popover, view old revision + back to latest, diff overlay (72 removed entities), back-side hit filtering, 3D render, branch create+switch, restore an old version. Zero console errors.

### Key challenges
- Both OpenRouter keys used during development hit their limits during this stretch (401 "User not found"; 403 key limit). The post-merge browser e2e therefore ran on `google:gemini-3.1-pro-preview`; the earlier headless e2e had used claude-sonnet-5. `pydantic-ai-slim[google]` is now a declared extra, and the README documents both routes.
- A server started with an empty API key surfaces as a 401 "Missing Authentication header" in the run's `RUN_ERROR` event, not as a startup failure. Check the key before blaming the model route.
- e2e script friction worth remembering: `page.waitForSelector("path.hit")` fails on zero-area track hit lines because Playwright treats them as invisible (board-layout dependent) — wait for a hit path with real `getBoundingClientRect` area instead. The Run-goal button is correctly disabled while any run is active, so `agent.mjs` must wait for the chat run to finish first. Compare on two consecutive silkscreen-label commits yields an empty diff: the pick index has no text entities, so reference-text moves are not diffable (documented in `harness/web/NOTES.md`).
- Goal-mode auto-continue paused twice for "low progress" while a background subagent was legitimately building; the work was fine, but rapid resume-then-wait cycles waste turns. Better to end the turn and let the subagent's completion notification drive.

## 2026-10-17 — Real-Claude browser e2e and ship

### What was done
- **Restored the Claude route.** The shared OpenRouter keys used earlier had hit their limits, so this project got a dedicated key with a small cap. The route itself stayed `openai:anthropic/claude-sonnet-5` via an OpenAI-compatible provider.
- **Re-ran both browser walkthroughs against real Claude** (`openai:anthropic/claude-sonnet-5` via OpenRouter) on the fixed server, from a freshly seeded `blinker-demo`:
  - `agent.mjs`: 27 tool cards; the autonomous goal run made 22 tool calls over 13 versions (outline → 9 footprint moves → query → rip-up → ref text → Freerouting autoroute → check → render → mark_addressed → check) and the persisted event stream ends with `goal_met: true`. Steering, supervised approval (`set_board_outline` → Approve → applied, version a03ce8c), show_version + compare_versions, and Activity replay all worked. Zero console errors.
  - `walk.mjs`: 14 flows passed — comment with tags/Must-fix, thread pins and cards, measure 9.6025 mm, select popover, view old revision + back, diff overlay (66 removed), back-side filter, 3D render, branch create/switch, restore ("Restore eb86be1").
- Deleted `harness/web/e2e/serve_patched.py` (the B1 runtime shim) now that `agui_compat.py` is the real fix, and updated the notes that referenced it.
- Merged `harness-v1` into `main` and pushed (`176ed3a..522b75c`); reran the suite on `main`: **172 passed**.

### Key challenges
- The goal's own review criterion is only satisfied at the moment the agent finishes: `walk.mjs` deliberately leaves a throwaway thread, so `goal/status` reads "not met" afterwards (1 open thread) even though the run's event stream shows `goal_met: true` with all six criteria. Read the run events, not the post-walk status, when auditing.
- A per-key OpenRouter limit shows up as 403 "Key limit exceeded", while a deleted key shows as 401 "User not found" and an unset env var as 401 "Missing Authentication header" — three different-looking failures with the same practical meaning.
