---
allowed-tools: Agent, TaskCreate, TaskList, TaskUpdate, TaskGet, Read, Glob, Grep
---

# PCB Design Review

Run a comprehensive design review of the current PCB layout against all `.agents/rules/pcb-*.md` rule files using parallel sub-agents.

## Instructions

1. **Find board files** — locate the render data JSON, layout script, and PCB file in the project. If `$ARGUMENTS` specifies a path, use that as the render data file. Otherwise search for `render_data*.json` in the project.

2. **Create tasks** — one per review domain. Each task maps to a specific rule file:

| Task | Rule File | Focus |
|------|-----------|-------|
| Placement | `pcb-placement.md` | IC priority, decoupling distance, grouping, orientation, signal flow, spacing |
| Routing | `pcb-routing.md` | 45-degree bends, 3W spacing, return vias, via count, return path continuity |
| Power | `pcb-power.md` | Trace widths, decoupling strategy (3-stage), current handling, VRM layout |
| DFM | `pcb-dfm.md` | Trace/space minimums, copper balance, fiducials, tombstoning, edge clearance |
| EMC | `pcb-emc.md` | Return paths, loop area, via stitching, board edge treatment, decoupling |
| Thermal | `pcb-thermal.md` | Power dissipation calc, derating, thermal vias, copper spreading |
| Silkscreen | `pcb-silkscreen.md` | Text sizing, pad clearance, text-to-text overlap, polarity marks |
| Test/Debug | `pcb-test-debug.md` | Test points, probe access, power indicators, debug headers |
| Mechanical | `pcb-mechanical.md` | Mounting holes, corner radii, board dimensions, keepouts, panelization |
| Copper Pours | `pcb-copper-pours.md` | When to pour, stitching vias, dead copper, thermal relief |
| BOM/Components | `pcb-bom-components.md` | Derating, lifecycle, alternates, MSL, ESD sensitivity |
| Stackup | `pcb-stackup.md` | Layer count decision, impedance, material selection |

3. **Launch agents** — spawn all review agents in parallel with `run_in_background: true`. Each agent gets this prompt:

```
You are reviewing a PCB layout for compliance with [DOMAIN] rules. DO NOT write any code — research only.

Read these files:
1. .agents/rules/pcb-[rule-file] — the design rules
2. [layout script path] — component positions and routing code
3. [render data JSON path] — board data (components, tracks, vias, outline)

Context: [brief description of the circuit — what it is, approximate frequency, layer count, component count]

Check ALL applicable rules in the rule file against this board.
For rules that don't apply to this design (e.g., RF rules on a DC circuit), note them as N/A with a brief reason.

Report a structured list:
- PASS: rules that are satisfied (brief note why)
- VIOLATIONS: rules that are broken (with specific coordinates, values, and what the rule requires)
- IMPROVEMENT SUGGESTIONS: things that could be better (note if essential, moderate, or nice-to-have)
```

4. **Collect results** — as each agent completes, mark its task done.

5. **Consolidate** — when all agents finish, produce a single summary table organized by severity:

```markdown
### Critical (should fix)
| # | Issue | Source | Fix |
|---|-------|--------|-----|

### Moderate (should address)
| # | Issue | Source | Fix |
|---|-------|--------|-----|

### Minor / Nice-to-have
| # | Issue | Source |
|---|-------|--------|
```

Deduplicate findings that appear in multiple reviews (e.g., "missing bypass cap" from both Power and EMC reviews). Credit all sources.
