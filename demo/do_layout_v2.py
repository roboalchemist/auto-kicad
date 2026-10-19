#!/usr/bin/env python3
"""
555 LED Blinker — Redesigned PCB layout following PCB design rules.

Design philosophy (from .claude/rules/):
  - placement.md: ICs first, decoupling cap right at the power pins, timing
    components adjacent to IC, signal flow left-to-right
  - routing.md: 45-degree bends (no 90°), consistent trace widths, minimize
    vias — every net but one VCC link is routed on F.Cu
  - power.md: wider power traces (0.5mm), bypass cap C3 between pin 8 (VCC)
    and pin 1 (GND), each ~2.6mm away
  - dfm.md: 2mm+ pad-to-edge clearance, 0.2mm+ copper clearance everywhere
  - silkscreen.md: reference text clear of every pad (default footprint
    positions — placement and rotation keep them clear, no post-processing)

Net connectivity:
  VCC:       R1.1, U1.8, U1.4, C3.1
  GND:       C1.2, C2.2, C3.2, D1.1, U1.1
  DISCHARGE: R1.2, R2.1, U1.7
  THRESHOLD: C1.1, R2.2, U1.2, U1.6
  CONTROL:   C2.1, U1.5
  OUTPUT:    R3.1, U1.3
  LED_ANODE: D1.2, R3.2

NE555 SOIC-8 (no rotation), pads 0.59 x 2.05mm on a 1.27mm pitch:
  Bottom row (y=+2.57):  pads 1(GND), 2(TRIG), 3(OUT), 4(RST)
  Top row    (y=-2.57):  pads 8(VCC), 7(DISCH), 6(THRES), 5(CONT)
  The body between the rows (y -1.55..+1.55) is free F.Cu routing space.

2-pad components (R0805, C0805):
  pad 1 at (-1, 0), pad 2 at (+1, 0)
  rotation=90:  pad 1 at (0, +1), pad 2 at (0, -1)
  rotation=180: pad 1 at (+1, 0), pad 2 at (-1, 0)
  rotation=270: pad 1 at (0, -1), pad 2 at (0, +1)
  Reference text sits 3mm from the centre, on the pad-2 side (turns with the part)

LED (LED0805-RD):
  pad 1 (cathode -) at (-1.1, 0), pad 2 (anode +) at (+1.1, 0)
  With rotation=90: pad 1 at (0, +1.1), pad 2 at (0, -1.1)
"""

import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from layout import BoardLayout

KICAD_CLI_PATHS = ["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"]
KICAD_PYTHON = Path(
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
)


def parse_netlist(netlist_path: str) -> dict[str, list[tuple[str, str]]]:
    """Parse netlist to get net -> [(ref, pin), ...] mapping."""
    content = Path(netlist_path).read_text()
    nets = {}
    nets_start = content.find("(nets")
    if nets_start < 0:
        return nets
    nets_section = content[nets_start:]
    i = 0
    while i < len(nets_section):
        net_start = nets_section.find("(net\n", i)
        if net_start < 0:
            net_start = nets_section.find("(net ", i)
        if net_start < 0:
            break
        depth = 0
        j = net_start
        while j < len(nets_section):
            if nets_section[j] == "(":
                depth += 1
            elif nets_section[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        block = nets_section[net_start : j + 1]
        name_match = re.search(r'\(name\s+"([^"]*)"\)', block)
        if name_match:
            net_name = name_match.group(1)
            nodes = re.findall(
                r'\(node\s*\(ref\s+"(\w+)"\)\s*\(pin\s+"(\w+)"\)', block
            )
            nets[net_name] = nodes
        i = j + 1
    return nets


def get_pad_position(board: BoardLayout, ref: str, pad_num: str) -> tuple[float, float]:
    """Get absolute position of a pad on a placed component, accounting for rotation."""
    comp = board._components.get(ref)
    if not comp:
        raise ValueError(f"Component {ref} not found")
    for pad in comp.pads:
        if pad["num"] == pad_num:
            lx, ly = pad["local_x"], pad["local_y"]
            if comp.rotation:
                rad = math.radians(-comp.rotation)
                rx = lx * math.cos(rad) - ly * math.sin(rad)
                ry = lx * math.sin(rad) + ly * math.cos(rad)
                lx, ly = rx, ry
            return (round(comp.x + lx, 3), round(comp.y + ly, 3))
    raise ValueError(f"Pad {pad_num} not found on {ref}")


def route_45deg(x1, y1, x2, y2):
    """Route between two points using 45-degree segments (no 90° bends).

    Per routing.md: "Use 45-degree bends, never 90-degree — reduces reflections
    and acid traps."

    Strategy: vertical-first then 45° diagonal to target.
    """
    dx = x2 - x1
    dy = y2 - y1

    if abs(dx) < 0.1 or abs(dy) < 0.1:
        return [(x1, y1), (x2, y2)]

    # Use 45° dogleg: go partially vertical, then 45° diagonal to target
    adx, ady = abs(dx), abs(dy)
    if ady >= adx:
        # More vertical: go vertical first, then 45° diagonal
        straight = ady - adx
        mid_y = y1 + math.copysign(straight, dy)
        return [(x1, y1), (x1, mid_y), (x2, y2)]
    else:
        # More horizontal: go horizontal first, then 45° diagonal
        straight = adx - ady
        mid_x = x1 + math.copysign(straight, dx)
        return [(x1, y1), (mid_x, y1), (x2, y2)]


def main():
    demo_dir = Path(__file__).parent
    netlist_path = str(demo_dir / "blinker.net")
    output_path = str(demo_dir / "blinker_routed_v2.kicad_pcb")
    fp_dir = str(demo_dir / "libs" / "footprints")

    if not Path(netlist_path).exists():
        sys.exit(f"{netlist_path} not found — run blinker.py first (from demo/)")

    # ══════════════════════════════════════════════════════════════════════════
    # CREATE BOARD — using new_board() so we can add C3 (VCC bypass cap)
    # ══════════════════════════════════════════════════════════════════════════
    components = [
        {"ref": "U1", "value": "NE555DR", "footprint": "SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL"},
        {"ref": "R1", "value": "10K", "footprint": "R0805"},
        {"ref": "R2", "value": "10K", "footprint": "R0805"},
        {"ref": "R3", "value": "470R", "footprint": "R0805"},
        {"ref": "C1", "value": "10uF", "footprint": "C0805"},
        {"ref": "C2", "value": "100nF", "footprint": "C0805"},
        {"ref": "C3", "value": "100nF", "footprint": "C0805"},  # VCC bypass cap
        {"ref": "D1", "value": "RED", "footprint": "LED0805-RD"},
    ]

    print("Creating board with 8 components (including C3 VCC bypass)...")
    board = BoardLayout.new_board(output_path, components, fp_dir)
    print(f"  Components: {[c['ref'] for c in components]}")

    # Parse netlist and extend with C3 (not in blinker.net)
    netlist = parse_netlist(netlist_path)
    netlist.setdefault("VCC", []).append(("C3", "1"))
    netlist.setdefault("GND", []).append(("C3", "2"))
    pad_net_map: dict[str, dict[str, str]] = {}
    for net_name, nodes in netlist.items():
        for ref, pin in nodes:
            pad_net_map.setdefault(ref, {})[pin] = net_name
    board.set_pad_nets(pad_net_map)

    # ══════════════════════════════════════════════════════════════════════════
    # PLACEMENT — Following placement.md rules
    # ══════════════════════════════════════════════════════════════════════════
    #
    # Board: 25mm x 20mm
    #
    # Design rules applied:
    #   1. IC (U1) placed first, center — anchors layout
    #   2. C3 (VCC bypass) between pin 8 (VCC) and pin 1 (GND), ~2.6mm from each
    #   3. C2 (CONTROL bypass) within 3mm of U1 pin 5
    #   4. Timing components (R1, R2, C1) adjacent to IC; R2 and C1 rotated 180°
    #      so their THRESHOLD pads face U1 and every signal routes on F.Cu
    #   5. Signal flow: timing (left/top) → IC → output stage (right)
    #   6. 2mm+ pad-to-edge clearance (drc_rules.py), 3mm+ for most parts
    #   7. Reference text positions checked against every pad

    print("\nPlacing components (PCB design rules applied)...")
    board.set_board_outline(25, 20)

    # U1: NE555 at center, anchors layout
    # Pin positions (with U1 at 9, 10):
    #   Pin 8 (VCC):   (7.095, 7.43)   Pin 7 (DISCH): (8.365, 7.43)
    #   Pin 6 (THRES): (9.635, 7.43)   Pin 5 (CONT):  (10.905, 7.43)
    #   Pin 1 (GND):   (7.095, 12.57)  Pin 2 (TRIG):  (8.365, 12.57)
    #   Pin 3 (OUT):   (9.635, 12.57)  Pin 4 (RST):   (10.905, 12.57)
    board.place_component("U1", 9, 10)

    # C3: VCC bypass, vertical, left of U1: C3.1 (VCC) at (5, 9), C3.2 (GND) at
    # (5, 11). Pins 8 and 1 each reach it with one 45° dogleg (~2.6mm).
    # Its reference text lands below it at (5, 13), clear of U1's pads.
    board.place_component("C3", 5, 10, rotation=270)

    # R1: VCC → DISCHARGE, top-left: R1.1 (VCC) at (3.5, 3), R1.2 at (5.5, 3)
    board.place_component("R1", 4.5, 3, rotation=0)

    # R2: DISCHARGE → THRESHOLD, top-right, rotated 180° so THRESHOLD (R2.2) is
    # at (12, 3), straight up-right from pin 6, and DISCHARGE (R2.1) at (14, 3)
    # is reached over the top. Its text lands at (10, 3), between R1 and R2.
    board.place_component("R2", 13, 3, rotation=180)

    # C2: CONTROL bypass — C2.1 at (12.5, 5) is 2.9mm from U1 pin 5
    board.place_component("C2", 13.5, 5, rotation=0)

    # C1: Timing cap below U1, rotated 180° so THRESHOLD (C1.1) at (10, 16.5)
    # sits under pin 2's path and GND (C1.2) at (8, 16.5) under pin 1's
    board.place_component("C1", 9, 16.5, rotation=180)

    # R3: OUTPUT current limiter — right side
    board.place_component("R3", 17, 12, rotation=0)

    # D1: LED — below R3: pads at (19, 17.1) (cathode, GND) and (19, 14.9)
    # Bottom edge clearance: 20 - 17.6 = 2.4mm
    board.place_component("D1", 19, 16, rotation=90)

    print("Components placed:")
    for c in board.list_components():
        print(f"  {c['ref']:4s} at ({c['x']:5.1f}, {c['y']:5.1f}) rot={c['rotation']}")

    # ══════════════════════════════════════════════════════════════════════════
    # ROUTING — Following routing.md and power.md rules
    # ══════════════════════════════════════════════════════════════════════════
    #
    # Strategy:
    #   - Everything on F.Cu except one B.Cu link from U1.4 (RESET, tied to
    #     VCC) back to the VCC net on the left; 2 vias total
    #   - Signal traces 0.25mm, VCC/GND 0.5mm
    #   - ALL bends are 45°; every track ends on a pad or via centre
    #   - GND reaches C2 and D1 along the board's bottom and right edges

    print("\nRouting tracks (45° bends only)...")

    W_SIG = 0.25    # Signal trace width (mm)
    W_PWR = 0.5     # Power trace width (mm)
    TOP_CHANNEL_Y = 1.5    # DISCHARGE runs above R2 to reach R2.1
    GND_BOTTOM_Y = 18.2    # GND from C1 to D1 along the bottom edge
    GND_RIGHT_X = 21.5     # GND from C2 to D1 along the right edge

    def pad(ref, pin):
        return get_pad_position(board, ref, pin)

    def track(net_name, points, power=False, layer="F.Cu"):
        w = W_PWR if power else W_SIG
        pts = [(round(x, 4), round(y, 4)) for x, y in points]
        board.add_track(net_name, pts, width_mm=w, layer=layer)

    def via(net_name, x, y):
        board.add_via(round(x, 4), round(y, 4), net_name, drill_mm=0.3)

    # Print pad positions for reference
    print("\nPad positions:")
    for net_name, nodes in sorted(netlist.items()):
        positions = []
        for ref, pin in nodes:
            x, y = pad(ref, pin)
            positions.append(f"{ref}.{pin}({x:.1f},{y:.1f})")
        print(f"  {net_name:12s}: {', '.join(positions)}")

    # ── VCC: U1.8 → C3.1 → R1.1 on F.Cu; U1.4 via B.Cu ──────────────────
    u1_8 = pad("U1", "8")
    u1_4 = pad("U1", "4")
    c3_1 = pad("C3", "1")
    r1_1 = pad("R1", "1")

    track("VCC", route_45deg(*u1_8, *c3_1), power=True)       # pin 8 → bypass cap
    v_vcc_left = (c3_1[0], c3_1[1] - 3.0)                     # (5, 6): above C3
    track("VCC", [c3_1, v_vcc_left], power=True)
    via("VCC", *v_vcc_left)
    track("VCC", route_45deg(*v_vcc_left, *r1_1), power=True)  # → R1 (timing)

    # U1.4 (RESET) is boxed in by OUTPUT and the THRESHOLD path through the
    # body, so it reaches VCC on B.Cu: stub right to a via, then one 45° run
    # under U1 to the via above C3.
    v_vcc_right = (u1_4[0] + 1.4, u1_4[1])                    # (12.3, 12.57)
    track("VCC", [u1_4, v_vcc_right], power=True)
    via("VCC", *v_vcc_right)
    track("VCC", route_45deg(*v_vcc_right, *v_vcc_left), power=True, layer="B.Cu")

    # ── GND: U1.1 → C3.2 and C1.2; C1.2 → D1.1 → C2.2 around the edges ───
    u1_1 = pad("U1", "1")
    c1_2 = pad("C1", "2")
    c2_2 = pad("C2", "2")
    c3_2 = pad("C3", "2")
    d1_1 = pad("D1", "1")

    track("GND", route_45deg(*u1_1, *c3_2), power=True)       # pin 1 → bypass cap
    track("GND", route_45deg(*u1_1, *c1_2), power=True)       # pin 1 → timing cap

    # C1.2 → D1.1 along the bottom edge (below C1.1 and the board ID text area)
    track("GND", [
        c1_2,
        (c1_2[0], GND_BOTTOM_Y - 0.8),
        (c1_2[0] + 0.8, GND_BOTTOM_Y),
        (d1_1[0] - (GND_BOTTOM_Y - d1_1[1]), GND_BOTTOM_Y),
        d1_1,
    ], power=True)

    # C2.2 → D1.1 down the right edge, outside R3 and the LED
    y_top = c2_2[1] + 1.0
    track("GND", [
        c2_2,
        (c2_2[0] + 1.0, y_top),
        (GND_RIGHT_X - 1.5, y_top),
        (GND_RIGHT_X, y_top + 1.5),
        (GND_RIGHT_X, d1_1[1] - 1.5),
        (GND_RIGHT_X - 1.5, d1_1[1]),
        d1_1,
    ], power=True)

    # ── DISCHARGE (F.Cu signal) ──────────────────────────────────────────
    u1_7 = pad("U1", "7")
    r1_2 = pad("R1", "2")
    r2_1 = pad("R2", "1")

    # U1.7 → R1.2: 45° route
    track("DISCHARGE", route_45deg(*u1_7, *r1_2))
    # U1.7 → R2.1 over the top: up from pin 7, 45° up-right to the channel
    # above R2, then 45° down into R2.1. The diagonal (x + y = 13) clears
    # R2.2's corner by 0.4mm and runs parallel to the THRESHOLD diagonal.
    disch_diag = 13.0
    track("DISCHARGE", [
        u1_7,
        (u1_7[0], disch_diag - u1_7[0]),
        (disch_diag - TOP_CHANNEL_Y, TOP_CHANNEL_Y),
        (r2_1[0] - (r2_1[1] - TOP_CHANNEL_Y), TOP_CHANNEL_Y),
        r2_1,
    ])

    # ── THRESHOLD (F.Cu signal) ──────────────────────────────────────────
    u1_2 = pad("U1", "2")
    u1_6 = pad("U1", "6")
    r2_2 = pad("R2", "2")
    c1_1 = pad("C1", "1")

    # U1.6 → R2.2: up from pin 6 between the DISCHARGE and CONTROL stubs
    track("THRESHOLD", route_45deg(*u1_6, *r2_2))
    # U1.6 → U1.2 through the IC body: down out of pin 6's pad, one pitch
    # left on a 45°, then straight down into pin 2 (0.85mm from pins 1/3/5/7)
    body_y = u1_6[1] + 1.47                                   # 8.9: below pad 6
    pitch = u1_6[0] - u1_2[0]                                 # 1.27
    track("THRESHOLD", [u1_6, (u1_6[0], body_y), (u1_2[0], body_y + pitch), u1_2])
    # U1.2 → C1.1: down, then 45° into the timing cap
    track("THRESHOLD", route_45deg(*u1_2, *c1_1))

    # ── CONTROL (F.Cu signal) ────────────────────────────────────────────
    u1_5 = pad("U1", "5")
    c2_1 = pad("C2", "1")
    track("CONTROL", route_45deg(*u1_5, *c2_1))

    # ── OUTPUT (F.Cu signal) ─────────────────────────────────────────────
    u1_3 = pad("U1", "3")
    r3_1 = pad("R3", "1")
    # Straight down out of pin 3, 45° under pin 4's pad (0.8mm clear), right,
    # then 45° up into R3.1
    out_y = u1_3[1] + 1.73                                    # 14.3
    track("OUTPUT", [
        u1_3,
        (u1_3[0], out_y - 0.4),
        (u1_3[0] + 0.4, out_y),
        (r3_1[0] - (out_y - r3_1[1]), out_y),
        r3_1,
    ])

    # ── LED_ANODE (F.Cu signal) ──────────────────────────────────────────
    r3_2 = pad("R3", "2")
    d1_2 = pad("D1", "2")
    track("LED_ANODE", route_45deg(*r3_2, *d1_2))

    # ══════════════════════════════════════════════════════════════════════════
    # DRC — basic geometry checks (track crossings, component overlap)
    # ══════════════════════════════════════════════════════════════════════════
    print("\nRunning basic DRC...")
    violations = board.run_drc()
    if violations:
        print(f"  {len(violations)} violations:")
        for v in violations:
            print(f"    {v['type']}: {v['message']}")
    else:
        print("  PASS — No violations!")

    # ══════════════════════════════════════════════════════════════════════════
    # METRICS
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Placement & Routing Metrics ──")
    stats = board.placement_stats(netlist=netlist)
    print(f"  Board area:          {stats['board_area_mm2']} mm²")
    print(f"  Component bbox:      {stats['component_bbox_mm2']} mm²")
    print(f"  Compactness:         {stats['compactness']:.1%}")
    print(f"  Total track length:  {stats['total_track_length']:.1f} mm")
    if stats["total_ratsnest"] is not None:
        print(f"  Total ratsnest:      {stats['total_ratsnest']:.1f} mm")
        print(f"  Routing directness:  {stats['routing_directness']:.1%}")
    print(f"  Via count:           {stats['via_count']}")
    print(f"  Layer usage:")
    for layer, length in stats["layer_usage"].items():
        print(f"    {layer:6s}: {length:.1f} mm")

    if stats.get("total_hpwl") is not None:
        print(f"  HPWL (total):        {stats['total_hpwl']:.1f} mm")

    lb = stats.get("layer_balance")
    if lb is not None:
        print(f"  Layer balance:       {lb:.1%}")

    print(f"  Crosstalk risk:      {stats.get('crosstalk_risk_pairs', 0)} parallel pairs")

    cong = stats.get("congestion")
    if cong:
        print(f"  Congestion:          max={cong['max_segments_per_cell']}, "
              f"avg={cong['avg_segments_per_cell']:.1f}, "
              f"hotspot={cong['hotspot_ratio']}")

    ec = stats.get("edge_clearance", {})
    if ec:
        print(f"  Edge clearance:      min={ec.get('min_actual_mm')}mm "
              f"({ec.get('violations', 0)} violations)")

    dist = stats.get("segment_length_distribution")
    if dist:
        print(f"  Segment lengths:     min={dist['min']:.1f} median={dist['median']:.1f} "
              f"max={dist['max']:.1f} mean={dist['mean']:.1f} mm")

    print(f"\n  Per-net breakdown:")
    for net, ns in sorted(stats["per_net"].items()):
        parts = [f"track={ns['track_mm']:.1f}mm"]
        if ns["ratsnest_mm"] is not None:
            parts.append(f"ratsnest={ns['ratsnest_mm']:.1f}mm")
        if ns["directness"] is not None:
            parts.append(f"directness={ns['directness']:.0%}")
        if ns["vias"]:
            parts.append(f"vias={ns['vias']}")
        print(f"    {net:12s}  {', '.join(parts)}")

    # ══════════════════════════════════════════════════════════════════════════
    # SAVE
    # ══════════════════════════════════════════════════════════════════════════
    board.save(output_path)

    # Board ID text on silkscreen, below the bottom GND run
    board_id_text = (
        '\n  (gr_text "555-BLINKER v2" (at 12.5 19.2) (layer "F.SilkS")\n'
        '    (effects (font (size 0.8 0.8) (thickness 0.12)))\n'
        '  )'
    )
    pcb_content = Path(output_path).read_text()
    last_paren = pcb_content.rfind(")")
    Path(output_path).write_text(pcb_content[:last_paren] + board_id_text + "\n)\n")
    print(f"\nSaved routed board: {output_path}")

    # Inject pad_nets into component data for render export
    for ref, comp in board._components.items():
        for p in comp.pads:
            p["net_name"] = pad_net_map.get(ref, {}).get(p["num"], "")

    render_json = str(demo_dir / "render_data_v2.json")
    board.export_render_data(render_json, footprint_dir=fp_dir)
    print(f"Saved render data:  {render_json}")

    # ══════════════════════════════════════════════════════════════════════════
    # DRC — dual engine: kicad-cli (native) + drc_rules.py (design intent)
    # ══════════════════════════════════════════════════════════════════════════
    import json as json_mod

    # ── Engine 1: kicad-cli native DRC ──────────────────────────────────
    # Catches: net connectivity, clearance violations, courtyard overlaps,
    # copper zone issues — using real pad geometry and netlist awareness
    print("\n── KiCad Native DRC (kicad-cli) ──")
    kicad_cli = next(
        (p for p in KICAD_CLI_PATHS + [shutil.which("kicad-cli")] if p and Path(p).exists()),
        None,
    )

    engines_failed = []
    kicad_errors = 0
    kicad_warnings = 0
    if kicad_cli:
        # *-drc.json is gitignored
        drc_json = Path(output_path).with_name(Path(output_path).stem + "-drc.json")
        result = subprocess.run(
            [kicad_cli, "pcb", "drc", output_path, "--format", "json",
             "--severity-all", "--output", str(drc_json)],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and drc_json.exists():
            drc_data = json_mod.loads(drc_json.read_text())
            violations = drc_data.get("violations", [])
            unconnected = drc_data.get("unconnected_items", [])
            for v in violations:
                sev = v.get("severity", "error")
                desc = v.get("description", "")
                items_desc = ", ".join(
                    i.get("description", "")[:60] for i in v.get("items", [])[:2]
                )
                if sev == "error":
                    kicad_errors += 1
                    print(f"  [ERROR] {desc}: {items_desc}")
                else:
                    kicad_warnings += 1
                    print(f"  [WARN ] {desc}: {items_desc}")
            for u in unconnected:
                kicad_errors += 1
                items_desc = " ↔ ".join(
                    i.get("description", "")[:50] for i in u.get("items", [])[:2]
                )
                print(f"  [ERROR] Unconnected: {items_desc}")
            print(f"  KiCad DRC: {kicad_errors} errors, {kicad_warnings} warnings")
        else:
            engines_failed.append("kicad-cli")
            print(f"  Failed: {(result.stderr or result.stdout).strip()}")
    else:
        engines_failed.append("kicad-cli")
        print("  kicad-cli not found")

    # ── Engine 2: Design intent DRC (drc_rules.py) ──────────────────────
    # Catches: bypass cap placement, tombstoning risk, acute angles,
    # track-to-pad clearance, asymmetric dead space, silkscreen issues.
    # Needs KiCad's Python for pcbnew.
    print("\n── Design Intent DRC (drc_rules.py) ──")
    custom_errors = 0
    custom_warnings = 0
    if KICAD_PYTHON.exists():
        result = subprocess.run(
            [str(KICAD_PYTHON), str(demo_dir / "drc_rules.py"), render_json],
            capture_output=True, text=True,
        )
        # pcbnew prints a harmless wx "traits" assert on startup
        output = "\n".join(
            line for line in result.stdout.splitlines()
            if "assert" not in line and "traits" not in line
        )
        if output.strip():
            print(output)
            for line in output.splitlines():
                if "[ERROR]" in line:
                    custom_errors += 1
                elif "[WARN" in line:
                    custom_warnings += 1
        if result.returncode not in (0, 1):
            engines_failed.append("drc_rules.py")
            for line in result.stderr.splitlines():
                if "assert" not in line and "traits" not in line:
                    print(line)
    else:
        engines_failed.append("drc_rules.py")
        print(f"  KiCad Python not found at {KICAD_PYTHON}")

    # ── Combined summary ────────────────────────────────────────────────
    total_errors = kicad_errors + custom_errors
    total_warnings = kicad_warnings + custom_warnings
    print(f"\n══ Combined DRC: {total_errors} errors, {total_warnings} warnings ══")
    print(f"   KiCad native: {kicad_errors}E / {kicad_warnings}W")
    print(f"   Design rules: {custom_errors}E / {custom_warnings}W")
    if engines_failed:
        print(f"   Did not run: {', '.join(engines_failed)}")

    # Non-zero exit when the board has DRC errors or couldn't be fully checked
    sys.exit(1 if total_errors or engines_failed else 0)


if __name__ == "__main__":
    main()
