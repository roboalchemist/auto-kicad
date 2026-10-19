# PCBWay PCBA Guide for KiCad Projects

Complete reference for submitting KiCad designs for PCB Assembly at PCBWay.

**Last updated:** April 2026  
**KiCad version tested:** 9.0.4  
**Source:** Live PCBWay documentation + community validation

---

## TL;DR — What You Need

Three files submitted together:

1. **Gerber ZIP** — all PCB layers (same as bare PCB order)
2. **BOM** — Excel/CSV with MPN + manufacturer + distributor part number
3. **Centroid/CPL** — pick-and-place file with X/Y coordinates in mm

Use the **PCBWay KiCad plugin** (KiCad Plugin Manager) for one-click generation + direct order submission. See [Tool Options](#2-kicad-export-tools) below.

**Key difference from JLCPCB:** PCBWay has no fixed component catalog — it sources from distributors (Digi-Key, Mouser, LCSC, etc.) using the MPN you provide. No "LCSC Part #" concept. More flexible sourcing, especially for non-standard parts.

---

## 1. File Format Specifications

### Gerber ZIP

Identical RS-274X format to JLCPCB. Same file set required:

| File | Layer |
|------|-------|
| `*.gtl` | F.Cu |
| `*.gbl` | B.Cu |
| `*.g1`, `*.g2` | Inner layers (4-layer) |
| `*.gts`, `*.gbs` | Solder mask |
| `*.gto`, `*.gbo` | Silkscreen |
| `*.gtp`, `*.gbp` | Solder paste (required for SMT) |
| `*.gm1` | Edge.Cuts |
| `*.drl` | Excellon drill files |

PCBWay also accepts direct `.kicad_pcb` import for Gerber viewer review.

### BOM File

Accepted formats: `.xls`, `.xlsx`, `.csv` (PDF explicitly rejected).  
Sample template: https://www.pcbway.com/img/images/pcbway/Sample_BOM_PCBWay.xlsx

**Columns by sourcing mode:**

| Column | Consigned/Kitted | Turn-key |
|--------|-----------------|---------|
| Line # | Required | Required |
| Quantity Per Part Number | Required | Required |
| Reference Designator | Required | Required |
| Part Number | Required | Required |
| Part Description | Required | Required |
| Package/Footprint | Required | Required |
| Type (SMT / THT / Hybrid) | Required | Required |
| Manufacturer Name | — | Required |
| Manufacturer Part Number (MPN) | — | Required |
| Distributor Part Number | — | Required |

Notes:
- Designators must exactly match the silkscreen on the PCB
- For passives with no part number, provide value + package (e.g. "100nF 0402")
- Type field: `SMT`, `THT`, or `Hybrid` — explicit, not inferred

### Centroid / CPL File

Accepted formats: `.xlsx`, `.txt`, `.pos` (KiCad's native `.pos` is accepted directly).  
Sample: https://www.pcbway.com/img/images/pcbway/a-sample-of-PCBWay-Centroid-File.txt

Required columns:

| Column | Notes |
|--------|-------|
| Reference Designator | Must match BOM and silkscreen exactly |
| X-coordinate | mm only |
| Y-coordinate | mm only |
| Rotation angle | Degrees; 0° = pin 1 pointing right (IPC convention) |
| Board Layer | `Top` / `Bottom` |

- THT-only components can be excluded from the centroid file
- Centroid file is mandatory for any SMD component

**KiCad `.pos` file is accepted directly** — no header renaming required. PCBWay reads the standard `Reference`, `PosX`, `PosY`, `Rotation`, `Side` columns.

---

## 2. KiCad Export Tools

### Option A: PCBWay Official Plugin (Recommended)

**GitHub:** https://github.com/pcbway/PCBWay-Plug-in-for-Kicad

Install via KiCad Plugin Manager → search "PCBWay".

Features:
- Exports Gerber files, IPC-Netlist, BOM, and pick-and-place in one click
- **Direct order submission** to PCBWay's order system without manual file upload
- Supports MPN fields for component sourcing

### Option B: Manual Export from KiCad 9.0

Full walkthrough: https://www.pcbway.com/helpcenter/generate_gerber/How_to_Export_Gerber__BOM__and_Pick_and_Place_Files_in_KiCad_9_0.html

```bash
KICAD=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli

# Gerbers
$KICAD pcb export gerbers --board-plot-params -o /tmp/gerbers/ board.kicad_pcb
$KICAD pcb export drill --format excellon --excellon-separate-th --excellon-units mm -o /tmp/gerbers/ board.kicad_pcb

# BOM
$KICAD sch export bom \
  --fields "Reference,Value,Footprint,\${QUANTITY},MPN,Manufacturer" \
  --labels "Designator,Description,Package,Qty,Part Number,Manufacturer Name" \
  --group-by "Value,Footprint" --exclude-dnp \
  -o bom.csv schematic.kicad_sch

# CPL (PCBWay accepts KiCad's native .pos format directly)
$KICAD pcb export pos \
  --units mm --format csv --exclude-no-load \
  -o centroid.pos board.kicad_pcb
```

---

## 3. Component Sourcing Modes

PCBWay offers four modes — choose at quote time:

| Mode | Description | When to Use |
|------|-------------|-------------|
| **Turn-key** | PCBWay sources everything from distributors you specify | Standard production; all MPNs known |
| **Partial turn-key** | PCBWay sources most; customer supplies a few | Mix of standard + hard-to-source parts |
| **Combo** | Customer supplies some; PCBWay sources rest | When you have existing inventory |
| **Consigned / Kitted** | Customer ships all components; PCBWay assembles only | Full inventory control; custom/exotic parts |

**No PCBWay part numbers exist.** Provide MPNs from standard distributors (Digi-Key, Mouser, LCSC, etc.) in the BOM. PCBWay sources from those distributors. You can include a supplier link in the BOM for clarity.

### Consignment Requirements

PCBWay PCBA Material Preparation Spec (Serial PCBWay20181230-01):
- 01005–0805 passives, qty 1–20: provide **>10 pieces per value** (feeder loading consumes ~10 pcs regardless of order qty)
- Qty >1000: provide **5% extra**
- Reel-packaged parts: need ≥50mm blank tape before first component as feeder lead-in
- Leftover parts not returned by default (confirm with sales rep if needed)

---

## 4. Assembly Types Supported

| Type | Supported | Notes |
|------|-----------|-------|
| SMT | Yes | All packages including BGA |
| THT | Yes | Wave solder or hand solder |
| Mixed (SMT + THT) | Yes | SMT first, then THT; mark "Hybrid" in BOM Type column |
| BGA | Yes | X-ray inspection available |
| Double-sided | Yes | Both sides assembled |

**MOQ:** 1 piece. Prototype pricing starts around $88 for 10 pcs (components billed separately).

---

## 5. Design Constraints for Assembly

### Component Spacing

| Requirement | Spec |
|-------------|------|
| Minimum trace/space | 4 mil (0.1 mm); recommended 6 mil (0.15 mm) |
| Component-to-component | ≥ 0.15–0.2 mm minimum |
| Smallest supported package | 0201 and finer |

### Fiducial Marks

- **Size:** 1 mm diameter bare copper circle (no solder mask)
- **Keepout zone:** 10 mm diameter copper-free area around each fiducial
- **Minimum:** 3 per assembly side (2 in diagonally opposite corners minimum)
- **Local fiducials:** Strongly recommended around fine-pitch ICs (QFP, BGA, 0.5mm pitch or finer)

### Panelization

For assembly, PCBWay requires breakaway rails on conveyor sides:
- **Rail width:** Minimum 5 mm, recommended 10 mm
- **V-scoring:** Continuous across full panel only; cannot stop mid-panel
- **Tab-route (mouse-bite):** Use for irregular shapes, mixed designs, or boards with edge cutouts
- V-scoring cannot be used if boards have cutouts along the edge

PCBWay can create the panel for you — submit individual board Gerber + specify layout.

### Tooling Holes

- 2.0 mm NPTH, minimum 2 (preferably 3) per panel
- Not within 5 mm of board edge

### Polarity / Assembly Drawing

If silkscreen clearly shows polarity (cathode dot, +/− on caps, pin-1 mark on ICs), a separate assembly drawing is not needed. Declare any deviations from standard conventions explicitly.

---

## 6. Inspection and Testing Services

### Included by Default

| Service | What It Catches |
|---------|----------------|
| **Visual Inspection** | Manual check after SMD process |
| **AOI** (automated optical) | Component presence, polarity, solder bridges — **free** |

### Add-On Services

| Service | Notes | When Required |
|---------|-------|---------------|
| **X-Ray** | Hidden solder joint inspection | BGA, QFN, LGA packages |
| **ICT** (in-circuit test) | Bed-of-nails fixture; tests component values + connectivity | High volume (100+ units); high NRE for fixture |
| **FCT** (functional circuit test) | Customer supplies test scope, instruction, fixture; PCBWay designs jig, sets up instruments, produces report | Production volumes where NRE amortizes |
| **Flying Probe** | Available on request; no fixture needed | Prototype quantities |

**FCT workflow:** PCBWay's testing engineer reviews your test specification, designs the jig if needed, sets up instruments, and provides a test report. For functional test, you supply: test scope document, test procedure, pass/fail criteria, and fixture design (or PCBWay designs it for you with cost).

**Note:** AOI, X-ray, ICT, and FCT costs are quoted per-order — not published as flat rates.

---

## 7. PCBWay vs JLCPCB — Choose the Right One

| Factor | PCBWay | JLCPCB |
|--------|--------|--------|
| **Component library** | No in-house library; source any MPN from any distributor | 300k+ LCSC-linked catalog; Basic parts free, Extended +$3/type |
| **Part ID format** | Manufacturer Part Number (MPN) | LCSC Part Number (`Cxxxxx`) |
| **SMT prototype cost** | ~$88+ for 10 pcs | ~$20–40 for 10 pcs (with LCSC stock parts) |
| **THT/mixed assembly** | Native, wave + hand solder | Hand solder only, extra fee |
| **Exotic/discontinued parts** | Best — source from any distributor | Needs consignment; designed around LCSC catalog |
| **BGA assembly** | Yes, with X-ray | Yes |
| **Double-sided** | Yes | Yes (Standard PCBA required) |
| **Turnaround** | 24h–5 days after parts arrive | 24h–3 days with LCSC stock |
| **KiCad plugin** | Official PCBWay plugin | Bouni/kicad-jlcpcb-tools or Fabrication Toolkit |
| **Order process** | Quote-based (slower for first order) | Self-serve interactive (fast) |
| **Best for** | THT/mixed, exotic parts, turn-key with any MPN, production-grade testing, BGA | Simple SMT prototypes, fast cheap iteration, LCSC-stock designs |

**Rule of thumb:** 
- Pure SMT + common parts + prototype quantity → JLCPCB
- THT/mixed board, exotic parts, BGA, or need flexibility in sourcing → PCBWay

---

## 8. Order Process

1. Go to pcbway.com → PCB Assembly → Get Instant Quote
2. Upload Gerber ZIP → configure PCB specs
3. Select **assembly type** (SMT/THT/Mixed), **sourcing mode** (turn-key, partial, consigned)
4. Upload BOM + Centroid files
5. PCBWay reviews and sends a quote with component pricing breakdown
6. Confirm order → ship consigned parts if applicable
7. Production begins once components are received

For consigned orders: production cannot start until your parts arrive at the PCBWay warehouse.

---

## 9. Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| BOM rejected | Submitted as PDF | Use .xls/.xlsx/.csv only |
| Rotation errors | KiCad vs PCBWay rotation convention mismatch | Verify .pos file against PCBWay's centroid sample; use PCBWay plugin |
| Long lead time | Parts ordered from distributor | Provide distributor stock links in BOM; prefer in-stock MPNs |
| Missing fiducials on fine-pitch IC | No local fiducials around QFP/BGA | Add local fiducial pair near any 0.5mm pitch component |
| V-score panel failure | Board has edge cutouts | Switch to tab-route (mouse-bite) panelization |
| Consignment part shortage | Forgot feeder lead-in waste | Add 10+ extra pcs per value; 50mm blank tape lead-in for reels |

---

## Related Files

- `JLCPCB_PCBA_GUIDE.md` — JLCPCB equivalent (cheaper for SMT prototypes, catalog-based)
- `demo/drc_rules.py` — 27-check DRC engine against JLCPCB manufacturing rules (rules largely apply to PCBWay too)
- `data/jlcpcb-components.sqlite3` — local JLCPCB parts DB; LCSC MPNs from here work in PCBWay BOM
- `README.md` — kicad-agent project overview
