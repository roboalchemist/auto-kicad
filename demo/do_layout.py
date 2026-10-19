#!/usr/bin/env python3
"""
Use the BoardLayout agent interface to place and route the 555 blinker board.

This script demonstrates how an agent would use layout.py to:
1. Load the generated PCB
2. Place components in a sensible arrangement
3. Route tracks between connected pads
4. Run DRC and save

Net connectivity (from blinker.net):
  VCC:       R1.1, U1.8, U1.4
  GND:       C1.2, C2.2, D1.1, U1.1
  DISCHARGE: R1.2, R2.1, U1.7
  THRESHOLD: C1.1, R2.2, U1.2, U1.6
  CONTROL:   C2.1, U1.5
  OUTPUT:    R3.1, U1.3
  LED_ANODE: D1.2, R3.2

NE555 pinout (SOIC-8, pads numbered 1-8):
  Standard: 1=GND, 2=TRIG, 3=OUT, 4=RST, 5=CONT, 6=THRES, 7=DISCH, 8=VCC

  Pad layout in our SOIC-8 footprint (no rotation):
    Bottom row (y=+2.57):  pads 1,2,3,4  (x from -1.905 to +1.905)
    Top row    (y=-2.57):  pads 8,7,6,5  (x from -1.905 to +1.905)

    Pin 1 (GND)    at (-1.905, +2.57)   Pin 8 (VCC)   at (-1.905, -2.57)
    Pin 2 (TRIG)   at (-0.635, +2.57)   Pin 7 (DISCH) at (-0.635, -2.57)
    Pin 3 (OUT)    at (+0.635, +2.57)   Pin 6 (THRES) at (+0.635, -2.57)
    Pin 4 (RST)    at (+1.905, +2.57)   Pin 5 (CONT)  at (+1.905, -2.57)

2-pad components (R0805, C0805):
  pad 1 at (-1, 0), pad 2 at (1, 0)
  With rotation=90: pad 1 at (0, +1), pad 2 at (0, -1)

LED (LED0805-RD):
  pad 1 (cathode) at (-1.1, 0), pad 2 (anode) at (1.1, 0)
  With rotation=90: pad 1 at (0, +1.1), pad 2 at (0, -1.1)
"""

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from layout import BoardLayout


def parse_netlist(netlist_path: str) -> dict[str, list[tuple[str, str]]]:
    """Parse netlist to get net → [(ref, pin), ...] mapping."""
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
                r'\(node\s*\(ref\s+"(\w+)"\)\s*\(pin\s+"(\w+)"\)',
                block,
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
                rad = math.radians(-comp.rotation)  # KiCad rotation is CW
                rx = lx * math.cos(rad) - ly * math.sin(rad)
                ry = lx * math.sin(rad) + ly * math.cos(rad)
                lx, ly = rx, ry
            return (
                round(comp.x + lx, 3),
                round(comp.y + ly, 3),
            )

    raise ValueError(f"Pad {pad_num} not found on {ref}")


def route_two_points(x1, y1, x2, y2, channel_y=None):
    """Route between two points using L-shaped or direct paths.

    If channel_y is provided, route via that Y coordinate to avoid overlaps.
    """
    if abs(x1 - x2) < 0.1:
        # Vertical — direct
        return [(x1, y1), (x2, y2)]
    if abs(y1 - y2) < 0.1:
        # Horizontal — direct
        return [(x1, y1), (x2, y2)]

    if channel_y is not None:
        # Route via a specific Y channel: go vertical to channel, horizontal, vertical to target
        points = [(x1, y1)]
        if abs(y1 - channel_y) > 0.1:
            points.append((x1, channel_y))
        points.append((x2, channel_y))
        if abs(y2 - channel_y) > 0.1:
            points.append((x2, y2))
        return points

    # Default L-shape: vertical first, then horizontal
    return [(x1, y1), (x1, y2), (x2, y2)]


def main():
    demo_dir = Path(__file__).parent
    pcb_path = str(demo_dir / "blinker.kicad_pcb")
    netlist_path = str(demo_dir / "blinker.net")
    output_path = str(demo_dir / "blinker_routed.kicad_pcb")

    print("Loading board...")
    board = BoardLayout(pcb_path)

    print(f"Found {len(board.list_components())} components")
    for c in board.list_components():
        print(f"  {c['ref']:4s} at ({c['x']}, {c['y']}), pads: {len(board._components[c['ref']].pads)}")

    # ── Step 1: Place components ─────────────────────────────────────────────
    # Board: 28mm x 22mm (compact)
    #
    # Layout strategy:
    #   U1 (555) center-left. Timing network (R1, R2) above.
    #   C2 bypass right of U1. C1 timing cap below. R3+D1 output chain right.
    #
    # U1 SOIC-8 (no rotation):
    #   Bottom row (+y): pins 1(GND), 2(TRIG), 3(OUT), 4(RST)
    #   Top row (-y):    pins 8(VCC), 7(DISCH), 6(THRES), 5(CONT)

    print("\nPlacing components...")
    board.set_board_outline(28, 22)

    # U1: NE555 — center-left of board
    board.place_component("U1", 11, 11)

    # R1: VCC → DISCHARGE — above-left of U1, near pins 8,7
    board.place_component("R1", 7, 4.5, rotation=0)

    # R2: DISCHARGE → THRESHOLD — above-right of U1, near pins 7,6
    board.place_component("R2", 15, 4.5, rotation=0)

    # C2: CONTROL bypass → GND — right of U1, near pin 5
    board.place_component("C2", 19, 10, rotation=90)

    # C1: THRESHOLD → GND (timing cap) — below U1, near pins 1,2
    board.place_component("C1", 11, 18, rotation=0)

    # R3: OUTPUT → LED_ANODE — below-right of U1
    board.place_component("R3", 20, 15, rotation=0)

    # D1: LED_ANODE → GND — right of R3
    board.place_component("D1", 24, 18, rotation=90)

    print("Components placed:")
    for c in board.list_components():
        print(f"  {c['ref']:4s} at ({c['x']}, {c['y']}, rot={c['rotation']})")

    # Print all pad absolute positions for debugging
    print("\nPad positions:")
    netlist = parse_netlist(netlist_path)
    for net_name, nodes in sorted(netlist.items()):
        print(f"  {net_name}:")
        for ref, pin in nodes:
            try:
                x, y = get_pad_position(board, ref, pin)
                print(f"    {ref}.{pin} at ({x}, {y})")
            except ValueError as e:
                print(f"    {ref}.{pin} ERROR: {e}")

    # ── Step 2: Route tracks ─────────────────────────────────────────────────
    print("\nRouting tracks...")

    track_width_signal = 0.25   # mm, signal traces
    track_width_power = 0.4     # mm, power traces (VCC, GND)

    def pad(ref, pin):
        return get_pad_position(board, ref, pin)

    def track(net_name, points, power=False, layer="F.Cu"):
        w = track_width_power if power else track_width_signal
        board.add_track(net_name, points, width_mm=w, layer=layer)
        p0 = f"({points[0][0]:.1f},{points[0][1]:.1f})"
        p1 = f"({points[-1][0]:.1f},{points[-1][1]:.1f})"
        print(f"  {net_name}: {p0} → {p1}  ({len(points)} pts, {layer})")

    def via(net_name, x, y):
        board.add_via(x, y, net_name, drill_mm=0.3)
        print(f"  {net_name}: via at ({x:.1f},{y:.1f})")

    # ── Routing strategy ──
    # Two-layer: F.Cu = signals, B.Cu = power (VCC, GND).
    # Compact 28x22mm board — tighter channels.
    #
    # U1 pad positions (U1 at 11,11):
    #   Top row (y=8.43):    pin8(9.095), pin7(10.365), pin6(11.635), pin5(12.905)
    #   Bottom row (y=13.57): pin1(9.095), pin2(10.365), pin3(11.635), pin4(12.905)

    # --- VCC net (B.Cu): R1.1, U1.8, U1.4 ---
    u1_8 = pad("U1", "8")
    u1_4 = pad("U1", "4")
    r1_1 = pad("R1", "1")

    # R1.1 → via offset down
    v_r1_1 = (r1_1[0], r1_1[1] + 1.5)
    track("VCC", [r1_1, v_r1_1], power=True)
    via("VCC", *v_r1_1)

    # U1.8 → via offset up
    v_u1_8 = (u1_8[0], u1_8[1] - 1.5)
    track("VCC", [u1_8, v_u1_8], power=True)
    via("VCC", *v_u1_8)

    # B.Cu: R1.1 via → U1.8 via
    track("VCC", route_two_points(*v_r1_1, *v_u1_8, channel_y=6.5), power=True, layer="B.Cu")

    # U1.4 → via offset right (avoid OUTPUT at y≈15)
    v_u1_4 = (u1_4[0] + 1.5, u1_4[1])
    track("VCC", [u1_4, v_u1_4], power=True)
    via("VCC", *v_u1_4)

    # B.Cu: U1.8 via → U1.4 via (route right side, avoid GND hub)
    track("VCC", [v_u1_8, (v_u1_4[0], v_u1_8[1]), v_u1_4], power=True, layer="B.Cu")

    # --- GND net (B.Cu): C1.2, C2.2, D1.1, U1.1 ---
    u1_1 = pad("U1", "1")
    c1_2 = pad("C1", "2")
    c2_2 = pad("C2", "2")
    d1_1 = pad("D1", "1")

    # U1.1 → via offset down
    v_u1_1 = (u1_1[0], u1_1[1] + 1.5)
    track("GND", [u1_1, v_u1_1], power=True)
    via("GND", *v_u1_1)

    # C1.2 → via offset down
    v_c1_2 = (c1_2[0], c1_2[1] + 1.5)
    track("GND", [c1_2, v_c1_2], power=True)
    via("GND", *v_c1_2)

    # C2.2 → via offset left
    v_c2_2 = (c2_2[0] - 1.5, c2_2[1])
    track("GND", [c2_2, v_c2_2], power=True)
    via("GND", *v_c2_2)

    # D1.1 → via offset down
    v_d1_1 = (d1_1[0], d1_1[1] + 1.5)
    track("GND", [d1_1, v_d1_1], power=True)
    via("GND", *v_d1_1)

    # B.Cu hub from U1.1 via (routes stay below y=15 to avoid VCC B.Cu above)
    track("GND", route_two_points(*v_u1_1, *v_c1_2), power=True, layer="B.Cu")
    # To C2.2: go down first then right, staying below VCC B.Cu channel
    track("GND", [v_u1_1, (v_u1_1[0], 16.5), (v_c2_2[0], 16.5), v_c2_2], power=True, layer="B.Cu")
    # To D1.1: go down then right
    track("GND", [v_u1_1, (v_u1_1[0], 20.5), (v_d1_1[0], 20.5), v_d1_1], power=True, layer="B.Cu")

    # --- DISCHARGE net (F.Cu): R1.2, R2.1, U1.7 ---
    u1_7 = pad("U1", "7")
    r1_2 = pad("R1", "2")
    r2_1 = pad("R2", "1")

    # U1.7 → R1.2 (up-left)
    track("DISCHARGE", route_two_points(*u1_7, *r1_2, channel_y=6.5))
    # U1.7 → R2.1 (up-right)
    track("DISCHARGE", route_two_points(*u1_7, *r2_1, channel_y=7.5))

    # --- THRESHOLD net (F.Cu + B.Cu): C1.1, R2.2, U1.2, U1.6 ---
    u1_2 = pad("U1", "2")
    u1_6 = pad("U1", "6")
    r2_2 = pad("R2", "2")
    c1_1 = pad("C1", "1")

    # U1.6 → via into IC body center
    v_u1_6 = (u1_6[0], 10)
    track("THRESHOLD", [u1_6, v_u1_6])
    via("THRESHOLD", *v_u1_6)

    # R2.2 → via offset down
    v_r2_2 = (r2_2[0], r2_2[1] + 1.5)
    track("THRESHOLD", [r2_2, v_r2_2])
    via("THRESHOLD", *v_r2_2)

    # B.Cu: U1.6 via → R2.2 via
    track("THRESHOLD", [v_u1_6, (v_u1_6[0], 14), (17, 14), (17, v_r2_2[1]), v_r2_2], layer="B.Cu")

    # U1.6 → U1.2: through IC body center
    track("THRESHOLD", [u1_6, (u1_6[0], 11), (u1_2[0], 11), u1_2])

    # U1.2 → C1.1: drop down
    track("THRESHOLD", route_two_points(*u1_2, *c1_1, channel_y=16))

    # --- CONTROL net (F.Cu): C2.1, U1.5 ---
    u1_5 = pad("U1", "5")
    c2_1 = pad("C2", "1")
    track("CONTROL", route_two_points(*u1_5, *c2_1))

    # --- OUTPUT net (F.Cu): R3.1, U1.3 ---
    u1_3 = pad("U1", "3")
    r3_1 = pad("R3", "1")
    track("OUTPUT", [u1_3, (u1_3[0], 15), (r3_1[0], 15), r3_1])

    # --- LED_ANODE net (F.Cu): D1.2, R3.2 ---
    r3_2 = pad("R3", "2")
    d1_2 = pad("D1", "2")
    track("LED_ANODE", route_two_points(*r3_2, *d1_2))

    # ── Step 3: DRC ──────────────────────────────────────────────────────────
    print("\nRunning DRC...")
    violations = board.run_drc()
    if violations:
        print(f"  {len(violations)} violations found:")
        for v in violations:
            print(f"    {v['type']}: {v['message']}")
    else:
        print("  No violations!")

    # ── Step 4: Placement stats ─────────────────────────────────────────────
    print("\nPlacement & routing efficiency:")
    stats = board.placement_stats(netlist=netlist)
    print(f"  Board area:         {stats['board_area_mm2']} mm²")
    print(f"  Component bbox:     {stats['component_bbox_mm2']} mm²")
    print(f"  Compactness:        {stats['compactness']:.1%}")
    print(f"  Total track length: {stats['total_track_length']:.1f} mm")
    if stats["total_ratsnest"] is not None:
        print(f"  Total ratsnest:     {stats['total_ratsnest']:.1f} mm")
        print(f"  Routing directness: {stats['routing_directness']:.1%}")
    print(f"  Via count:          {stats['via_count']}")
    print(f"  Layer usage:")
    for layer, length in stats["layer_usage"].items():
        print(f"    {layer:6s}: {length:.1f} mm")
    print(f"  Per-net breakdown:")
    for net, ns in stats["per_net"].items():
        parts = [f"track={ns['track_mm']:.1f}mm"]
        if ns["ratsnest_mm"] is not None:
            parts.append(f"ratsnest={ns['ratsnest_mm']:.1f}mm")
        if ns["directness"] is not None:
            parts.append(f"directness={ns['directness']:.0%}")
        if ns["vias"]:
            parts.append(f"vias={ns['vias']}")
        print(f"    {net:12s}  {', '.join(parts)}")

    # ── New metrics ──
    if stats.get("total_hpwl") is not None:
        print(f"\n  HPWL (total):       {stats['total_hpwl']:.1f} mm")
        print(f"  HPWL per net:")
        for net, hpwl in sorted(stats["hpwl_per_net"].items()):
            aspect = stats["net_bbox_aspect"].get(net, "?")
            print(f"    {net:12s}  hpwl={hpwl:.1f}mm, bbox_aspect={aspect}")

    dist = stats.get("segment_length_distribution")
    if dist:
        print(f"\n  Segment length distribution ({dist['count']} segments):")
        print(f"    min={dist['min']:.1f}  p25={dist['p25']:.1f}  "
              f"median={dist['median']:.1f}  p75={dist['p75']:.1f}  "
              f"max={dist['max']:.1f}  mean={dist['mean']:.1f} mm")

    print(f"  Crosstalk risk:     {stats.get('crosstalk_risk_pairs', 0)} parallel segment pairs")

    lb = stats.get("layer_balance")
    if lb is not None:
        print(f"  Layer balance:      {lb:.1%}")

    cong = stats.get("congestion")
    if cong:
        print(f"  Congestion ({cong['grid_size_mm']}mm grid, {cong['rows']}x{cong['cols']}):")
        print(f"    max={cong['max_segments_per_cell']} segs/cell, "
              f"avg={cong['avg_segments_per_cell']:.1f}, "
              f"hotspot_ratio={cong['hotspot_ratio']}")

    ar = stats.get("annular_ring", {})
    if ar:
        print(f"  Annular ring:       {ar.get('violations', 0)} violations "
              f"(min required: {ar.get('min_required_mm')}mm, "
              f"sizes: {ar.get('sizes_mm', [])})")

    ec = stats.get("edge_clearance", {})
    if ec:
        print(f"  Edge clearance:     min={ec.get('min_actual_mm')}mm, "
              f"{ec.get('violations', 0)} violations "
              f"(min required: {ec.get('min_required_mm')}mm)")

    pp = stats.get("power_pin_proximity_mm", {})
    if pp:
        print(f"  Power pin proximity (avg pad-to-via):")
        for net, dist_mm in sorted(pp.items()):
            print(f"    {net:12s}  {dist_mm:.1f}mm")

    md = stats.get("manhattan_directness")
    if md is not None:
        print(f"  Manhattan directness: {md:.1%}")
        for net, m in sorted(stats.get("manhattan_per_net", {}).items()):
            track_mm = stats["per_net"].get(net, {}).get("track_mm", 0)
            det = round(m / track_mm, 3) if track_mm > 0 else None
            det_str = f"{det:.0%}" if det else "n/a"
            print(f"    {net:12s}  manhattan={m:.1f}mm, detour_factor={det_str}")

    pc = stats.get("plane_coverage", {})
    if pc:
        pct = pc.get("coverage_pct")
        note = pc.get("note", "")
        if pct is not None:
            print(f"  Plane coverage:     {pct:.1%}")
        else:
            print(f"  Plane coverage:     {note}")

    # ── Step 5: Save ─────────────────────────────────────────────────────────
    board.save(output_path)
    print(f"\nSaved routed board: {output_path}")

    render_json = str(demo_dir / "render_data.json")
    board.export_render_data(render_json, footprint_dir=str(demo_dir / "libs" / "footprints"))
    print(f"Saved render data:  {render_json}")


if __name__ == "__main__":
    main()
