---
name: pcb-design
description: PCB design knowledge base covering layout, routing, signal integrity, power, EMC, manufacturing, and more. Use when designing PCBs, reviewing layouts, or making component placement and routing decisions.
---

# PCB Design Knowledge Base

## Contents
- [Overview](#overview)
- [Examples](#examples)
- [Topic Index](#topic-index)
- [Quick Reference](#quick-reference)

## Overview

Comprehensive PCB design rules for use with KiCad and general PCB layout. Covers the full design lifecycle from requirements through manufacturing handoff. Rules are organized by topic in `reference/` files — read only what's relevant to the current task.

<examples>
<example>
Task: Route USB 3.0 differential pairs on a 4-layer board

Read [reference/high-speed.md](reference/high-speed.md) for impedance targets (100Ω diff), skew limits (±10mil), and back-drill requirements. Cross-reference [reference/stackup.md](reference/stackup.md) for trace width on your dielectric spacing.
</example>

<example>
Task: Place decoupling capacitors for a mixed-signal ADC

Read [reference/mixed-signal.md](reference/mixed-signal.md) for ADC/DAC layout rules: 100nF within 2mm of each power pin, ferrite bead filtering between analog/digital domains, and guard ring placement around sensitive inputs.
</example>

<example>
Task: Prepare manufacturing files for a prototype board

Read [reference/dfm.md](reference/dfm.md) for trace/space minimums, then [reference/solder-mask-finish/surface-finish.md](reference/solder-mask-finish/surface-finish.md) for surface finish selection. Check [reference/silkscreen.md](reference/silkscreen.md) for text sizing. Use [reference/version-control/release-management.md](reference/version-control/release-management.md) for file naming and release checklist.
</example>

<example>
Task: Design a 4-layer stackup for a board with USB and Ethernet

Read [reference/stackup.md](reference/stackup.md) for standard 4-layer patterns (SIG-GND-GND-SIG vs SIG-GND-PWR-SIG), impedance implications, and material selection. Cross-reference [reference/emc.md](reference/emc.md) for grounding strategy.
</example>

<example>
Task: Review thermal management for a power regulator layout

Read [reference/thermal.md](reference/thermal.md) for thermal via sizing (0.3mm optimal), copper spreading rules, and TIM selection. Check [reference/power.md](reference/power.md) for VRM layout distance rules (<5mm output to IC).
</example>
</examples>

## Topic Index

### Core Workflow
| Topic | File | Key Content |
|-------|------|-------------|
| Design process | [design-process.md](reference/design-process.md) | 8-phase workflow, dependencies, sequencing mistakes |
| Placement | [placement.md](reference/placement.md) | Priority order, grouping, orientation, spacing, thermal |
| Routing | [routing.md](reference/routing.md) | Priority, trace geometry, spacing, signal integrity, vias |
| Metrics | [metrics.md](reference/metrics.md) | Wirelength, congestion, directness, via count, quality scores |
| Autorouter | [autorouter.md](reference/autorouter.md) | Algorithm selection, cost functions, human-guided approach |
| **Design review** | [review.md](reference/review.md) | Parallel review process, agent prompts, 12-domain checklist, `/pcb-review` |

### Signal Integrity & Stackup
| Topic | File | Key Content |
|-------|------|-------------|
| Stackup | [stackup.md](reference/stackup.md) | Layer count decisions, 4/6-layer patterns, materials, impedance |
| High-speed | [high-speed.md](reference/high-speed.md) | Diff pairs, impedance, termination, via stubs, interface specs |
| Mixed-signal | [mixed-signal.md](reference/mixed-signal.md) | Unified ground, guard rings, ADC/DAC layout, clock isolation |

### Power & EMC
| Topic | File | Key Content |
|-------|------|-------------|
| Power | [power.md](reference/power.md) | Planes, decoupling, PDN impedance, VRM layout, sequencing |
| EMC/EMI | [emc.md](reference/emc.md) | Grounding, via stitching, shielding, ESD, filtering, compliance |

### Physical & Thermal
| Topic | File | Key Content |
|-------|------|-------------|
| Thermal | [thermal.md](reference/thermal.md) | Thermal vias, relief pads, copper spreading, simulation, TIM |
| Mechanical | [mechanical.md](reference/mechanical.md) | Mounting holes, board outline, connectors, keepouts, flex |
| Conformal coatings | [reliability/coatings.md](reference/reliability/coatings.md) | Coating types, thickness, application, keep-out areas |
| Potting & vibration | [reliability/potting-vibration.md](reference/reliability/potting-vibration.md) | Encapsulation materials, thermal considerations, mechanical design |
| Environmental reliability | [reliability/environmental.md](reference/reliability/environmental.md) | Thermal cycling, MTBF, humidity, salt spray, IPC classes, materials |

### Manufacturing
| Topic | File | Key Content |
|-------|------|-------------|
| DFM/DFA | [dfm.md](reference/dfm.md) | Trace/space, vias, copper balance, pick-and-place, tombstoning |
| Silkscreen | [silkscreen.md](reference/silkscreen.md) | Text sizing, clearance, placement, methods, color |
| Copper pours | [copper-pours.md](reference/copper-pours.md) | When to use, clearance, thermal relief, stitching, dead copper |
| Solder mask | [solder-mask-finish/solder-mask.md](reference/solder-mask-finish/solder-mask.md) | Mask types, NSMD/SMD, clearance, dam width, via coverage |
| Surface finish & stencil | [solder-mask-finish/surface-finish.md](reference/solder-mask-finish/surface-finish.md) | HASL/ENIG/OSP/Ag/Sn/Hard Gold, stencil apertures, paste release |

### Advanced Topics
| Topic | File | Key Content |
|-------|------|-------------|
| HDI | [hdi.md](reference/hdi.md) | Microvias, blind/buried vias, SBU process, via-in-pad, cost |
| BGA design & fanout | [bga-fine-pitch/bga-design.md](reference/bga-fine-pitch/bga-design.md) | Fanout by pitch, VIPPO, escape routing, pad design, solder paste |
| Fine-pitch manufacturing | [bga-fine-pitch/bga-manufacturing.md](reference/bga-fine-pitch/bga-manufacturing.md) | QFN/QFP, thermal pads, X-ray inspection, rework, tolerances |
| RF fundamentals | [rf/rf-fundamentals.md](reference/rf/rf-fundamentals.md) | Transmission lines, impedance matching, substrate materials |
| RF layout | [rf/rf-layout.md](reference/rf/rf-layout.md) | Ground planes, antennas, connectors, routing, testing |

### Project Management
| Topic | File | Key Content |
|-------|------|-------------|
| BOM & components | [bom-components.md](reference/bom-components.md) | Derating, lifecycle, alternates, footprint verification, MSL/ESD |
| Test & debug | [test-debug.md](reference/test-debug.md) | Test points, bed-of-nails, flying probe, JTAG/SWD, ICT |
| Git workflow | [version-control/git-workflow.md](reference/version-control/git-workflow.md) | Revisions, file naming, .gitignore, branching, commits |
| Release management | [version-control/release-management.md](reference/version-control/release-management.md) | Design review, ECO process, releases, freeze, library mgmt, archival |

## Quick Reference

### Critical Numbers
- Decoupling cap: **0.1µF within 5mm** of every IC power pin
- Differential pair skew: **±5-25mil** depending on interface
- Trace spacing (3W rule): center-to-center ≥ **3× trace width**
- Return via: within **5-10mil** of signal via on layer transitions
- Board edge clearance: **2-3mm** minimum for components
- Thermal via: **0.3mm diameter**, **0.8mm spacing** grid
- Test point: **1.0mm diameter**, **2.5mm center-to-center**
- Solder mask dam: **4mil minimum** (green mask)

### Design Phase → Topic Mapping
```
Requirements    → design-process, bom-components
Schematic       → bom-components, power
Pre-layout      → stackup, design-process, mechanical
Placement       → placement, thermal, mixed-signal
Routing         → routing, high-speed, power, emc, rf
Verification    → metrics, dfm, emc, test-debug
Manufacturing   → dfm, silkscreen, solder-mask-finish, copper-pours
Review/Handoff  → version-control, bom-components, reliability
```

### Board Validation

Run `drc_rules.py` against the board's `render_data.json` (requires KiCad Python for pcbnew pad geometry):

```bash
$KICAD_PYTHON demo/drc_rules.py demo/render_data_v2.json
```

This performs 27 automated checks across 8 rule files, each violation citing the source rule:

| Category | Checks |
|---|---|
| JLCPCB manufacturing | Pad/via clearance, track width, hole sizes, annular ring, edge clearance, track crossings |
| Silkscreen | Text size, pad clearance, text-to-text overlap |
| Routing | 90-degree bends |
| DFM | Tombstoning risk, fiducials, copper balance |
| Power | Missing bypass caps, cap-to-IC-pin distance |
| EMC | Return via proximity to GND vias |
| Test/Debug | Test points present |
| Mechanical | Pad edge clearance, corner radii, mounting holes, board size, power connector |

For a full multi-agent review (12 domains in parallel), use `/pcb-review`. See [reference/review.md](reference/review.md) for the process and agent prompt template.
