# JLCPCB PCBA Guide for KiCad Projects

Complete reference for submitting KiCad designs for PCB Assembly at JLCPCB.

**Last updated:** April 2026  
**KiCad version tested:** 9.0.4  
**Source:** Live JLCPCB documentation + community validation

---

## TL;DR — What You Need

Three files, uploaded in sequence on jlcpcb.com:

1. **Gerber ZIP** — all PCB layers (same as bare PCB order)
2. **BOM CSV** — component list with LCSC part numbers
3. **CPL CSV** — component placement/pick-and-place coordinates

Use **Bouni/kicad-jlcpcb-tools** (KiCad Plugin Manager) to generate all three in one click with live LCSC part number assignment. See [Tool Options](#2-kicad-export-tools) below.

---

## 1. File Format Specifications

### Gerber ZIP

Standard RS-274X format. Same files as any bare PCB order from JLCPCB. Required layers:

| File | Layer |
|------|-------|
| `*.gtl` | F.Cu (front copper) |
| `*.gbl` | B.Cu (back copper) |
| `*.g1`, `*.g2` | In1.Cu, In2.Cu (inner layers, 4-layer boards) |
| `*.gts` | F.Mask (front solder mask) |
| `*.gbs` | B.Mask (back solder mask) |
| `*.gto` | F.Silkscreen |
| `*.gbo` | B.Silkscreen |
| `*.gtp` | F.Paste (solder paste — required for assembly) |
| `*.gbp` | B.Paste |
| `*.gm1` | Edge.Cuts (board outline) |
| `*.drl` | Excellon drill files (PTH + NPTH) |

Zip all into one archive. KiCad Fabrication Toolkit handles this automatically.

### BOM CSV

Required columns (exact names):

| Column | Description | Example |
|--------|-------------|---------|
| `Comment` | Component value and specs | `100nF 50V X7R` |
| `Designator` | Reference designators (comma-separated) | `C1, C2, C5` |
| `Footprint` | Package type | `0805` |
| `LCSC Part #` | LCSC catalog number | `C49678` |

Rules:
- `LCSC Part #` format is always `C` followed by digits (e.g. `C6187`)
- Each designator appears exactly once across all rows
- Case must match exactly between BOM and CPL (`R1` ≠ `r1`)
- Max 200 designators per row; split into multiple rows if needed

### CPL CSV (Component Placement List)

Required columns (exact names):

| Column | Description | Example |
|--------|-------------|---------|
| `Designator` | Reference designator | `U1` |
| `Mid X` | X coordinate of component center (mm) | `25.4` |
| `Mid Y` | Y coordinate of component center (mm) | `12.7` |
| `Layer` | Board side | `Top` or `Bottom` |
| `Rotation` | Counter-clockwise degrees | `90` |

Rules:
- Coordinates in **millimeters only**
- `Top`/`top`/`T` and `Bottom`/`bottom`/`B` all accepted for Layer
- Rotation is **counter-clockwise**; 0° = pin 1 at left/standard orientation

**KiCad default export column mapping (rename required if not using a plugin):**

| KiCad exports as | JLCPCB requires |
|-----------------|-----------------|
| `Ref` | `Designator` |
| `PosX` | `Mid X` |
| `PosY` | `Mid Y` |
| `Rot` | `Rotation` |
| `Side` | `Layer` |

---

## 2. KiCad Export Tools

### Option A: Bouni/kicad-jlcpcb-tools (Recommended)

**GitHub:** https://github.com/Bouni/kicad-jlcpcb-tools — 1,862 stars, updated April 2026

Install via KiCad Plugin Manager → search "kicad-jlcpcb-tools".

Features:
- Generates Gerber ZIP + BOM CSV + CPL CSV in one click (all headers correct)
- **Live JLCPCB parts database search** inside KiCad — search by keyword/MPN, see stock and pricing, assign LCSC numbers without leaving the editor
- Syncs `LCSC` field from schematic symbols ("Fetch LCSC from Schematic" button)
- Excludes DNP components automatically
- Marks components with `JLCPCB_IGNORE=True` to exclude from BOM/CPL

**Required schematic field:** Add a field named `LCSC` to each symbol with the `Cxxxxx` value. The plugin reads this field.

### Option B: bennymeg/Fabrication-Toolkit

**GitHub:** https://github.com/bennymeg/Fabrication-Toolkit — 616 stars  
Install via KiCad Plugin Manager → search "Fabrication Toolkit".

⚠️ **Known bug in KiCad v9:** `JLCPCB Rotation Offset` attribute is ignored (issue #195). Use `FT Rotation Offset` field instead.

Features:
- Single-click ZIP archive (Gerbers + BOM + CPL)
- Reads `LCSC Part #`, `LCSC Part`, `LCSC`, `JLCPCB Part #`, `MPN`, `mpn` fields (priority order)
- CLI mode for CI/CD: `python3 -m plugins.cli -p board.kicad_pcb --autoTranslate --excludeDNP --autoFill`

### Option C: kicad-cli (command-line, no plugin)

```bash
KICAD=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli

# Gerbers
$KICAD pcb export gerbers --board-plot-params -o /tmp/gerbers/ board.kicad_pcb
$KICAD pcb export drill --format excellon --excellon-separate-th --excellon-units mm -o /tmp/gerbers/ board.kicad_pcb

# BOM (group by Value+Footprint, exclude DNP)
$KICAD sch export bom \
  --fields "Reference,Value,Footprint,\${QUANTITY},LCSC" \
  --labels "Designator,Comment,Footprint,Qty,LCSC Part #" \
  --group-by "Value,Footprint" --sort-field Value --exclude-dnp \
  -o bom.csv schematic.kicad_sch

# CPL/positions
$KICAD pcb export pos \
  --units mm --format csv --exclude-no-load \
  -o positions.csv board.kicad_pcb
```

Post-process the CPL to rename headers: `Ref→Designator`, `PosX→Mid X`, `PosY→Mid Y`, `Rot→Rotation`, `Side→Layer`.

---

## 3. LCSC Part Numbers

### How to Find Them

1. Go to https://jlcpcb.com/parts or https://lcsc.com
2. Search by component type + value + package
3. Filter by **"Basic Parts"** to avoid extended part fees
4. Filter by **"Assembly"** availability (not all LCSC parts can be assembled)
5. Copy the `Cxxxxx` number into the `LCSC` field on your KiCad symbol

### Adding LCSC to KiCad Symbols

In schematic editor: select symbol → `E` → Properties table → add field:
- **Field name:** `LCSC`
- **Field value:** `C6187` (example)

Best practice: create a custom symbol library with LCSC pre-populated per component type.

Automated approach: use **JLC2KiCad_lib** to import components directly from the JLCPCB/EasyEDA database with correct footprint + LCSC pre-filled:

```bash
pip install JLC2KiCadLib
JLC2KiCadLib C6187   # generates AMS1117-5.0 symbol+footprint+3D model
```

### Basic vs Extended Parts

| Tier | Description | Fee per type |
|------|-------------|-------------|
| **Basic** | ~698 types; pre-loaded on P&P machines | $0 |
| **Extended** | 300,000+ types; loaded per order | $3/unique type (Economic PCBA) |

Common Basic parts: standard 0402/0603/0805 resistors/caps, AMS1117 regulators, common transistors.

---

## 4. Assembly Service Options

### Economic PCBA

- Boards batched with other customers' orders on shared panel
- Setup fee: **$8/order** + $1.50 stencil
- SMT assembly: **$0.0016/joint**
- THT (hand solder): **$0.0157/joint** + $3.50 labor fee/order
- Extended part loading: **$3.00/unique type**
- Best for: small prototype runs with mostly LCSC-stock SMT parts

### Standard PCBA

- Dedicated panel (no co-batching)
- Setup fee: **$25** (single-side) / **$50** (double-side)
- Same per-joint pricing as Economic
- Loading fee: **$1.50/type** (all types, not just extended)
- Best for: double-sided boards, production volumes, boards with sensitive co-batching concerns

### THT Assembly

THT is **hand-soldered only** (no wave solder at JLCPCB). Significantly more expensive per joint ($0.0157 vs $0.0016). For prototype quantities, hand-soldering connectors yourself after SMT assembly is usually more practical.

---

## 5. Component Sourcing

### JLCPCB Stock Parts

Parts in the JLCPCB/LCSC catalog with an LCSC number. Automatic — just include LCSC# in BOM.

### Consignment Parts (Customer-Supplied)

For parts not in JLCPCB's catalog (modules, exotic parts, discontinued ICs):

1. Go to Parts Manager → Consign Parts on jlcpcb.com
2. Search by MPN; if not found → "Consign the part directly" → fill specs
3. JLCPCB reviews/approves (email notification)
4. **Ship components to JLCPCB warehouse** — order cannot start until received
5. Parts appear in "Consigned Parts" in My Parts Lib for future orders

Constraints:
- JLCPCB accepts no liability for quality issues from consigned parts
- Cannot mix JLC-stock and consigned for the same component type in one order
- International shipments need invoice + customs documentation

### Global Sourcing

JLCPCB can source parts from third-party distributors on your behalf. Add lead time and cost. Mixed experiences reported for uncommon parts.

---

## 6. Design Constraints for Assembly

### Component Clearances

| Requirement | Spec |
|-------------|------|
| Component-to-board-edge | ≥ 2.5 mm (body) |
| Component-to-component spacing (CPL) | ≥ 0.2 mm center-to-center |
| IPC-7351B density | Medium or Low density only (not High) |

### Fiducials

Required for pick-and-place alignment. JLCPCB will add them if yours are missing — select **"Added by JLCPCB"** at order time.

If adding manually:
- Copper circle: 1 mm diameter
- Solder mask opening: 1 mm diameter
- Copper-free keepout: 3 mm radius around fiducial center
- Minimum 3 fiducials per assembly side
- Location: board corners or panel rail, 3.85 mm from edge

### Process Edges (Panels)

JLCPCB adds rails to your board for the P&P conveyor. Minimum 5 mm rails on conveyor sides. Tooling holes: 2 mm NPTH. These can be added by JLCPCB automatically.

---

## 7. Rotation Errors (Most Common Pitfall)

KiCad footprint rotation 0° and JLCPCB's pick-and-place reference differ for many packages. Components arrive rotated 90°/180°/270° after assembly.

**Fix per-component:** Add `FT Rotation Offset` custom property to the symbol (degrees, positive = counter-clockwise):

```
FT Rotation Offset = 180
```

The kicad-jlcpcb-tools plugin maintains a corrections database for common packages.

**Verify in JLCPCB's visual CPL preview** before confirming — every component shows as a rectangle with a red dot for pin 1. Fix any obviously wrong ones directly in the JLCPCB UI without re-uploading.

⚠️ `bennymeg/Fabrication-Toolkit` has an active KiCad v9 bug (issue #195) where `JLCPCB Rotation Offset` is ignored. Use `FT Rotation Offset` field name instead.

---

## 8. Inspection and Testing

### Included by Default (Every Order)

| Service | What It Catches |
|---------|----------------|
| **SPI** (solder paste inspection) | Paste volume, alignment, bridging before placement |
| **AOI** (automated optical inspection) | Missing parts, wrong polarity, solder bridges, tombstoning |
| **Visual inspection** | Manual supplementary check |

### Add-On Services

| Service | Usefulness | Notes |
|---------|-----------|-------|
| **Flying Probe** (electrical test) | High for prototypes | Tests opens/shorts/connectivity; no fixture needed; ~$10-20 |
| **X-Ray** | BGA/QFN only | Skip if no hidden-joint packages |
| **FCT** (functional test) | Production volumes only | Customer supplies fixture + test spec + firmware; high NRE |
| **Firmware flash** | Negotiate manually | "Partially supported" — contact support with .bin + flash method; requires USB/UART test points on PCB |

**Recommendation for first prototype run:** Default AOI + add Flying Probe.

---

## 9. Order Process

1. Upload Gerber ZIP → configure PCB specs (layers, finish, quantity)
2. Enable **"PCB Assembly"** toggle → choose Economic or Standard, top/bottom/both
3. Upload BOM CSV + CPL CSV
4. **Interactive BOM review** — JLCPCB auto-matches by LCSC#; fix any "Unselected" rows; verify Basic vs Extended classification
5. **Visual CPL preview** — check all rotation/placement; edit directly in UI for any wrong rotations
6. Enable **"Confirm production files"** — engineer reviews Gerbers before production (strongly recommended)
7. Review quote and complete order

---

## 10. Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Components rotated 90°/180° | KiCad/JLC rotation reference mismatch | Add `FT Rotation Offset` field; verify in visual preview |
| BOM row shows "Unselected" | LCSC# not provided or not found | Search and manually assign in interactive BOM review |
| Order forced to Standard PCBA | Board has Standard-Only parts (0201, certain ICs) | Check "PCBA Type" field in jlcpcb.com/parts per component |
| Placement offset errors | Component origin ≠ body center | Add `FT Position Offset` field (mm, `x,y` format) |
| Extended part fee surprise | Part not in Basic tier | Filter by Basic parts when selecting alternatives |
| Board not assembling | THT on shared panel | Use Standard PCBA or hand-solder THT yourself |

---

## Related Files

- `PCBWAY_PCBA_GUIDE.md` — PCBWay equivalent (more flexible sourcing, better for THT/mixed)
- `demo/drc_rules.py` — 27-check DRC engine against JLCPCB manufacturing rules
- `data/jlcpcb-components.sqlite3` — 437k JLCPCB parts local DB (query with Python/sqlite3)
- `README.md` — kicad-agent project overview

---

## Querying the Local JLCPCB Parts DB

```python
import sqlite3
db = sqlite3.connect('data/jlcpcb-components.sqlite3')
db.row_factory = sqlite3.Row
c = db.cursor()

# Look up by LCSC number
c.execute('SELECT lcsc, mfr, package, basic, stock FROM components WHERE lcsc = ?', (6187,))
print(c.fetchone())  # AMS1117-5.0, SOT-223, basic=1, stock=148715

# Find all Basic 0805 parts
c.execute('SELECT lcsc, mfr, package, stock FROM components WHERE package="0805" AND basic=1 ORDER BY stock DESC LIMIT 10')
for r in c.fetchall(): print(r['lcsc'], r['mfr'], r['stock'])

# Search by manufacturer name
c.execute('SELECT lcsc, mfr, package, basic, stock FROM components WHERE mfr LIKE "%MAX485%" ORDER BY stock DESC LIMIT 5')
for r in c.fetchall(): print(r['lcsc'], r['mfr'], r['package'], r['stock'])
```
