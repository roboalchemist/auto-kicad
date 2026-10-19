"""
DRC rules engine matching KiCad .kicad_dru format.

Implements JLCPCB manufacturing capabilities as Python checks,
run against the BoardLayout + pcbnew footprint data.

Based on: https://github.com/labtroll/KiCad-DesignRules/blob/main/JLCPCB/JLCPCB.kicad_dru
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


RULES_DIR = ".agents/rules"

# Maps rule name → (rule file, section heading) for citation in reports
RULE_REFS: dict[str, tuple[str, str]] = {
    "Track width outer layer":       ("pcb-dfm.md", "Trace & Space"),
    "Track width inner layer":       ("pcb-dfm.md", "Trace & Space"),
    "Hole diameter min":             ("pcb-dfm.md", "Vias"),
    "Hole diameter max":             ("pcb-dfm.md", "Vias"),
    "Annular ring width":            ("pcb-dfm.md", "Vias"),
    "Pad/via to pad/via clearance":  ("pcb-dfm.md", "Trace & Space"),
    "Via to pad clearance":          ("pcb-dfm.md", "Vias"),
    "Edge to track clearance":       ("pcb-mechanical.md", "Board Outline"),
    "Edge to via clearance":         ("pcb-mechanical.md", "Board Outline"),
    "Track crossing (short circuit)": ("pcb-routing.md", "Signal Integrity"),
    "Silkscreen text height":        ("pcb-silkscreen.md", "Text Sizing"),
    "Silkscreen text thickness":     ("pcb-silkscreen.md", "Text Sizing"),
    "Pad to silkscreen clearance":   ("pcb-silkscreen.md", "Clearance Rules"),
    "Silkscreen overlap":            ("pcb-silkscreen.md", "Placement Rules"),
    "Pad to board edge clearance":   ("pcb-mechanical.md", "Board Outline"),
    "90-degree bend":                ("pcb-routing.md", "Trace Geometry"),
    "Tombstoning risk":              ("pcb-dfm.md", "Tombstoning Prevention (0402/0603)"),
    "Return via proximity":          ("pcb-emc.md", "Via Stitching"),
    "Decoupling cap missing":        ("pcb-power.md", "Decoupling Strategy (3-stage)"),
    "Decoupling cap too far":        ("pcb-power.md", "Decoupling Strategy (3-stage)"),
    "Copper balance":                ("pcb-copper-pours.md", "Copper Balance"),
    "Missing fiducials":             ("pcb-dfm.md", "Pick-and-Place"),
    "Missing test points":           ("pcb-test-debug.md", "Test Points"),
    "Insufficient test points":      ("pcb-test-debug.md", "Test Points"),
    "Hole-to-hole (different net)":  ("pcb-dfm.md", "Vias"),
    "Hole-to-hole (same net)":       ("pcb-dfm.md", "Vias"),
    "No power connector":            ("pcb-placement.md", "Priority Order"),
    "No corner radii":               ("pcb-mechanical.md", "Board Outline"),
    "Board too small":               ("pcb-mechanical.md", "Board Outline"),
    "No mounting holes":             ("pcb-mechanical.md", "Mounting Holes"),
    "Bypass cap too far from IC pin": ("pcb-placement.md", "Priority Order"),
    "Acute angle":                   ("pcb-routing.md", "Trace Geometry"),
    "Track to pad clearance":        ("pcb-dfm.md", "Trace & Space"),
    "Asymmetric dead space":         ("pcb-placement.md", "Spacing"),
}


@dataclass
class DRCViolation:
    rule: str
    severity: str  # "error" or "warning"
    message: str
    x: float = 0.0
    y: float = 0.0
    items: list = field(default_factory=list)

    @property
    def rule_ref(self) -> str:
        """Return a citation string like 'pcb-dfm.md > Tombstoning Prevention'."""
        ref = RULE_REFS.get(self.rule)
        if ref:
            return f"{RULES_DIR}/{ref[0]} > {ref[1]}"
        return ""


# ── JLCPCB Design Rules (from .kicad_dru) ────────────────────────────────

RULES = {
    # Track width
    "track_width_outer_min": 0.127,      # mm, outer layers, 1oz copper
    "track_width_inner_min": 0.09,       # mm, inner layers

    # Track spacing (track-to-track, same layer, different nets)
    "track_spacing_outer_min": 0.127,    # mm
    "track_spacing_inner_min": 0.09,     # mm

    # Via / hole
    "hole_diameter_min": 0.2,            # mm, all holes
    "hole_diameter_max": 6.3,            # mm
    "hole_npth_min": 0.5,               # mm, non-plated
    "via_annular_ring_min": 0.075,       # mm

    # Clearances
    "pad_to_pad_min": 0.127,             # mm, different nets, plated
    "track_to_pad_min": 0.2,             # mm, different nets
    "track_to_npth_min": 0.254,          # mm, perimeter
    "track_to_pth_min": 0.33,            # mm, perimeter
    "hole_to_hole_diff_net_min": 0.5,    # mm, perimeter
    "hole_to_hole_same_net_min": 0.254,  # mm, perimeter
    "edge_clearance_min": 0.3,           # mm, routed edge to track

    # Silkscreen
    "silk_text_thickness_min": 0.15,     # mm
    "silk_text_height_min": 1.0,         # mm (we relaxed to 0.8 for compact boards)
    "pad_to_silk_min": 0.15,             # mm
}


def run_drc(render_data_path: str, pcbnew_module=None) -> list[DRCViolation]:
    """Run JLCPCB DRC rules against a board defined by render_data.json.

    Uses pcbnew to load the board's footprints for accurate pad geometry, so it
    must run under KiCad's Python. A relative `footprint_dir` is resolved
    against the JSON file's directory.

    Args:
        render_data_path: Path to render_data.json
        pcbnew_module: Optional pcbnew module (auto-imported if None)

    Returns:
        List of DRCViolation objects

    Raises:
        RuntimeError: pcbnew can't be imported (not running under KiCad's Python)
        FileNotFoundError: footprint_dir or a component's footprint is missing
    """
    data = json.loads(Path(render_data_path).read_text())
    violations = []

    # Load pad geometry via pcbnew
    pads, silk_items = _load_pads_and_silk(
        data, pcbnew_module, base_dir=Path(render_data_path).resolve().parent
    )
    tracks = data.get("tracks", [])
    vias = data.get("vias", [])
    outline = data.get("outline")
    nets = data.get("nets", {})

    # Reverse net ID → name lookup
    net_id_to_name = {v: k for k, v in nets.items()}

    # ── Track width checks ────────────────────────────────────────────
    for track in tracks:
        w = track.get("width", 0.25)
        layer = track.get("layer", "F.Cu")
        is_inner = layer not in ("F.Cu", "B.Cu")
        min_w = RULES["track_width_inner_min"] if is_inner else RULES["track_width_outer_min"]
        if w < min_w:
            pts = track["points"]
            violations.append(DRCViolation(
                rule=f"Track width {'inner' if is_inner else 'outer'} layer",
                severity="error",
                message=f"Track width {w:.3f}mm < {min_w}mm minimum",
                x=pts[0][0], y=pts[0][1],
            ))

    # ── Via / hole checks ─────────────────────────────────────────────
    for v in vias:
        drill = v.get("drill", 0.3)
        via_size = 0.6  # default via outer diameter
        annular = (via_size - drill) / 2

        if drill < RULES["hole_diameter_min"]:
            violations.append(DRCViolation(
                rule="Hole diameter min",
                severity="error",
                message=f"Via drill {drill}mm < {RULES['hole_diameter_min']}mm",
                x=v["x"], y=v["y"],
            ))
        if drill > RULES["hole_diameter_max"]:
            violations.append(DRCViolation(
                rule="Hole diameter max",
                severity="error",
                message=f"Via drill {drill}mm > {RULES['hole_diameter_max']}mm",
                x=v["x"], y=v["y"],
            ))
        if annular < RULES["via_annular_ring_min"]:
            violations.append(DRCViolation(
                rule="Annular ring width",
                severity="error",
                message=f"Via annular ring {annular:.3f}mm < {RULES['via_annular_ring_min']}mm",
                x=v["x"], y=v["y"],
            ))

    # ── Pad-to-pad clearance (different nets) ─────────────────────────
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            p1, p2 = pads[i], pads[j]
            if p1["ref"] == p2["ref"]:
                continue  # same component
            if p1.get("net") and p2.get("net") and p1["net"] == p2["net"]:
                continue  # same net
            if not (p1["through"] or p2["through"] or set(p1["layers"]) & set(p2["layers"])):
                continue  # SMD pads on opposite sides

            gap_x = abs(p1["x"] - p2["x"]) - (p1["sx"] / 2 + p2["sx"] / 2)
            gap_y = abs(p1["y"] - p2["y"]) - (p1["sy"] / 2 + p2["sy"] / 2)

            if gap_x < 0 and gap_y < 0:
                # Actual overlap
                violations.append(DRCViolation(
                    rule="Pad/via to pad/via clearance",
                    severity="error",
                    message=f"{p1['ref']}.{p1['pad']} overlaps {p2['ref']}.{p2['pad']} "
                            f"(gap: {max(gap_x, gap_y):.2f}mm)",
                    x=(p1["x"] + p2["x"]) / 2,
                    y=(p1["y"] + p2["y"]) / 2,
                    items=[f"{p1['ref']}.{p1['pad']}", f"{p2['ref']}.{p2['pad']}"],
                ))
            elif gap_x < RULES["pad_to_pad_min"] and gap_y < RULES["pad_to_pad_min"]:
                gap = max(gap_x, gap_y)
                if gap < RULES["pad_to_pad_min"]:
                    violations.append(DRCViolation(
                        rule="Pad/via to pad/via clearance",
                        severity="error",
                        message=f"{p1['ref']}.{p1['pad']} to {p2['ref']}.{p2['pad']}: "
                                f"clearance {gap:.3f}mm < {RULES['pad_to_pad_min']}mm",
                        x=(p1["x"] + p2["x"]) / 2,
                        y=(p1["y"] + p2["y"]) / 2,
                        items=[f"{p1['ref']}.{p1['pad']}", f"{p2['ref']}.{p2['pad']}"],
                    ))

    # ── Via-to-pad clearance ──────────────────────────────────────────
    via_outer_r = 0.3  # 0.6mm diameter / 2
    for v in vias:
        vx, vy = v["x"], v["y"]
        v_net = net_id_to_name.get(v.get("net"), "")
        for p in pads:
            if p.get("net") and p["net"] == v_net:
                continue  # same net OK
            dx = max(0, abs(vx - p["x"]) - p["sx"] / 2)
            dy = max(0, abs(vy - p["y"]) - p["sy"] / 2)
            gap = math.hypot(dx, dy) - via_outer_r
            if gap < RULES["pad_to_pad_min"]:
                violations.append(DRCViolation(
                    rule="Via to pad clearance",
                    severity="error",
                    message=f"Via({vx:.1f},{vy:.1f}) to {p['ref']}.{p['pad']}: "
                            f"clearance {gap:.3f}mm < {RULES['pad_to_pad_min']}mm",
                    x=vx, y=vy,
                    items=[f"via@({vx},{vy})", f"{p['ref']}.{p['pad']}"],
                ))

    # ── Via-to-via clearance (hole-to-hole) ───────────────────────────
    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            v1, v2 = vias[i], vias[j]
            dist = math.hypot(v1["x"] - v2["x"], v1["y"] - v2["y"])
            drill1 = v1.get("drill", 0.3) / 2
            drill2 = v2.get("drill", 0.3) / 2
            edge_gap = dist - drill1 - drill2

            v1_net = net_id_to_name.get(v1.get("net"), "")
            v2_net = net_id_to_name.get(v2.get("net"), "")
            same_net = v1_net and v2_net and v1_net == v2_net
            min_gap = RULES["hole_to_hole_same_net_min"] if same_net else RULES["hole_to_hole_diff_net_min"]

            if edge_gap < min_gap:
                violations.append(DRCViolation(
                    rule=f"Hole-to-hole ({'same' if same_net else 'different'} net)",
                    severity="error",
                    message=f"Via-to-via gap {edge_gap:.3f}mm < {min_gap}mm (via@{v1['x']:.1f},{v1['y']:.1f} via@{v2['x']:.1f},{v2['y']:.1f})",
                    x=(v1["x"] + v2["x"]) / 2,
                    y=(v1["y"] + v2["y"]) / 2,
                ))

    # ── Edge clearance ────────────────────────────────────────────────
    if outline:
        bw, bh = outline
        for track in tracks:
            for pt in track["points"]:
                x, y = pt
                edge_dist = min(x, y, bw - x, bh - y)
                if edge_dist < RULES["edge_clearance_min"]:
                    violations.append(DRCViolation(
                        rule="Edge to track clearance",
                        severity="error",
                        message=f"Track at ({x:.1f},{y:.1f}) is {edge_dist:.2f}mm from board edge "
                                f"(min {RULES['edge_clearance_min']}mm)",
                        x=x, y=y,
                    ))
        for v in vias:
            edge_dist = min(v["x"], v["y"], bw - v["x"], bh - v["y"])
            if edge_dist < RULES["edge_clearance_min"]:
                violations.append(DRCViolation(
                    rule="Edge to via clearance",
                    severity="error",
                    message=f"Via at ({v['x']:.1f},{v['y']:.1f}) is {edge_dist:.2f}mm from edge",
                    x=v["x"], y=v["y"],
                ))

    # ── Track-to-track crossings (different nets, same layer) ─────────
    segments = []
    for track in tracks:
        pts = track["points"]
        net = track.get("net", "")
        layer = track.get("layer", "F.Cu")
        for k in range(len(pts) - 1):
            segments.append((pts[k][0], pts[k][1], pts[k+1][0], pts[k+1][1],
                             net, track.get("net_name", net_id_to_name.get(net, "")), layer))

    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            s1, s2 = segments[i], segments[j]
            if s1[4] == s2[4]:
                continue  # same net
            if s1[6] != s2[6]:
                continue  # different layers
            pt = _segments_intersect(*s1[:4], *s2[:4])
            if pt:
                violations.append(DRCViolation(
                    rule="Track crossing (short circuit)",
                    severity="error",
                    message=f"{s1[5]} and {s2[5]} cross at ({pt[0]:.2f},{pt[1]:.2f}) on {s1[6]}",
                    x=pt[0], y=pt[1],
                    items=[s1[5], s2[5]],
                ))

    # ── Silkscreen checks ────────────────────────────────────────────
    if silk_items:
        # 1. Silkscreen text height and thickness
        for s in silk_items:
            if s["height"] < RULES["silk_text_height_min"]:
                violations.append(DRCViolation(
                    rule="Silkscreen text height",
                    severity="warning",
                    message=f"{s['ref']} text height {s['height']:.2f}mm < {RULES['silk_text_height_min']}mm",
                    x=s["x"], y=s["y"],
                ))
            if s["thickness"] < RULES["silk_text_thickness_min"]:
                violations.append(DRCViolation(
                    rule="Silkscreen text thickness",
                    severity="warning",
                    message=f"{s['ref']} text thickness {s['thickness']:.2f}mm < {RULES['silk_text_thickness_min']}mm",
                    x=s["x"], y=s["y"],
                ))

        # 2. Silkscreen to pad clearance (includes own component pads —
        #    per silkscreen.md: "Never place silkscreen over pads")
        for s in silk_items:
            for p in pads:
                # Check if silk bbox overlaps pad bbox with clearance
                gap_x = abs(s["x"] - p["x"]) - (s["bbox_w"] / 2 + p["sx"] / 2 + RULES["pad_to_silk_min"])
                gap_y = abs(s["y"] - p["y"]) - (s["bbox_h"] / 2 + p["sy"] / 2 + RULES["pad_to_silk_min"])
                if gap_x < 0 and gap_y < 0:
                    violations.append(DRCViolation(
                        rule="Pad to silkscreen clearance",
                        severity="error",
                        message=f"{s['ref']} silkscreen overlaps {p['ref']}.{p['pad']} pad",
                        x=s["x"], y=s["y"],
                        items=[s["ref"], f"{p['ref']}.{p['pad']}"],
                    ))

        # 3. Silkscreen to silkscreen overlap
        for i in range(len(silk_items)):
            for j in range(i + 1, len(silk_items)):
                s1, s2 = silk_items[i], silk_items[j]
                gap_x = abs(s1["x"] - s2["x"]) - (s1["bbox_w"] / 2 + s2["bbox_w"] / 2)
                gap_y = abs(s1["y"] - s2["y"]) - (s1["bbox_h"] / 2 + s2["bbox_h"] / 2)
                if gap_x < 0 and gap_y < 0:
                    violations.append(DRCViolation(
                        rule="Silkscreen overlap",
                        severity="warning",
                        message=f"{s1['ref']} and {s2['ref']} silkscreen text overlap "
                                f"(gap: {max(gap_x, gap_y):.2f}mm)",
                        x=(s1["x"] + s2["x"]) / 2,
                        y=(s1["y"] + s2["y"]) / 2,
                        items=[s1["ref"], s2["ref"]],
                    ))

    # ── Pad edge clearance (pads too close to board edge) ────────────
    if outline:
        bw, bh = outline
        for p in pads:
            edge_dist = min(
                p["x"] - p["sx"] / 2,          # left
                p["y"] - p["sy"] / 2,          # top
                bw - (p["x"] + p["sx"] / 2),   # right
                bh - (p["y"] + p["sy"] / 2),   # bottom
            )
            if edge_dist < 2.0:
                violations.append(DRCViolation(
                    rule="Pad to board edge clearance",
                    severity="error",
                    message=f"{p['ref']}.{p['pad']} pad edge is {edge_dist:.1f}mm from board edge (min 2mm)",
                    x=p["x"], y=p["y"],
                ))

    # ── 90-degree bend detection ──────────────────────────────────────
    for track in tracks:
        pts = track["points"]
        for k in range(len(pts) - 2):
            x1, y1 = pts[k]
            x2, y2 = pts[k + 1]
            x3, y3 = pts[k + 2]
            a1 = math.atan2(y2 - y1, x2 - x1)
            a2 = math.atan2(y3 - y2, x3 - x2)
            angle_diff = abs(math.degrees(a2 - a1))
            # Normalize to 0-180
            angle_diff = angle_diff % 360
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            # Flag 90° bends (85-95° range)
            if 85 < angle_diff < 95:
                raw_net = track.get("net", "")
                net_name = net_id_to_name.get(raw_net, raw_net) if isinstance(raw_net, int) else (raw_net or track.get("net_name", "?"))
                violations.append(DRCViolation(
                    rule="90-degree bend",
                    severity="warning",
                    message=f"{net_name} has {angle_diff:.0f}-degree bend at ({x2:.1f},{y2:.1f}) on {track['layer']}",
                    x=x2, y=y2,
                ))

    # ── Tombstoning risk (asymmetric trace widths on 2-pad components) ─
    # Group pads by component
    comp_pads: dict[str, list[dict]] = {}
    for p in pads:
        comp_pads.setdefault(p["ref"], []).append(p)
    for ref, cp in comp_pads.items():
        if len(cp) != 2:
            continue  # only check 2-pad passives
        # Find traces connecting to each pad
        widths = [[], []]
        for i, pad_info in enumerate(cp):
            px, py = pad_info["x"], pad_info["y"]
            for track in tracks:
                tw = track.get("width", 0.25)
                for pt in track["points"]:
                    if abs(pt[0] - px) < 0.5 and abs(pt[1] - py) < 0.5:
                        widths[i].append(tw)
                        break
        w0 = max(widths[0]) if widths[0] else 0
        w1 = max(widths[1]) if widths[1] else 0
        if w0 > 0 and w1 > 0 and max(w0, w1) / min(w0, w1) > 1.5:
            violations.append(DRCViolation(
                rule="Tombstoning risk",
                severity="warning",
                message=f"{ref}: asymmetric trace widths ({w0}mm vs {w1}mm) — thermal imbalance",
                x=(cp[0]["x"] + cp[1]["x"]) / 2,
                y=(cp[0]["y"] + cp[1]["y"]) / 2,
            ))

    # ── Return via proximity (signal vias should have nearby GND via) ─
    # Via net can be stored as string name or int ID — normalize to string
    def _via_net_name(v):
        n = v.get("net", "")
        if isinstance(n, int):
            return net_id_to_name.get(n, "")
        return str(n)

    power_names = {"GND", "VCC"}
    signal_vias = [v for v in vias if _via_net_name(v) not in power_names]
    gnd_vias = [v for v in vias if _via_net_name(v) == "GND"]

    for v in signal_vias:
        min_dist = float("inf")
        for gv in gnd_vias:
            d = math.hypot(v["x"] - gv["x"], v["y"] - gv["y"])
            min_dist = min(min_dist, d)
        if min_dist > 2.0:
            vn = _via_net_name(v)
            violations.append(DRCViolation(
                rule="Return via proximity",
                severity="warning",
                message=f"{vn} via at ({v['x']:.1f},{v['y']:.1f}) — nearest GND via is {min_dist:.1f}mm away (want <2mm)",
                x=v["x"], y=v["y"],
            ))

    # ── Decoupling cap distance check ─────────────────────────────────
    # Check that every IC power pin has a capacitor within 5mm on the same net
    components = data.get("components", [])
    ic_refs = [c["ref"] for c in components
               if any(k in c["footprint"] for k in ("SOIC", "QFP", "BGA", "LQFP", "QFN", "TSSOP", "DIP"))]
    cap_refs = [c["ref"] for c in components
                if c.get("ref", "").startswith("C") or "cap" in c["footprint"].lower()]
    if ic_refs and cap_refs:
        # Find IC power pads (VCC/GND) — these MUST have bypass caps
        power_nets = {"VCC", "GND"}
        ic_power_pads = [p for p in pads if p["ref"] in ic_refs and p.get("net") in power_nets]
        # Build cap pad lookup by net (all nets, not just power)
        cap_pads_by_net: dict[str, list[dict]] = {}
        for p in pads:
            if p["ref"] in cap_refs and p.get("net"):
                cap_pads_by_net.setdefault(p["net"], []).append(p)

        for ip in ic_power_pads:
            net = ip.get("net", "")
            caps_on_net = cap_pads_by_net.get(net, [])
            if not caps_on_net:
                violations.append(DRCViolation(
                    rule="Decoupling cap missing",
                    severity="error",
                    message=f"No decoupling cap on {net} net near {ip['ref']}.{ip['pad']}",
                    x=ip["x"], y=ip["y"],
                ))
            else:
                min_dist = min(math.hypot(ip["x"] - cp["x"], ip["y"] - cp["y"]) for cp in caps_on_net)
                if min_dist > 5.0:
                    violations.append(DRCViolation(
                        rule="Decoupling cap too far",
                        severity="warning",
                        message=f"Nearest cap on {net} is {min_dist:.1f}mm from {ip['ref']}.{ip['pad']} (max 5mm)",
                        x=ip["x"], y=ip["y"],
                    ))

        # Also check: every IC pin that has a cap on its net — is cap within 5mm?
        # This catches bypass caps like C2 on CONTROL pin 5
        for ip in pads:
            if ip["ref"] not in ic_refs:
                continue
            net = ip.get("net", "")
            if not net or net in power_nets:
                continue  # already checked above
            caps_on_net = cap_pads_by_net.get(net, [])
            if caps_on_net:
                min_dist = min(math.hypot(ip["x"] - cp["x"], ip["y"] - cp["y"]) for cp in caps_on_net)
                if min_dist > 5.0:
                    violations.append(DRCViolation(
                        rule="Bypass cap too far from IC pin",
                        severity="warning",
                        message=f"Cap on {net} is {min_dist:.1f}mm from {ip['ref']}.{ip['pad']} (max 5mm)",
                        x=ip["x"], y=ip["y"],
                    ))

    # ── Copper balance estimate ───────────────────────────────────────
    if outline:
        bw, bh = outline
        board_area = bw * bh
        layer_copper: dict[str, float] = {}
        for track in tracks:
            layer = track.get("layer", "F.Cu")
            pts = track["points"]
            for k in range(len(pts) - 1):
                seg_len = math.hypot(pts[k+1][0] - pts[k][0], pts[k+1][1] - pts[k][1])
                copper = seg_len * track.get("width", 0.25)
                layer_copper[layer] = layer_copper.get(layer, 0) + copper
        # Add pad areas (rough estimate: count pads * avg pad area)
        avg_pad_area = 1.1 * 1.4  # 0805 pad size
        for layer in ["F.Cu", "B.Cu"]:
            layer_copper.setdefault(layer, 0)
            layer_copper[layer] += len(pads) * avg_pad_area * (0.7 if layer == "F.Cu" else 0.3)
        for layer, copper_area in layer_copper.items():
            pct = copper_area / board_area
            if pct < 0.20:  # 40% target, warn at 20%
                violations.append(DRCViolation(
                    rule="Copper balance",
                    severity="warning",
                    message=f"{layer} copper density ~{pct:.0%} (target 40-60%, add pour or thieving)",
                ))

    # ── Fiducial check ──────────────────────────────────────────────
    # Per dfm.md: "Place fiducials (3 per board, asymmetric) for machine alignment"
    fiducial_count = sum(
        1 for c in components
        if "fiducial" in c.get("footprint", "").lower()
        or "fiducial" in c.get("ref", "").lower()
        or c.get("ref", "").startswith("FID")
    )
    if fiducial_count < 3:
        violations.append(DRCViolation(
            rule="Missing fiducials",
            severity="warning",
            message=f"Board has {fiducial_count} fiducials (need 3 asymmetric for pick-and-place)",
        ))

    # ── Test point check ─────────────────────────────────────────────
    # Per test-debug.md: test points for key signals (VCC, GND, OUTPUT minimum)
    tp_count = sum(
        1 for c in components
        if c.get("ref", "").startswith("TP")
        or "test" in c.get("footprint", "").lower()
        or "testpoint" in c.get("footprint", "").lower()
    )
    if tp_count == 0:
        violations.append(DRCViolation(
            rule="Missing test points",
            severity="warning",
            message="No test points found — add TP pads for VCC, GND, and key signals for probing",
        ))
    elif tp_count < 3:
        violations.append(DRCViolation(
            rule="Insufficient test points",
            severity="warning",
            message=f"Only {tp_count} test point(s) — recommend at least 3 (VCC, GND, OUTPUT)",
        ))

    # ── Power connector check ───────────────────────────────────────
    # Per placement.md: "Place connectors and mechanical components at board edges"
    has_connector = any(
        c.get("ref", "").startswith("J")
        or c.get("ref", "").startswith("P")
        or any(k in c.get("footprint", "").lower()
               for k in ("connector", "header", "pin_header", "terminal", "usb", "barrel"))
        for c in components
    )
    if not has_connector:
        violations.append(DRCViolation(
            rule="No power connector",
            severity="warning",
            message="No power connector or input header found — add power entry pads (e.g., 2-pin header)",
        ))

    # ── Board outline checks ─────────────────────────────────────────
    if outline:
        bw, bh = outline
        # Minimum board size (JLCPCB: 10x10mm)
        if bw < 10 or bh < 10:
            violations.append(DRCViolation(
                rule="Board too small",
                severity="error",
                message=f"Board {bw}x{bh}mm is below 10x10mm minimum",
            ))

        # Corner radii — we can only check if outline is a simple rectangle
        # (gr_rect = sharp corners). If it were arcs, render_data would show it differently.
        # Since outline is stored as [w, h], it's always a sharp-corner rectangle.
        violations.append(DRCViolation(
            rule="No corner radii",
            severity="warning",
            message=f"Board outline has sharp 90-degree corners — add 0.5-1.0mm radius to reduce stress",
        ))

    # ── Mounting holes check ──────────────────────────────────────────
    has_mounting = any(
        c.get("ref", "").startswith("MH")
        or c.get("ref", "").startswith("H")
        or "mounting" in c.get("footprint", "").lower()
        or "mountinghole" in c.get("footprint", "").lower()
        for c in components
    )
    if not has_mounting:
        violations.append(DRCViolation(
            rule="No mounting holes",
            severity="warning",
            message="No mounting holes found — consider adding M3 holes for mechanical securing",
        ))

    # ── Acute angle detection (<45°) ─────────────────────────────────
    # Per routing.md: "Use 45-degree bends" — angles sharper than 45° create
    # impedance discontinuities and acid traps worse than 90° bends
    for track in tracks:
        pts = track["points"]
        for k in range(len(pts) - 2):
            x1, y1 = pts[k]
            x2, y2 = pts[k + 1]
            x3, y3 = pts[k + 2]
            # Skip zero-length segments
            d1 = math.hypot(x2 - x1, y2 - y1)
            d2 = math.hypot(x3 - x2, y3 - y2)
            if d1 < 0.01 or d2 < 0.01:
                continue
            # Calculate angle between segments using dot product
            v1x, v1y = x2 - x1, y2 - y1
            v2x, v2y = x3 - x2, y3 - y2
            dot = v1x * v2x + v1y * v2y
            cos_angle = dot / (d1 * d2)
            cos_angle = max(-1, min(1, cos_angle))  # clamp for floating point
            angle = math.degrees(math.acos(cos_angle))
            # angle is the turning angle (0° = straight, 180° = U-turn)
            if angle >= 135:  # sharper than 45° (180° - 45° = 135°)
                raw_net = track.get("net", "")
                net_name = net_id_to_name.get(raw_net, raw_net) if isinstance(raw_net, int) else (raw_net or track.get("net_name", "?"))
                violations.append(DRCViolation(
                    rule="Acute angle",
                    severity="warning",
                    message=f"{net_name} has {180 - angle:.0f}° acute angle at ({x2:.1f},{y2:.1f}) on {track['layer']} (min 45°)",
                    x=x2, y=y2,
                ))

    # ── Track-to-pad clearance ────────────────────────────────────────
    # Minimum distance from each track segment to every pad it doesn't connect
    # to on the same copper layer, using the pad's real (rotated) extent.
    min_track_pad = RULES["track_to_pad_min"]  # 0.2mm
    for track in tracks:
        pts = track["points"]
        raw_net = track.get("net", "")
        track_net = net_id_to_name.get(raw_net, raw_net) if isinstance(raw_net, int) else (raw_net or track.get("net_name", ""))
        layer = track.get("layer", "F.Cu")
        tw_half = track.get("width", 0.25) / 2
        for i in range(len(pts) - 1):
            sx, sy = pts[i]
            ex, ey = pts[i + 1]
            if math.hypot(ex - sx, ey - sy) < 0.01:
                continue
            for p in pads:
                # Skip pads on the same net, and SMD pads on the other side
                if p.get("net", "") == track_net and track_net:
                    continue
                if not p["through"] and layer not in p["layers"]:
                    continue
                dist, cx, cy = _seg_rect_distance(
                    sx, sy, ex, ey, p["x"], p["y"], p["sx"] / 2, p["sy"] / 2
                )
                clearance = dist - tw_half
                if clearance < min_track_pad:
                    violations.append(DRCViolation(
                        rule="Track to pad clearance",
                        severity="error" if clearance < 0 else "warning",
                        message=f"Track ({track_net}) to {p['ref']}.{p['pad']}: clearance {clearance:.2f}mm < {min_track_pad}mm at ({cx:.1f},{cy:.1f}) on {layer}",
                        x=cx, y=cy,
                    ))

    # ── Asymmetric dead space ─────────────────────────────────────────
    # Check that margins around components are roughly balanced per edge.
    # A large gap on one side vs a small gap on the other means the board
    # can be shrunk or components should be re-centered.
    if outline and components:
        bw, bh = outline
        xs = [c["x"] for c in components]
        ys = [c["y"] for c in components]
        pad_margin = 2.0  # approximate half-component body size
        left_gap = min(xs) - pad_margin
        right_gap = bw - max(xs) - pad_margin
        top_gap = min(ys) - pad_margin
        bottom_gap = bh - max(ys) - pad_margin
        max_imbalance = 2.0  # mm — flag if one side has 2mm+ more space than opposite
        if right_gap - left_gap >= max_imbalance:
            violations.append(DRCViolation(
                rule="Asymmetric dead space",
                severity="warning",
                message=f"Right margin ({right_gap:.1f}mm) is {right_gap - left_gap:.1f}mm larger than left ({left_gap:.1f}mm) — shift components right or shrink board width",
            ))
        if left_gap - right_gap >= max_imbalance:
            violations.append(DRCViolation(
                rule="Asymmetric dead space",
                severity="warning",
                message=f"Left margin ({left_gap:.1f}mm) is {left_gap - right_gap:.1f}mm larger than right ({right_gap:.1f}mm) — shift components left or shrink board width",
            ))
        if bottom_gap - top_gap >= max_imbalance:
            violations.append(DRCViolation(
                rule="Asymmetric dead space",
                severity="warning",
                message=f"Bottom margin ({bottom_gap:.1f}mm) is {bottom_gap - top_gap:.1f}mm larger than top ({top_gap:.1f}mm) — shift components down or shrink board height",
            ))
        if top_gap - bottom_gap >= max_imbalance:
            violations.append(DRCViolation(
                rule="Asymmetric dead space",
                severity="warning",
                message=f"Top margin ({top_gap:.1f}mm) is {top_gap - bottom_gap:.1f}mm larger than bottom ({bottom_gap:.1f}mm) — shift components up or shrink board height",
            ))

    return violations


def _load_pads_and_silk(
    data: dict, pcbnew_module=None, base_dir: Optional[Path] = None
) -> tuple[list[dict], list[dict]]:
    """Load pad geometry and silkscreen text from the board's footprints via pcbnew.

    Returns (pads, silk_items). Each pad carries its rotated bounding box
    (x, y = centre; sx, sy = size), the outer copper layers it is on, and
    whether it is drilled. Missing pcbnew or footprints raise instead of
    silently producing a board without pads.
    """
    if pcbnew_module is None:
        try:
            import pcbnew as pcbnew_module
        except ImportError:
            raise RuntimeError(
                "pcbnew is not importable; run drc_rules.py with KiCad's bundled Python "
                "(/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/"
                "Versions/Current/bin/python3)"
            ) from None

    fp_dir = data.get("footprint_dir")
    if not fp_dir:
        raise FileNotFoundError("render data has no footprint_dir, so pads can't be loaded")
    fp_path = Path(fp_dir)
    if not fp_path.is_absolute() and base_dir is not None:
        fp_path = base_dir / fp_path
    if not fp_path.is_dir():
        raise FileNotFoundError(f"footprint_dir {fp_dir!r} does not exist (resolved to {fp_path})")

    pads = []
    silk_items = []
    board = pcbnew_module.BOARD()
    missing = []
    for comp in data.get("components", []):
        fp_name = comp["footprint"].split(":")[-1]
        loaded = None
        for c in fp_path.rglob(f"{fp_name}.kicad_mod"):
            try:
                loaded = pcbnew_module.FootprintLoad(str(c.parent), fp_name)
            except Exception:
                loaded = None
            if loaded:
                break
        if not loaded:
            missing.append(f"{comp['ref']} ({fp_name})")
            continue
        loaded.SetReference(comp["ref"])
        loaded.SetPosition(pcbnew_module.VECTOR2I(
            pcbnew_module.FromMM(comp["x"]),
            pcbnew_module.FromMM(comp["y"]),
        ))
        if comp.get("rotation"):
            loaded.SetOrientationDegrees(comp["rotation"])
        board.Add(loaded)
    if missing:
        raise FileNotFoundError(f"footprints not found under {fp_path}: {', '.join(missing)}")

    pad_nets = {}
    for comp in data.get("components", []):
        for pname, nname in comp.get("pad_nets", {}).items():
            pad_nets[(comp["ref"], pname)] = nname

    copper = (("F.Cu", pcbnew_module.F_Cu), ("B.Cu", pcbnew_module.B_Cu))
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            bbox = pad.GetBoundingBox()
            center = bbox.GetCenter()
            pads.append({
                "ref": ref,
                "pad": pad.GetName(),
                "x": pcbnew_module.ToMM(center.x),
                "y": pcbnew_module.ToMM(center.y),
                "sx": pcbnew_module.ToMM(bbox.GetWidth()),
                "sy": pcbnew_module.ToMM(bbox.GetHeight()),
                "layers": [name for name, layer_id in copper if pad.IsOnLayer(layer_id)],
                "through": pad.GetDrillSize().x > 0,
                "net": pad_nets.get((ref, pad.GetName()), ""),
            })
        # Collect silkscreen reference text
        ref_field = fp.Reference()
        if ref_field.IsVisible() and "Silk" in ref_field.GetLayerName():
            pos = ref_field.GetPosition()
            bbox = ref_field.GetBoundingBox()
            bbox_w = pcbnew_module.ToMM(bbox.GetRight() - bbox.GetLeft())
            bbox_h = pcbnew_module.ToMM(bbox.GetBottom() - bbox.GetTop())
            silk_items.append({
                "ref": ref,
                "text": ref_field.GetText(),
                "x": pcbnew_module.ToMM(pos.x),
                "y": pcbnew_module.ToMM(pos.y),
                "bbox_w": bbox_w,
                "bbox_h": bbox_h,
                "height": pcbnew_module.ToMM(ref_field.GetTextSize().y),
                "thickness": pcbnew_module.ToMM(ref_field.GetTextThickness()),
            })

    return pads, silk_items


def _seg_rect_distance(sx, sy, ex, ey, cx, cy, hw, hh):
    """Distance from segment (sx,sy)-(ex,ey) to the axis-aligned rectangle centred
    at (cx,cy) with half-sizes (hw,hh), and the nearest point on the segment.

    Returns (0, x, y) when the segment touches or crosses the rectangle.
    """
    x0, x1, y0, y1 = cx - hw, cx + hw, cy - hh, cy + hh

    def rect_dist(px, py):
        return math.hypot(max(x0 - px, 0.0, px - x1), max(y0 - py, 0.0, py - y1))

    def seg_point(px, py):
        vx, vy = ex - sx, ey - sy
        length2 = vx * vx + vy * vy
        t = max(0.0, min(1.0, ((px - sx) * vx + (py - sy) * vy) / length2)) if length2 else 0.0
        return sx + t * vx, sy + t * vy

    for px, py in ((sx, sy), (ex, ey)):
        if rect_dist(px, py) == 0:
            return 0.0, px, py
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    for k in range(4):
        hit = _segments_intersect(sx, sy, ex, ey, *corners[k], *corners[(k + 1) % 4])
        if hit:
            return 0.0, hit[0], hit[1]
    # No overlap: the minimum is at a segment end or a rectangle corner
    best = min((rect_dist(sx, sy), sx, sy), (rect_dist(ex, ey), ex, ey))
    for qx, qy in corners:
        px, py = seg_point(qx, qy)
        d = math.hypot(qx - px, qy - py)
        if d < best[0]:
            best = (d, px, py)
    return best


def _segments_intersect(x1a, y1a, x1b, y1b, x2a, y2a, x2b, y2b):
    """Check if two line segments intersect. Returns intersection point or None."""
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

    d1 = cross(x2a, y2a, x2b, y2b, x1a, y1a)
    d2 = cross(x2a, y2a, x2b, y2b, x1b, y1b)
    d3 = cross(x1a, y1a, x1b, y1b, x2a, y2a)
    d4 = cross(x1a, y1a, x1b, y1b, x2b, y2b)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        t = d1 / (d1 - d2)
        return (x1a + t * (x1b - x1a), y1a + t * (y1b - y1a))

    def on_segment(px, py, ax, ay, bx, by):
        return (min(ax, bx) - 0.001 <= px <= max(ax, bx) + 0.001 and
                min(ay, by) - 0.001 <= py <= max(ay, by) + 0.001)

    if abs(d1) < 0.001 and on_segment(x1a, y1a, x2a, y2a, x2b, y2b):
        return (x1a, y1a)
    if abs(d2) < 0.001 and on_segment(x1b, y1b, x2a, y2a, x2b, y2b):
        return (x1b, y1b)
    return None


def print_report(violations: list[DRCViolation]):
    """Print a formatted DRC report with rule citations."""
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    if not violations:
        print("DRC: PASS — 0 violations (JLCPCB rules)")
        return

    print(f"DRC: {len(errors)} errors, {len(warnings)} warnings (JLCPCB rules)")
    for v in violations:
        prefix = "ERROR" if v.severity == "error" else "WARN "
        ref = f"  → {v.rule_ref}" if v.rule_ref else ""
        print(f"  [{prefix}] {v.rule}: {v.message}{ref}")


# ── CLI usage ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "render_data_v2.json"
    try:
        violations = run_drc(path)
    except (RuntimeError, FileNotFoundError) as e:
        # Exit 2: the board could not be checked at all (distinct from DRC errors)
        print(f"drc_rules.py: {e}", file=sys.stderr)
        sys.exit(2)
    print_report(violations)
    sys.exit(1 if any(v.severity == "error" for v in violations) else 0)
