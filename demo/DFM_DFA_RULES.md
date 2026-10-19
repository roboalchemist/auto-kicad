# PCB Design for Manufacturing (DFM) & Design for Assembly (DFA) Rules

A practical reference for designing 2-4 layer PCBs with standard fabrication processes.

---

## 1. TRACE WIDTH & SPACING

### Minimum Specifications
| Property | Standard (6/6 mil) | Tight (5/5 mil) | Conservative |
|----------|-------------------|-----------------|--------------|
| **Trace Width (min)** | 6 mil (0.15 mm) | 5 mil (0.13 mm) | 8 mil (0.2 mm) |
| **Trace-to-Trace Spacing** | 6 mil (0.15 mm) | 5 mil (0.13 mm) | 8 mil (0.2 mm) |
| **Trace-to-Pad Spacing** | 8 mil (0.2 mm) | 6 mil (0.15 mm) | 10 mil (0.25 mm) |
| **Trace-to-Via Spacing** | 8 mil (0.2 mm) | 6 mil (0.15 mm) | 10 mil (0.25 mm) |

### By Copper Weight
- **1 oz. copper (inner)**: Min trace/space = 0.003" (3 mil)
- **2 oz. copper**: Min trace/space = 0.005" (5 mil)
- **3 oz. copper**: Min trace/space = 0.009" (9 mil)
- **4 oz. copper**: Min trace/space = 0.010" (10 mil)

### Best Practices
- Use 6/6 mil as the industry standard sweet spot (80% of fabs can achieve with lowest cost)
- Add 2 mil safety margin above minimums for reliability
- Avoid sharp angles; use 45° or smooth curves instead of 90° corners
- Keep high-speed signals away from board edges (min 0.050" / 1.27 mm)

---

## 2. ANNULAR RINGS (Pad-to-Via Relationship)

### Calculation
**Annular Ring = (Pad Diameter - Hole Diameter) / 2**

Example: If pad = 22 mil and hole = 10 mil, then AR = (22-10)/2 = 6 mil

### Minimum Specifications by IPC Class

| IPC Class | External Layers | Internal Layers | Application |
|-----------|-----------------|-----------------|-------------|
| **Class 2** | 4-6 mil (0.10-0.15 mm) | 3-4 mil | Consumer/Commercial products |
| **Class 3** | 2-3 mil (0.05-0.08 mm) | 1-2 mil (0.025-0.05 mm) | High-reliability, aerospace |

### Via Type Recommendations
- **Mechanically Drilled Vias**: Minimum 3 mil annular ring
- **Laser-Drilled Microvias**: Less than 2 mil annular ring acceptable
- **Standard Through Vias**: 4-5 mil annular ring (safe default)

### Critical Rules
- Always exceed minimum by 2-3 mil for manufacturing margin
- Check annular ring on all layers, especially internal layers where inspection is harder
- Use design rule checks (DRC) to catch violations automatically
- Avoid placing component pads near pad edges (ensure 0.010" / 0.25 mm clearance)

---

## 3. VIA DESIGN RULES

### Via Size Specifications

| Specification | Standard | Minimum | Maximum |
|---------------|----------|---------|---------|
| **Hole Diameter** | 0.012" (12 mil) | 0.008" (8 mil) | N/A |
| **Pad Diameter (external)** | 0.024" (24 mil) | 0.016" (16 mil) | 0.050" |
| **Annular Ring** | 5-6 mil | 3-4 mil | - |
| **Via Spacing (center-to-center)** | 0.025" (25 mil) | 0.020" (20 mil) | - |

### Aspect Ratio (Board Thickness / Hole Diameter)

| Via Type | Ideal AR | Maximum AR | Notes |
|----------|----------|------------|-------|
| **Standard Through Via** | ≤ 8:1 | 10:1 | Higher = harder to plate, thermal stress risk |
| **Blind/Buried Via** | ≤ 4:1 | 8:1 | Deeper vias more vulnerable |
| **Microvia (laser-drilled)** | 0.8:1 | 1.5:1 | High density interconnects |

**Example**: 1.6 mm board (63 mil) with 8 mil hole = 63/8 = 7.9:1 aspect ratio (acceptable)

### Via-in-Pad (VIPPO)

**When to use**:
- High density layouts requiring pad area recovery
- Ball Grid Arrays (BGAs) with fine pitch
- Escape routing from high pin-count components

**Rules**:
- Via must be filled (conductive filled via or solder-filled) unless used as thermal pad
- Filled vias require special fab process and cost premium (~30-50% increase)
- Hole diameter: 0.008"-0.012" (microvias)
- Must still maintain annular ring on filled vias: 2-3 mil minimum
- Declare via-in-pad in Gerber file attributes

### Via Tenting (Solder Mask Coverage)

**Tented Vias** (recommended for most applications):
- Covered with solder mask to prevent solder paste from flowing into via
- Prevents cold solder joints and via-related failures
- Most effective on small vias (< 0.012" / 12 mil diameter)
- Can reduce via pad size slightly (requires less annular ring)

**Untented Vias** (use when):
- Via requires thermal management (heat dissipation)
- Via needs to accept solder for mechanical strength
- Thermal pad area to internal copper for thermal spreading

**Tenting Rules**:
- Specify "tented" or "tented both sides" in fabrication notes
- Provide solder mask clearance file (negative, showing non-masked areas)
- Ensure solder mask material will adhere (avoid edges/crowded areas)

---

## 4. PAD & FOOTPRINT RULES

### Pad Design

| Specification | Requirement |
|---------------|-------------|
| **Minimum Pad Size** | 0.015"-0.020" (15-20 mil) |
| **Pad Spacing (center-to-center)** | ≥ 0.030" (30 mil) for standard SMD |
| **Pad-to-Pad Spacing** | ≥ 0.004" (4 mil) minimum, 0.006"-0.008" recommended |
| **Pad-to-Edge Clearance** | ≥ 0.010" (10 mil) |

### Component-Specific Rules

**Small Passives (0402, 0603)**:
- Symmetrical pad design to minimize tombstoning risk
- Equal pad sizes on both ends
- Consistent trace widths connecting to each pad
- Pad dimensions: 0603 = 0.024" × 0.043" typical

**QFP/LQFP Devices**:
- Pads should be 0.015"-0.020" wide
- Center-to-center spacing follows lead pitch (0.050" standard)
- Solder mask webbing between pads: 0.004"-0.006" minimum

**BGA Devices**:
- Via-in-pad typically required for escape routing
- Pad diameter: 0.020"-0.030"
- Solder ball diameter: 0.025"-0.035" (check component datasheet)

### Thermal Relief on Pads (Thermal Ties / Wagon Wheels)

**When to use**:
- Pads connected to large copper planes (ground, power, heat-spreading)
- Reduces thermal mass to enable reliable soldering
- Prevents "cold solder joints" from excess heat absorption

**Design Rules**:
- Total thermal width ≈ 60% of minimum pad diameter
- Typically 4 spokes, each 0.010"-0.020" wide
- Spoke length: 0.015"-0.030" from pad to plane
- Clearance from pad center to plane: 0.015"-0.025"

**Example**: For 0.050" pad diameter:
- Total thermal width = 0.050 × 0.6 = 0.030"
- 4 spokes = 0.030 / 4 = 0.0075" per spoke (increase to 0.010" for safety)
- Spoke length = 0.020"

**Special Cases**:
- Do NOT use thermal relief on thermal vias (maximum conductivity needed)
- Do NOT use thermal relief on power/ground vias (maximum conductivity)
- Use solid connection for high-current nets (power delivery, return paths)

---

## 5. DESIGN FOR ASSEMBLY (DFA) - COMPONENT PLACEMENT

### Fiducial Marks (Essential for Pick & Place)

**Minimum Requirements**:
- Minimum 3 global fiducial marks per PCB/panel
- At least 2 on opposite corners, 1 elsewhere for skew detection

**Fiducial Specifications**:
- Diameter: 0.050" ± 0.010" (1.27 ± 0.25 mm)
- Pad material: Copper (not solder mask or silkscreen)
- Clearance zone: 0.100" (2.54 mm) radius around fiducial (no copper, no components, no text)
- Location: Positioned on board corners, avoid large components nearby
- Must be on both sides if double-sided assembly

**Positioning Rules**:
- Global fiducials should form a large triangle (maximize area)
- Locate at least 0.100" (2.54 mm) from board edge
- Use same diameter and construction on all fiducials

---

### Component Placement Rules

| Rule | Specification | Why |
|------|---------------|-----|
| **Component Spacing** | ≥ 0.5 mm (20 mil) between pads | Prevent solder bridging |
| **Pad Symmetry** | Both ends of component equal | Prevent tombstoning (especially 0402, 0603) |
| **Trace Routing** | Equal trace width to both pads | Even heating during reflow |
| **Orientation Consistency** | All components on side face same direction | Improves assembly speed, reduces errors |
| **Keepout Zone from Edge** | ≥ 0.050" (1.27 mm) from V-score/tab lines | Prevents damage during depanelization |
| **Component Clearance** | ≥ 0.100" (2.54 mm) from board edge | Allows panel tooling access |
| **Large Component Placement** | Place early in layout (before small parts) | Defines routing paths, improves yield |

### Tombstoning Prevention (Critical for 0402/0603)

**Root Cause**: Uneven solder wetting on left vs. right pad → unequal surface tension → component lifts

**Preventive Measures**:
1. **Pad Symmetry**: Identical pad sizes, shapes, and copper weight on both ends
2. **Thermal Balance**: Connect equal amounts of copper to each pad
   - If one pad must connect to large plane, use thermal relief on that pad
   - Apply equivalent thermal via array or trace copper to opposite pad
3. **Trace Design**: Equal width traces to both pads, same routing distance
4. **Reflow Profile**: Longer "soak" phase (typically 60-120 seconds at 150-200°C) ensures thermal equilibrium
5. **BOM Notes**: Mark sensitive parts for slower conveyor speed through peak temperature zone

---

### Design for Test (DFT) Considerations

| Requirement | Specification |
|-------------|---------------|
| **Test Points** | 0.050"-0.100" diameter, spaced ≥ 0.100" apart |
| **Probe Landing Pads** | Use square pads (easier for probes than round) |
| **Via-as-Test-Point** | Use slightly larger annular ring (add 2 mil) for probe access |
| **Access for Probes** | Keep top of test point clear of solder mask (0.010"-0.020" clearance) |

---

## 6. PANELIZATION & BOARD EDGE RULES

### Panelization Layout

| Rule | Specification | Purpose |
|------|---------------|---------|
| **Board Centering** | Center board in X and Y axes of panel | Ensures even copper distribution, reduces warping |
| **Edge Clearance** | ≥ 0.100" (2.54 mm) from panel edge | Tooling/automation clearance |
| **Via Clearance from Edge** | ≥ 0.050" (1.27 mm) | Prevent via damage during V-score or routing |
| **Trace Clearance from Edge** | ≥ 0.050" (1.27 mm) | Prevent trace damage during depanelization |
| **Tab Width** | 0.080"-0.150" (2-4 mm) | Mechanical strength during handling |
| **Tab Spacing** | ≥ 0.100" (2.54 mm) between tabs | Prevent excessive load on single tab |

### Depanelization Methods

**V-Scoring** (preferred for thin boards):
- Trace clearance: ≥ 0.050" from score line
- Via clearance: ≥ 0.050" from score line
- Can be scored fully (goes through board) or partially (must snap)

**Routing** (for thick boards):
- Trace clearance: ≥ 0.050" from routing line
- Via clearance: ≥ 0.050" from routing line
- Router tool diameter: 0.094"-0.140"

**Tab Break-Off** (manual):
- Tab width: 0.125"-0.200"
- Minimum 2 tabs per board
- Solderable surface on each side if reassembly needed

---

## 7. LAYER STACKUP & COPPER DISTRIBUTION

### Standard 2-Layer PCB

```
Layer 1: Top Copper (signals + planes)
  ↓ Dielectric (1.4 mm typical for FR-4)
Layer 2: Bottom Copper (signals + ground plane)
```

**Rules**:
- Top layer: 70% components, 30% routing
- Bottom layer: Dedicated ground return plane if possible
- If mixed signal/ground: Subdivide planes logically (analog/digital separation)

### Standard 4-Layer PCB

```
Layer 1: Top Copper (components side signals)
Layer 2: Ground Plane (solid, with power islands if needed)
Layer 3: Power Plane (VCC / positive supply)
Layer 4: Bottom Copper (components side signals + return)
```

**Rules**:
- Layer 2 (ground): Solid copper, < 1% vias for isolation
- Layer 3 (power): Solid copper with islands for different voltage domains
- Minimum via count: Use at least 5-10 vias per IC pin to power/ground planes
- Copper distribution: Aim for 40-60% copper density on signal layers

### Copper Balance (Critical for Yield)

**Purpose**: Prevents uneven plating, warping, and etch resist adhesion issues

**Rules**:
- Total copper density: Target 40-60% across entire PCB
- Compare copper % per layer to average (within ±10% of target)
- If layer is copper-light, add non-functional copper:
  - Copper pour with isolation (0.010" clearance)
  - Crosshatch pattern vs. solid pour (easier etch, less warping)
  - Mark as "non-functional copper" in Gerber file comments

**Calculation**:
```
Copper Density = (Copper Area) / (Board Area) × 100%
```

Example: 100 mm² board with 40 mm² copper = 40% density (good)

---

## 8. SOLDER MASK & SILKSCREEN

### Solder Mask Rules

| Specification | Standard | Min |
|---------------|----------|-----|
| **Web Width (between pads)** | 0.010"-0.015" | 0.004" |
| **Clearance from Trace** | 0.008"-0.010" | 0.004" |
| **Via Tenting Clearance** | 0.002"-0.005" | 0.001" |
| **Text Size** | ≥ 0.025" height | 0.020" (risky) |
| **Mask Thickness** | 0.0015"-0.0030" | Fab-dependent |

### Silkscreen Rules

| Rule | Specification | Reason |
|------|---------------|--------|
| **Avoid Over Pads** | ≥ 0.010" clearance from pad edges | Solder mask melts into joint, hides defects |
| **Avoid Over Vias** | ≥ 0.020" clearance | Can block via access, hide rework damage |
| **Avoid Under Components** | Keep clear of component footprint | Blocks access, makes rework harder |
| **Text Orientation** | Consistent direction or 0°/180° only | Pick & place cameras favor horizontal text |
| **Text Size** | ≥ 0.025" (0.635 mm) height | Ensure readability and fab capability |
| **Line Width** | ≥ 0.010" (0.254 mm) | Thinner lines break during printing |

### Mask Clearance from Vias

| Via Type | Clearance Rule |
|----------|----------------|
| **Tented via** | 0.002"-0.005" overlap (solder mask covers via) |
| **Untented via** | 0.004"-0.010" clearance (solder mask opens around via) |
| **Via-in-pad** | 0.002"-0.005" (mask clearance to expose filled pad) |

---

## 9. COMMON DFM VIOLATIONS & HOW TO AVOID THEM

### Critical Violations (Will Cause Fab Rejection)

| Violation | Impact | Prevention |
|-----------|--------|-----------|
| **Annular ring < 2 mil on external layers** | Via pad lift during soldering | Use DRC: min_annular_ring = 4 mil (class 2) or 3 mil (class 3) |
| **Trace-to-pad spacing < 3 mil** | Shorts, bridges, etch adhesion | Set DRC minimum to 8 mil |
| **Pad-to-board-edge < 0.040"** | Damage during routing/V-score | Check all edge-adjacent components |
| **Annular ring missing on internal vias** | Via failure under thermal cycling | Fab will reject; verify in Gerber preview |
| **Via-in-pad without fill spec** | Solder paste flows into via | Declare "filled via" in fabrication notes + Gerber attributes |

### Common Manufacturing Issues (Causes Rework/Scrap)

| Issue | Cause | Prevention |
|-------|-------|-----------|
| **Solder bridges between pads** | Pad spacing < 0.004", excess paste | Ensure 0.006"-0.008" spacing, control paste volume |
| **Cold solder joints** | Insufficient thermal relief on large pads | Use spoke width ≥ 0.010" |
| **Via-induced shorts** | Vias placed in solder mask bridges | Keep vias ≥ 0.050" from exposed traces |
| **Tombstoning** | Unequal pad sizes or thermal mass | Equal pads, balanced copper on both ends |
| **Lifted components** | Fiducial registration failure | Minimum 3 fiducials, 0.100" diameter, clear clearance zone |
| **Cracked board edge** | Trace routed too close to edge | Maintain 0.050" min from V-score or routing line |
| **Warping/Bow** | Unbalanced copper, improper layer stackup | Aim for 40-60% copper balance, symmetric stackup |

### Electrical Issues (Cause Functional Failures)

| Issue | Cause | Prevention |
|-------|-------|-----------|
| **Signal integrity loss** | Long traces without impedance control | Use layer 2 (ground plane) for return paths, minimize loop area |
| **Crosstalk between nets** | Tight spacing on adjacent traces | Increase spacing (rule of thumb: 3× trace width minimum) |
| **Ground plane noise** | Segmented ground, high inductance returns | Solid ground plane, multiple via stitching (5-10 vias per IC pin) |
| **Power distribution noise** | Insufficient power delivery, long traces | Star point connection, local decoupling capacitors near ICs |

---

## 10. DESIGN RULE CHECK (DRC) CHECKLIST

Run these checks before submitting to fabrication:

### Trace & Via Rules
- [ ] Min trace width ≥ 6 mil (or fab minimum)
- [ ] Min trace spacing ≥ 6 mil (or fab minimum)
- [ ] Min annular ring ≥ 4 mil (external), 3 mil (internal, class 2)
- [ ] Min via diameter ≥ 8 mil (12 mil standard recommended)
- [ ] Min aspect ratio ≤ 10:1 for through vias
- [ ] Via-to-via spacing ≥ 20 mil (center-to-center)
- [ ] Via-to-trace spacing ≥ 8 mil

### Pad & Footprint Rules
- [ ] All pads ≥ 15 mil minimum size
- [ ] Pad-to-pad spacing ≥ 4 mil (6-8 mil recommended)
- [ ] Pad-to-board-edge clearance ≥ 40 mil (50 mil recommended)
- [ ] Symmetric footprints for small passives (0402, 0603)
- [ ] Component keepout zone: ≥ 100 mil from board edge

### Plane & Layer Rules
- [ ] Copper density 40-60% per layer
- [ ] Ground plane continuity (check for segmentation)
- [ ] Power plane islands isolated properly (check for bridges)
- [ ] No floating copper (all copper connected or removed)
- [ ] Layer stackup matches fabrication capabilities

### Assembly Rules
- [ ] Minimum 3 global fiducials, ≥ 0.050" diameter
- [ ] Fiducial clearance zone ≥ 0.100" radius
- [ ] No components on fiducials
- [ ] Silkscreen not over pads (≥ 0.010" clearance)
- [ ] Silkscreen not over vias (≥ 0.020" clearance)
- [ ] Reference designators readable (height ≥ 0.025")

### Edge & Panelization Rules
- [ ] Trace clearance from board edge ≥ 50 mil
- [ ] Via clearance from board edge ≥ 50 mil
- [ ] V-score lines clearly marked
- [ ] Tab width documented (100-200 mil)
- [ ] If panelized: boards centered in panel, ≥ 100 mil from panel edge

### Solder Mask Rules
- [ ] Mask web between pads ≥ 4 mil (10 mil recommended)
- [ ] Via tenting specified (tented/untented)
- [ ] If tented: all vias properly masked
- [ ] If untented: solder mask clearance specified (4-10 mil)

### File Integrity
- [ ] Gerber files generated from latest PCB design
- [ ] All layers present (top, bottom, inner, mask, silkscreen, drill)
- [ ] Drill file (Excellon or PDF) matches via/pad locations
- [ ] No duplicate geometry between layers
- [ ] File naming follows standard convention (e.g., `gerber/board.GBL`, `board.GTL`)
- [ ] Fabrication notes include: layer count, thickness, copper weight, board material (FR-4), surface finish

---

## 11. FABRICATION NOTES TEMPLATE

Include these notes in your PCB order/documentation:

```
FABRICATION SPECIFICATIONS
==========================

Board Material: FR-4, IPC-4101 Class 104/116
Board Thickness: 1.6 mm ± 0.1 mm
Copper Weight: 1 oz (35 µm) outer, 0.5 oz (17.5 µm) inner layers
Surface Finish: HASL, ENIG, or Immersion Tin (specify)
Solder Mask: Liquid photo-imageable, green (color optional)
Silkscreen: White epoxy ink, top and bottom
Min Trace Width: 6 mil (0.15 mm)
Min Trace Spacing: 6 mil (0.15 mm)
Min Annular Ring: 4 mil (0.10 mm) external, 3 mil internal
IPC Class: Class 2 (standard) or Class 3 (high-reliability)

VIA SPECIFICATIONS
==================
Through-hole vias: 0.012" hole, 0.024" pad (12/24 mil standard)
Min via spacing: 0.020" center-to-center (20 mil)
Via tenting: [Specify "tented" or "untented both sides"]
Via-in-pad: [If used, state "conductive filled" or "solder filled"]

SPECIAL NOTES
=============
- Fiducials: 3 global fiducials, 0.050" diameter, copper
- Panelization: [Specify if panel required, dimensions, tabs]
- Depanelization: V-Score / Router / Tab Break (specify method)
- Non-functional copper: [Yes / No] (copper pour for balance)
- Thermal relief spokes: [Specify if custom geometry required]
```

---

## 12. REFERENCE: IPC STANDARDS

| Standard | Description |
|----------|-------------|
| **IPC-2221** | Generic standard for PCB design |
| **IPC-6012** | Acceptability of circuit boards |
| **IPC-A-600** | Acceptability of assemblies |
| **IPC-6010** | Laminate design, material specification |
| **IPC-2152** | High-current PCB design guidelines |
| **IPC-D-325** | Design guidelines for high-speed digital layout |
| **IPC-2581** | PCB design data format (CAM data) |

**Common IPC Classes**:
- **Class 1**: General electronics (consumer)
- **Class 2**: Dedicated service (commercial, industrial)
- **Class 3**: High-reliability (aerospace, medical, military)

---

## Quick Reference Summary

### "Safe Default" Design Rules for 2-4 Layer Boards

```
TRACES:        6/6 mil (width/spacing)
VIAS:          12/24 mil (hole/pad), 8:1 aspect ratio max
ANNULAR RING:  4-5 mil (minimum 3 mil class 2, 2 mil class 3)
PADS:          0.020"+ minimum, symmetric for passives
THERMAL RELIEF: 4 spokes, 0.010"-0.020" wide each
FIDUCIALS:     0.050" diameter, 3 minimum, 0.100" clearance zone
EDGE CLEARANCE: 0.050" from traces/vias to board edge
COPPER DENSITY: 40-60% per layer (aim for balance)
SOLDER MASK:   0.004"-0.010" web between pads
SILKSCREEN:    0.010" minimum line width, avoid pads/vias
```

Use these defaults and only deviate with fabricator approval.

---

## Sources

- [Annular Ring Explained by Sierra Circuits](https://www.protoexpress.com/blog/dont-let-annular-rings-drive-you-crazy/)
- [PCB Design Guidelines for DFM - AdvancedPCB](https://www.advancedpcb.com/en-us/resources/blog/pcb-design-guidelines-for-dfm/)
- [PCB Minimum Annular Ring - Cadence](https://resources.pcb.cadence.com/manufacturability/2023-pcb-minimum-annular-ring-formula-and-guidelines)
- [PCB Assembly Design Guide 2025 - NextPCB](https://www.nextpcb.com/blog/pcb-assembly-design-guide)
- [Design for Assembly (DFA) in PCBs - HyePeak](https://hyepeak.com/blog/design-for-assembly/)
- [PCB Via Tenting Design Rules - Sierra Circuits](https://www.protoexpress.com/kb/pcb-via-tenting-design-rules-and-fabrication-notes/)
- [PCB Via Design Guide 2025 - FastTurnPCBs](https://www.fastturnpcbs.com/blog/pcb-via-guide/)
- [Thermal Relief Guidelines - Cadence](https://resources.pcb.cadence.com/blog/2021-pcb-thermal-relief-guidelines-for-effective-layouts/)
- [DFM Issues to Check Before Manufacturing - Sierra Circuits](https://www.protoexpress.com/blog/dfm-issues-pcb-manufacturing/)
- [PCB Trace Width and Spacing - EPC Tec](https://blog.epectec.com/pcb-trace-width-and-spacing-calculations-and-real-world-applications/)
- [Rigid PCB DFM Guidelines - 7PCB](https://www.7pcb.com/Upload_file/DFM_Guidelines.pdf)
- [Power Plane and Ground Plane Best Practices - Cadence](https://resources.pcb.cadence.com/blog/2024-power-plane-and-ground-pane-pcb-design-best-practices/)
- [PCB Ground Plane Guide - JHDPCB](https://jhdpcb.com/blog/pcb-ground-plane-guide/)
