"""
BoardLayout — Programmatic KiCad PCB manipulation for agent-driven placement & routing.

Provides a Python interface for placing components, adding tracks, setting board
outlines, and running DRC on .kicad_pcb files. Designed so a Claude agent (or MCP
server) can drive placement/routing after circuit generation.

Implementation uses direct S-expression manipulation (no pcbnew dependency).
"""

import json
import math
import os
import re
import uuid
import warnings
from dataclasses import dataclass, field
from pathlib import Path


# ── S-expression helpers ─────────────────────────────────────────────────────

def _sexp_parse(text: str) -> list:
    """Parse a KiCad S-expression string into nested lists."""
    tokens = re.findall(r'\(|\)|"[^"]*"|\S+', text)
    stack = [[]]
    for token in tokens:
        if token == "(":
            stack.append([])
        elif token == ")":
            node = stack.pop()
            stack[-1].append(node)
        else:
            # Strip quotes from strings
            if token.startswith('"') and token.endswith('"'):
                token = token[1:-1]
            stack[-1].append(token)
    return stack[0]


def _sexp_write(node, indent=0) -> str:
    """Serialize a nested list back to KiCad S-expression format."""
    if isinstance(node, list):
        if not node:
            return "()"
        # Check if this is a simple key-value (all strings, short)
        if all(isinstance(x, str) for x in node) and len(node) <= 4:
            inner = " ".join(_quote_if_needed(x) for x in node)
            return f"({inner})"
        # Multi-line for complex nodes
        lines = []
        lines.append("(" + _quote_if_needed(node[0]) if isinstance(node[0], str) else "(")
        for child in node[1:]:
            child_str = _sexp_write(child, indent + 2)
            lines.append(" " * (indent + 2) + child_str)
        lines.append(" " * indent + ")")
        return "\n".join(lines)
    return _quote_if_needed(node)


def _quote_if_needed(s: str) -> str:
    """Quote a string if it contains spaces or special characters."""
    if isinstance(s, str) and (
        " " in s or '"' in s or "(" in s or ")" in s or len(s) == 0
    ):
        return f'"{s}"'
    return str(s)


def _gen_uuid() -> str:
    return str(uuid.uuid4())


def _quote(s: str) -> str:
    """Quote a string the way KiCad does (backslash-escaped)."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _sexp_end(text: str, start: int) -> int:
    """Return the index just past the S-expression that opens at text[start]."""
    depth = 0
    in_str = False
    i = start
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError(f"Unbalanced S-expression starting at offset {start}")


# Generator name written into boards created by new_board()
_GENERATOR = "blinker-pipeline"

# (at x y [angle]) — position of footprints, pads, and texts
_AT_RE = re.compile(r'\(at\s+([\d.+-]+)\s+([\d.+-]+)(?:\s+([\d.+-]+))?\)')
# (pad "1" smd rect (at x y ...) — KiCad 5 leaves the pad name unquoted
_PAD_RE = re.compile(r'\(pad\s+"?(\w+)"?\s+(\w+)\s+(\w+)\s+\(at\s+([\d.+-]+)\s+([\d.+-]+)')
# Reference/value text: (fp_text reference R1 ...) up to KiCad 7,
# (property "Reference" "R1" ...) from KiCad 8 on
_REF_RE = re.compile(r'(?:\(fp_text\s+reference\s+|\(property\s+"Reference"\s+)"?([^"\s)]+)"?')
_VALUE_RE = re.compile(r'(?:\(fp_text\s+value\s+|\(property\s+"Value"\s+)"?([^"\s)]+)"?')
# Nets: (net 3 "VCC") up to KiCad 9 (KiCad 5 left the name unquoted);
# (net "VCC") from board version 20251028 (KiCad 10), which dropped net codes.
_NUMBERED_NET_RE = re.compile(r'\(net\s+(\d+)\s+(?:"((?:[^"\\]|\\.)*)"|([^\s()"]+))\)')
_NAMED_NET_RE = re.compile(r'\(net\s+"((?:[^"\\]|\\.)*)"\)')
_NAMED_NETS_MIN_VERSION = 20251028
# Top-level footprint blocks start on their own line
_FOOTPRINT_START_RE = re.compile(r'^[ \t]*\((?:footprint|module)\s', re.MULTILINE)


def _footprint_spans(content: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of every top-level footprint/module block."""
    spans = []
    for m in _FOOTPRINT_START_RE.finditer(content):
        start = content.index("(", m.start())
        spans.append((start, _sexp_end(content, start)))
    return spans


def _net_name_in(block: str) -> str | None:
    """Net name referenced inside a pad block, in either net syntax."""
    m = _NUMBERED_NET_RE.search(block)
    if m:
        return m.group(2) if m.group(2) is not None else m.group(3)
    m = _NAMED_NET_RE.search(block)
    return m.group(1) if m else None


def _fmt_num(v: float) -> str:
    """Format a number without trailing zeros, as KiCad writes them."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _rotate_local(lx: float, ly: float, rotation: float) -> tuple[float, float]:
    """Rotate a footprint-local offset into board orientation (KiCad: y down, CCW)."""
    if not rotation:
        return lx, ly
    rad = math.radians(-rotation)
    return (
        lx * math.cos(rad) - ly * math.sin(rad),
        lx * math.sin(rad) + ly * math.cos(rad),
    )


def _rotate_inner_angles(block: str, delta: float, skip_first: bool) -> str:
    """Add `delta` degrees to every (at x y [angle]) inside a footprint block.

    Inside a placed footprint KiCad keeps pad and text x/y in the footprint's
    local frame but stores their angles in board orientation, so turning the
    footprint means turning each of those angles too. `skip_first` leaves the
    footprint's own (at ...) alone.
    """
    if not delta % 360:
        return block
    seen = 0

    def repl(m):
        nonlocal seen
        seen += 1
        if skip_first and seen == 1:
            return m.group(0)
        angle = (float(m.group(3) or 0) + delta) % 360
        if not angle and m.group(3) is None:
            return m.group(0)
        return f"(at {m.group(1)} {m.group(2)} {_fmt_num(angle)})"

    return _AT_RE.sub(repl, block)


def _remove_edge_rects(content: str) -> str:
    """Drop every (gr_rect ...) on Edge.Cuts, however it is formatted."""
    out, pos = [], 0
    for m in re.finditer(r'\(gr_rect\b', content):
        if m.start() < pos:
            continue
        end = _sexp_end(content, m.start())
        if "Edge.Cuts" in content[m.start():end]:
            out.append(content[pos:m.start()].rstrip(" \t"))
            pos = end
    out.append(content[pos:])
    return "".join(out)


# ── Footprint file reading ───────────────────────────────────────────────────

def _read_footprint(fp_dir: str, footprint_ref: str) -> str | None:
    """Find and read a .kicad_mod file for a footprint reference like 'footprints:C7593'."""
    parts = footprint_ref.split(":")
    if len(parts) == 2:
        lib_name, fp_name = parts
    else:
        fp_name = footprint_ref

    # Search for the .kicad_mod file
    fp_path = Path(fp_dir)
    candidates = [
        fp_path / f"{fp_name}.kicad_mod",
        fp_path / "footprints.pretty" / f"{fp_name}.kicad_mod",
    ]
    # Also search in subdirectories
    for p in fp_path.rglob(f"{fp_name}.kicad_mod"):
        candidates.append(p)

    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text()
    return None


# ── Board Layout Class ───────────────────────────────────────────────────────

@dataclass
class ComponentInfo:
    ref: str
    footprint: str
    value: str
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    pads: list = field(default_factory=list)


class BoardLayout:
    """Load and manipulate a .kicad_pcb file for component placement and routing."""

    def __init__(self, pcb_path: str):
        """Load a .kicad_pcb file for manipulation."""
        self.pcb_path = pcb_path
        self._content = Path(pcb_path).read_text()
        self._components: dict[str, ComponentInfo] = {}
        self._tracks: list[dict] = []
        self._vias: list[dict] = []
        self._board_outline: tuple[float, float] | None = None
        self._nets: dict[str, int] = {}  # net_name -> net_id
        version = re.search(r'\(kicad_pcb\s+\(version\s+(\d+)\)', self._content)
        self._named_nets = bool(version) and int(version.group(1)) >= _NAMED_NETS_MIN_VERSION
        self._parse_existing()
        self._declared_nets = set(self._nets)

    @classmethod
    def new_board(
        cls,
        pcb_path: str,
        components: list[dict],
        footprint_dir: str,
    ) -> "BoardLayout":
        """Create a new .kicad_pcb with the given components.

        Args:
            pcb_path: Output path for the .kicad_pcb file.
            components: List of dicts with 'ref', 'value', 'footprint' keys.
            footprint_dir: Directory containing .kicad_mod files.
        """
        board = cls.__new__(cls)
        board.pcb_path = pcb_path
        board._components = {}
        board._tracks = []
        board._vias = []
        board._board_outline = None
        board._nets = {}
        board._named_nets = False  # we write the KiCad 8 format, which numbers nets
        board._declared_nets = set()
        board._footprint_dir = footprint_dir
        board._raw_footprints = {}  # ref -> raw kicad_mod content

        # Load footprint data for each component
        for i, comp in enumerate(components):
            ref = comp["ref"]
            fp_content = _read_footprint(footprint_dir, comp["footprint"])
            if fp_content is None:
                warnings.warn(
                    f"{ref}: footprint {comp['footprint']!r} not found under "
                    f"{footprint_dir}; using a generic 2-pad placeholder"
                )
            # Parse pad info from footprint content
            pads = []
            if fp_content:
                for pad_match in _PAD_RE.finditer(fp_content):
                    pads.append({
                        "num": pad_match.group(1),
                        "type": pad_match.group(2),
                        "shape": pad_match.group(3),
                        "local_x": float(pad_match.group(4)),
                        "local_y": float(pad_match.group(5)),
                    })
            board._components[ref] = ComponentInfo(
                ref=ref,
                footprint=comp["footprint"],
                value=comp.get("value", ref),
                x=10.0 + (i % 5) * 15.0,
                y=10.0 + (i // 5) * 15.0,
                pads=pads,
            )
            if fp_content:
                board._raw_footprints[ref] = fp_content

        board._content = board._generate_pcb_content()
        return board

    def _parse_existing(self):
        """Parse component positions and nets from existing .kicad_pcb content."""
        if self._named_nets:
            # KiCad 10+ boards only name their nets; number them ourselves
            for match in _NAMED_NET_RE.finditer(self._content):
                self._net_id(match.group(1))
        else:
            for match in _NUMBERED_NET_RE.finditer(self._content):
                name = match.group(2) if match.group(2) is not None else match.group(3)
                self._nets[name] = int(match.group(1))

        # Both (footprint ...) (KiCad 6+) and (module ...) (KiCad 5) blocks
        for start, end in _footprint_spans(self._content):
            block = self._content[start:end]
            # The first (at x y [rot]) in a block is the footprint's own position
            at_match = _AT_RE.search(block)
            ref_match = _REF_RE.search(block)
            val_match = _VALUE_RE.search(block)
            fp_name_match = re.match(r'\s*\((?:footprint|module)\s+"?([^"\s)]+)"?', block)

            if ref_match and at_match:
                ref = ref_match.group(1)
                # Parse pad info for routing
                pads = []
                for pad_match in _PAD_RE.finditer(block):
                    pads.append({
                        "num": pad_match.group(1),
                        "type": pad_match.group(2),
                        "shape": pad_match.group(3),
                        "local_x": float(pad_match.group(4)),
                        "local_y": float(pad_match.group(5)),
                    })

                self._components[ref] = ComponentInfo(
                    ref=ref,
                    footprint=fp_name_match.group(1) if fp_name_match else "",
                    value=val_match.group(1) if val_match else "",
                    x=float(at_match.group(1)),
                    y=float(at_match.group(2)),
                    rotation=float(at_match.group(3)) if at_match.group(3) else 0.0,
                    pads=pads,
                )

    def list_components(self) -> list[dict]:
        """Return all components with ref, footprint, current position."""
        return [
            {
                "ref": c.ref,
                "footprint": c.footprint,
                "value": c.value,
                "x": c.x,
                "y": c.y,
                "rotation": c.rotation,
            }
            for c in self._components.values()
        ]

    def place_component(self, ref: str, x_mm: float, y_mm: float, rotation: float = 0):
        """Move a component to absolute position (mm) with rotation (degrees)."""
        if ref not in self._components:
            raise ValueError(f"Component {ref} not found. Available: {list(self._components.keys())}")
        comp = self._components[ref]

        # Update in-memory
        old_x, old_y, old_rot = comp.x, comp.y, comp.rotation
        comp.x, comp.y, comp.rotation = x_mm, y_mm, rotation

        # Update in raw content
        self._content = self._update_component_position(
            self._content, ref, old_x, old_y, old_rot, x_mm, y_mm, rotation
        )

    def _update_component_position(
        self, content: str, ref: str,
        old_x: float, old_y: float, old_rot: float,
        new_x: float, new_y: float, new_rot: float,
    ) -> str:
        """Update a component's (at ...) in the PCB content by finding its block and patching."""
        for start, end in _footprint_spans(content):
            block = content[start:end]
            ref_match = _REF_RE.search(block)
            if not ref_match or ref_match.group(1) != ref:
                continue

            # The first (at ...) in the block is the component-level position
            at_match = _AT_RE.search(block)
            if not at_match:
                continue

            rot_str = f" {new_rot}" if new_rot else ""
            new_at = f"(at {new_x} {new_y}{rot_str})"
            new_block = block[:at_match.start()] + new_at + block[at_match.end():]
            new_block = _rotate_inner_angles(new_block, new_rot - old_rot, skip_first=True)
            return content[:start] + new_block + content[end:]

        return content

    def set_pad_nets(self, pad_net_map: dict[str, dict[str, str]]):
        """Set net assignments for component pads.

        Pad nets are written when a board created with new_board() is saved.

        Args:
            pad_net_map: {ref: {pad_num: net_name}} mapping
        """
        self._pad_net_map = pad_net_map
        for pads in pad_net_map.values():
            for net_name in pads.values():
                self._net_id(net_name)

    def _net_id(self, net_name: str) -> int:
        """Return the net code for `net_name`, registering the net if it is new."""
        if not net_name:
            return 0
        if net_name not in self._nets:
            self._nets[net_name] = max(self._nets.values(), default=0) + 1
        return self._nets[net_name]

    def auto_place_grid(self, spacing_mm: float = 10.0):
        """Simple grid placement — spread components out so they don't overlap."""
        refs = sorted(self._components.keys())
        cols = max(1, int(len(refs) ** 0.5) + 1)
        for i, ref in enumerate(refs):
            row, col = divmod(i, cols)
            x = 15.0 + col * spacing_mm
            y = 15.0 + row * spacing_mm
            self.place_component(ref, x, y, self._components[ref].rotation)

    def set_board_outline(self, width_mm: float, height_mm: float):
        """Create a rectangular board outline on Edge.Cuts layer."""
        self._board_outline = (width_mm, height_mm)

    def add_track(
        self,
        net_name: str,
        points: list[tuple[float, float]],
        width_mm: float = 0.25,
        layer: str = "F.Cu",
    ):
        """Add a copper track between a list of (x,y) points on a given layer."""
        net_id = self._net_id(net_name)
        self._tracks.append({
            "net": net_id,
            "net_name": net_name,
            "points": points,
            "width": width_mm,
            "layer": layer,
        })

    def add_via(
        self,
        x_mm: float,
        y_mm: float,
        net_name: str,
        drill_mm: float = 0.3,
    ):
        """Add a via at position."""
        net_id = self._net_id(net_name)
        self._vias.append({
            "x": x_mm,
            "y": y_mm,
            "net": net_id,
            "net_name": net_name,
            "drill": drill_mm,
        })

    def get_netlist_connections(self) -> dict[str, list[dict]]:
        """Return all nets with their connected pads and positions — the 'ratsnest'.

        Since the generated PCB may not have net assignments on pads (KiCad 5
        module format doesn't always include them), this method also returns
        component pad absolute positions so an agent can plan routing based on
        component placement and the netlist.
        """
        # Build pad absolute positions from parsed components
        result: dict[str, list[dict]] = {}

        # If we have net assignments in the content, use them
        for start, end in _footprint_spans(self._content):
            block = self._content[start:end]
            ref_match = _REF_RE.search(block)
            at_match = _AT_RE.search(block)
            if not ref_match or not at_match:
                continue
            ref = ref_match.group(1)
            fp_x, fp_y = float(at_match.group(1)), float(at_match.group(2))
            fp_rot = float(at_match.group(3) or 0)

            for pad_match in _PAD_RE.finditer(block):
                pad_num = pad_match.group(1)
                dx, dy = _rotate_local(float(pad_match.group(4)), float(pad_match.group(5)), fp_rot)
                pad_x = fp_x + dx
                pad_y = fp_y + dy

                pad_block = block[pad_match.start():_sexp_end(block, pad_match.start())]
                net_name = _net_name_in(pad_block)

                pad_info = {
                    "ref": ref,
                    "pad": pad_num,
                    "x": round(pad_x, 3),
                    "y": round(pad_y, 3),
                }

                if net_name:
                    result.setdefault(net_name, []).append(pad_info)
                else:
                    # Group unassigned pads under component ref for reference
                    key = f"_unassigned_{ref}_pad{pad_num}"
                    result.setdefault(key, []).append(pad_info)

        return result

    def run_drc(self) -> list[dict]:
        """Run basic design rule checks, return violations.

        Checks:
        - Component overlap (centers too close)
        - Components outside board outline
        - Track crossings between different nets on the same layer (shorts)
        - Collinear track overlaps between different nets on the same layer

        Note: This is a simplified DRC. Full DRC requires pcbnew.
        """
        violations = []

        # Check for overlapping components (centers too close)
        refs = list(self._components.keys())
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                ci = self._components[refs[i]]
                cj = self._components[refs[j]]
                dist = ((ci.x - cj.x) ** 2 + (ci.y - cj.y) ** 2) ** 0.5
                if dist < 2.0:  # 2mm minimum clearance
                    violations.append({
                        "type": "overlap",
                        "refs": [refs[i], refs[j]],
                        "distance_mm": round(dist, 2),
                        "message": f"{refs[i]} and {refs[j]} are only {dist:.1f}mm apart",
                    })

        # Check components within board outline
        if self._board_outline:
            w, h = self._board_outline
            for ref, comp in self._components.items():
                if comp.x < 0 or comp.y < 0 or comp.x > w or comp.y > h:
                    violations.append({
                        "type": "out_of_bounds",
                        "ref": ref,
                        "message": f"{ref} at ({comp.x}, {comp.y}) is outside board ({w}x{h}mm)",
                    })

        # Check for track crossings/overlaps between different nets on same layer
        # Expand multi-point tracks into individual segments
        segments = []  # (x1, y1, x2, y2, net_id, net_name, layer)
        for track in self._tracks:
            points = track["points"]
            for k in range(len(points) - 1):
                segments.append((
                    points[k][0], points[k][1],
                    points[k + 1][0], points[k + 1][1],
                    track["net"], track["net_name"], track["layer"],
                ))

        for i in range(len(segments)):
            for j in range(i + 1, len(segments)):
                s1, s2 = segments[i], segments[j]
                if s1[4] == s2[4]:
                    continue  # same net
                if s1[6] != s2[6]:
                    continue  # different layers can cross freely
                pt = self._segments_intersect(
                    s1[0], s1[1], s1[2], s1[3],
                    s2[0], s2[1], s2[2], s2[3],
                )
                if pt:
                    violations.append({
                        "type": "crossing",
                        "nets": [s1[5], s2[5]],
                        "layer": s1[6],
                        "point": pt,
                        "message": (
                            f"{s1[5]} and {s2[5]} cross at "
                            f"({pt[0]:.2f}, {pt[1]:.2f}) on {s1[6]}"
                        ),
                    })

        return violations

    @staticmethod
    def _segments_intersect(x1a, y1a, x1b, y1b, x2a, y2a, x2b, y2b):
        """Check if two line segments intersect. Returns intersection point or None."""
        def cross(ox, oy, ax, ay, bx, by):
            return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

        d1 = cross(x2a, y2a, x2b, y2b, x1a, y1a)
        d2 = cross(x2a, y2a, x2b, y2b, x1b, y1b)
        d3 = cross(x1a, y1a, x1b, y1b, x2a, y2a)
        d4 = cross(x1a, y1a, x1b, y1b, x2b, y2b)

        # Proper intersection
        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            t = d1 / (d1 - d2)
            return (x1a + t * (x1b - x1a), y1a + t * (y1b - y1a))

        # Collinear overlap check
        def on_segment(px, py, ax, ay, bx, by):
            return (min(ax, bx) - 0.001 <= px <= max(ax, bx) + 0.001 and
                    min(ay, by) - 0.001 <= py <= max(ay, by) + 0.001)

        if abs(d1) < 0.001 and on_segment(x1a, y1a, x2a, y2a, x2b, y2b):
            return (x1a, y1a)
        if abs(d2) < 0.001 and on_segment(x1b, y1b, x2a, y2a, x2b, y2b):
            return (x1b, y1b)
        if abs(d3) < 0.001 and on_segment(x2a, y2a, x1a, y1a, x1b, y1b):
            return (x2a, y2a)
        if abs(d4) < 0.001 and on_segment(x2b, y2b, x1a, y1a, x1b, y1b):
            return (x2b, y2b)

        return None

    def placement_stats(self, netlist: dict[str, list[tuple[str, str]]] = None) -> dict:
        """Compute placement and routing efficiency metrics.

        Args:
            netlist: Optional net → [(ref, pin), ...] mapping. If provided,
                     enables ratsnest-based metrics (routing directness).
                     Without it, only geometry-based metrics are returned.

        Returns dict with:
            board_area_mm2:       Board outline area
            component_bbox_mm2:   Bounding box around all components
            compactness:          component_bbox / board_area (0-1, higher = tighter)
            total_track_length:   Sum of all routed track segment lengths (mm)
            total_ratsnest:       Sum of minimum spanning tree edges per net (mm)
            routing_directness:   ratsnest / track_length (0-1, higher = more direct)
            via_count:            Number of vias
            vias_per_net:         {net_name: count}
            layer_usage:          {layer: total_track_mm}
            per_net:              {net: {track_mm, ratsnest_mm, directness, vias}}
        """
        stats: dict = {}

        # ── Board area ──
        if self._board_outline:
            w, h = self._board_outline
            stats["board_area_mm2"] = round(w * h, 1)
        else:
            stats["board_area_mm2"] = None

        # ── Component bounding box ──
        if self._components:
            xs = [c.x for c in self._components.values()]
            ys = [c.y for c in self._components.values()]
            bbox_w = max(xs) - min(xs)
            bbox_h = max(ys) - min(ys)
            # Add ~2mm margin per side for component bodies
            bbox_w += 4.0
            bbox_h += 4.0
            stats["component_bbox_mm2"] = round(bbox_w * bbox_h, 1)
        else:
            stats["component_bbox_mm2"] = 0

        if stats["board_area_mm2"]:
            stats["compactness"] = round(
                stats["component_bbox_mm2"] / stats["board_area_mm2"], 3
            )
        else:
            stats["compactness"] = None

        # ── Track lengths per net and layer ──
        net_track_len: dict[str, float] = {}
        layer_usage: dict[str, float] = {}
        for track in self._tracks:
            net_name = track["net_name"]
            layer = track["layer"]
            seg_len = 0.0
            pts = track["points"]
            for i in range(len(pts) - 1):
                dx = pts[i + 1][0] - pts[i][0]
                dy = pts[i + 1][1] - pts[i][1]
                seg_len += math.hypot(dx, dy)
            net_track_len[net_name] = net_track_len.get(net_name, 0) + seg_len
            layer_usage[layer] = layer_usage.get(layer, 0) + seg_len

        stats["total_track_length"] = round(sum(net_track_len.values()), 2)
        stats["layer_usage"] = {k: round(v, 2) for k, v in layer_usage.items()}

        # ── Via count per net ──
        vias_per_net: dict[str, int] = {}
        for via in self._vias:
            # Reverse-lookup net name from net id
            net_id = via["net"]
            net_name = next(
                (name for name, nid in self._nets.items() if nid == net_id), ""
            )
            vias_per_net[net_name] = vias_per_net.get(net_name, 0) + 1
        stats["via_count"] = len(self._vias)
        stats["vias_per_net"] = vias_per_net

        # ── Ratsnest (requires netlist) ──
        # Compute minimum spanning tree length per net as the theoretical
        # minimum wirelength. This is the best any router could achieve
        # assuming Manhattan distance isn't required.
        net_ratsnest: dict[str, float] = {}
        if netlist:
            for net_name, nodes in netlist.items():
                pad_positions = []
                for ref, pin in nodes:
                    pos = self._pad_abs_position(ref, pin)
                    if pos:
                        pad_positions.append(pos)
                if len(pad_positions) >= 2:
                    net_ratsnest[net_name] = self._mst_length(pad_positions)

        stats["total_ratsnest"] = round(sum(net_ratsnest.values()), 2) if net_ratsnest else None

        if net_ratsnest and stats["total_track_length"] > 0:
            stats["routing_directness"] = round(
                sum(net_ratsnest.values()) / stats["total_track_length"], 3
            )
        else:
            stats["routing_directness"] = None

        # ── Per-net breakdown ──
        all_nets = set(net_track_len) | set(net_ratsnest) | set(vias_per_net)
        per_net = {}
        for net in sorted(all_nets):
            if not net:
                continue
            t = net_track_len.get(net, 0)
            r = net_ratsnest.get(net, 0)
            per_net[net] = {
                "track_mm": round(t, 2),
                "ratsnest_mm": round(r, 2) if r else None,
                "directness": round(r / t, 3) if (r and t > 0) else None,
                "vias": vias_per_net.get(net, 0),
            }
        stats["per_net"] = per_net

        # ── HPWL (Half-Perimeter Wirelength) per net ──
        # HPWL = half the bounding-box perimeter of all pads in a net.
        # Fast lower bound on wirelength; compare to MST for quality check.
        net_hpwl: dict[str, float] = {}
        net_bbox_aspect: dict[str, float] = {}
        if netlist:
            for net_name, nodes in netlist.items():
                pad_positions = []
                for ref, pin in nodes:
                    pos = self._pad_abs_position(ref, pin)
                    if pos:
                        pad_positions.append(pos)
                if len(pad_positions) >= 2:
                    xs = [p[0] for p in pad_positions]
                    ys = [p[1] for p in pad_positions]
                    w = max(xs) - min(xs)
                    h = max(ys) - min(ys)
                    net_hpwl[net_name] = w + h
                    # Aspect ratio: 1.0 = square bbox, higher = elongated
                    short = min(w, h) if min(w, h) > 0.001 else 0.001
                    net_bbox_aspect[net_name] = round(max(w, h) / short, 2)

        stats["hpwl_per_net"] = {k: round(v, 2) for k, v in net_hpwl.items()}
        stats["total_hpwl"] = round(sum(net_hpwl.values()), 2) if net_hpwl else None
        stats["net_bbox_aspect"] = net_bbox_aspect

        # ── Connection length distribution (percentiles) ──
        # Collect all individual track segment lengths to show distribution.
        all_seg_lengths: list[float] = []
        for track in self._tracks:
            pts = track["points"]
            for i in range(len(pts) - 1):
                dx = pts[i + 1][0] - pts[i][0]
                dy = pts[i + 1][1] - pts[i][1]
                seg = math.hypot(dx, dy)
                if seg > 0.001:
                    all_seg_lengths.append(seg)

        if all_seg_lengths:
            all_seg_lengths.sort()
            n_segs = len(all_seg_lengths)

            def _percentile(data, p):
                idx = (p / 100) * (len(data) - 1)
                lo = int(idx)
                hi = min(lo + 1, len(data) - 1)
                frac = idx - lo
                return data[lo] * (1 - frac) + data[hi] * frac

            stats["segment_length_distribution"] = {
                "count": n_segs,
                "min": round(all_seg_lengths[0], 2),
                "p25": round(_percentile(all_seg_lengths, 25), 2),
                "median": round(_percentile(all_seg_lengths, 50), 2),
                "p75": round(_percentile(all_seg_lengths, 75), 2),
                "max": round(all_seg_lengths[-1], 2),
                "mean": round(sum(all_seg_lengths) / n_segs, 2),
            }
        else:
            stats["segment_length_distribution"] = None

        # ── Track parallelism / crosstalk risk ──
        # Find parallel track segments on the same layer within a threshold
        # distance that belong to different nets. Score = count of risky pairs.
        PARALLEL_THRESHOLD_MM = 0.3  # minimum spacing for crosstalk concern
        ANGLE_THRESHOLD_DEG = 10.0  # segments within this angle are "parallel"
        parallel_risk_pairs = 0
        # Build list of (net, layer, x1, y1, x2, y2) segments
        segments: list[tuple[str, str, float, float, float, float]] = []
        for track in self._tracks:
            pts = track["points"]
            for i in range(len(pts) - 1):
                segments.append((
                    track["net_name"], track["layer"],
                    pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                ))
        for i in range(len(segments)):
            for j in range(i + 1, len(segments)):
                s1, s2 = segments[i], segments[j]
                # Same layer, different nets
                if s1[1] != s2[1] or s1[0] == s2[0]:
                    continue
                # Compute angles
                a1 = math.atan2(s1[5] - s1[3], s1[4] - s1[2])
                a2 = math.atan2(s2[5] - s2[3], s2[4] - s2[2])
                angle_diff = abs(math.degrees(a1 - a2)) % 180
                if angle_diff > 90:
                    angle_diff = 180 - angle_diff
                if angle_diff > ANGLE_THRESHOLD_DEG:
                    continue
                # Check minimum distance between midpoints
                mx1 = (s1[2] + s1[4]) / 2
                my1 = (s1[3] + s1[5]) / 2
                mx2 = (s2[2] + s2[4]) / 2
                my2 = (s2[3] + s2[5]) / 2
                dist = math.hypot(mx1 - mx2, my1 - my2)
                if dist < PARALLEL_THRESHOLD_MM + max(
                    math.hypot(s1[4] - s1[2], s1[5] - s1[3]),
                    math.hypot(s2[4] - s2[2], s2[5] - s2[3]),
                ) / 2:
                    # More precise: perpendicular distance from midpoint to line
                    # of other segment
                    dx = s2[4] - s2[2]
                    dy = s2[5] - s2[3]
                    seg_len = math.hypot(dx, dy)
                    if seg_len > 0.001:
                        perp_dist = abs(
                            dx * (s2[3] - my1) - dy * (s2[2] - mx1)
                        ) / seg_len
                        if perp_dist < PARALLEL_THRESHOLD_MM:
                            parallel_risk_pairs += 1

        stats["crosstalk_risk_pairs"] = parallel_risk_pairs

        # ── Layer balance ──
        # How evenly track length is distributed across layers.
        # 1.0 = perfectly balanced, 0.0 = all on one layer.
        if layer_usage and len(layer_usage) > 1:
            total_len = sum(layer_usage.values())
            if total_len > 0:
                ideal = total_len / len(layer_usage)
                imbalance = sum(abs(v - ideal) for v in layer_usage.values())
                stats["layer_balance"] = round(1.0 - imbalance / (2 * total_len), 3)
            else:
                stats["layer_balance"] = None
        else:
            stats["layer_balance"] = None if not layer_usage else 0.0

        # ── Congestion heatmap (grid-based) ──
        # Divide board into grid cells, count track segments crossing each cell.
        # Report max congestion and average.
        if self._board_outline:
            bw, bh = self._board_outline
            grid_size = 5.0  # mm per cell
            cols = max(1, int(bw / grid_size))
            rows = max(1, int(bh / grid_size))
            grid = [[0] * cols for _ in range(rows)]
            for track in self._tracks:
                pts = track["points"]
                for k in range(len(pts) - 1):
                    # Mark cells along this segment (sample points)
                    sx, sy = pts[k]
                    ex, ey = pts[k + 1]
                    seg_len = math.hypot(ex - sx, ey - sy)
                    steps = max(1, int(seg_len / (grid_size / 2)))
                    visited: set[tuple[int, int]] = set()
                    for s in range(steps + 1):
                        t = s / steps
                        px = sx + t * (ex - sx)
                        py = sy + t * (ey - sy)
                        c = min(int(px / grid_size), cols - 1)
                        r = min(int(py / grid_size), rows - 1)
                        if c >= 0 and r >= 0:
                            visited.add((r, c))
                    for r, c in visited:
                        grid[r][c] += 1

            all_cells = [grid[r][c] for r in range(rows) for c in range(cols)]
            max_cong = max(all_cells)
            avg_cong = sum(all_cells) / len(all_cells) if all_cells else 0
            stats["congestion"] = {
                "grid_size_mm": grid_size,
                "rows": rows,
                "cols": cols,
                "max_segments_per_cell": max_cong,
                "avg_segments_per_cell": round(avg_cong, 1),
                "hotspot_ratio": round(max_cong / avg_cong, 1) if avg_cong > 0 else None,
            }
        else:
            stats["congestion"] = None

        # ── Annular ring adequacy ──
        # Check that via annular ring (outer_radius - drill/2) meets minimum.
        # Default via outer diameter in KiCad is typically drill + 0.5mm.
        MIN_ANNULAR_RING_MM = 0.15  # typical minimum
        via_ring_issues = 0
        via_ring_sizes: list[float] = []
        for v in self._vias:
            drill = v.get("drill", 0.3)
            # KiCad default via size is drill + 0.5
            outer_d = v.get("size", drill + 0.5)
            ring = (outer_d - drill) / 2
            via_ring_sizes.append(round(ring, 3))
            if ring < MIN_ANNULAR_RING_MM:
                via_ring_issues += 1

        stats["annular_ring"] = {
            "min_required_mm": MIN_ANNULAR_RING_MM,
            "sizes_mm": via_ring_sizes,
            "violations": via_ring_issues,
        }

        # ── Edge clearance ──
        # Check how close components and vias are to board edges.
        MIN_EDGE_CLEARANCE_MM = 1.0
        edge_violations = 0
        min_clearance = float("inf")
        if self._board_outline:
            bw, bh = self._board_outline
            for comp in self._components.values():
                clearances = [comp.x, comp.y, bw - comp.x, bh - comp.y]
                mc = min(clearances)
                min_clearance = min(min_clearance, mc)
                if mc < MIN_EDGE_CLEARANCE_MM:
                    edge_violations += 1
            for v in self._vias:
                clearances = [v["x"], v["y"], bw - v["x"], bh - v["y"]]
                mc = min(clearances)
                min_clearance = min(min_clearance, mc)
                if mc < MIN_EDGE_CLEARANCE_MM:
                    edge_violations += 1

        stats["edge_clearance"] = {
            "min_required_mm": MIN_EDGE_CLEARANCE_MM,
            "min_actual_mm": round(min_clearance, 2) if min_clearance < float("inf") else None,
            "violations": edge_violations,
        }

        # ── Power pin proximity ──
        # For power nets, measure average distance from pads to their
        # nearest via on the same net. Lower = less IR drop.
        # Heuristic: a net is "power" if it has vias and its name looks like
        # a common power/ground rail (case-insensitive).
        _POWER_PATTERNS = {"vcc", "vdd", "gnd", "vss", "3v3", "5v", "12v",
                           "+5v", "+3.3v", "+12v", "pwr", "v+", "v-"}
        power_nets: set[str] = set()
        if netlist:
            for net_name in netlist:
                if net_name.lower() in _POWER_PATTERNS or any(
                    p in net_name.lower() for p in ("vcc", "vdd", "gnd", "vss", "pwr")
                ):
                    power_nets.add(net_name)
        power_proximity: dict[str, float] = {}
        if netlist:
            for net_name in power_nets:
                if net_name not in netlist:
                    continue
                # Collect via positions for this net
                net_id = self._nets.get(net_name)
                net_vias = [
                    (v["x"], v["y"]) for v in self._vias if v["net"] == net_id
                ]
                if not net_vias:
                    continue
                # Average distance from each pad to nearest via
                distances = []
                for ref, pin in netlist[net_name]:
                    pos = self._pad_abs_position(ref, pin)
                    if pos:
                        d = min(math.hypot(pos[0] - vx, pos[1] - vy)
                                for vx, vy in net_vias)
                        distances.append(d)
                if distances:
                    power_proximity[net_name] = round(
                        sum(distances) / len(distances), 2
                    )

        stats["power_pin_proximity_mm"] = power_proximity

        # ── Net detour factor (Manhattan-based) ──
        # Compare actual routed length to Manhattan distance between net endpoints.
        # Unlike routing_directness (uses MST Euclidean), this uses Manhattan
        # distance which better reflects rectilinear routing reality.
        net_manhattan: dict[str, float] = {}
        if netlist:
            for net_name, nodes in netlist.items():
                pad_positions = []
                for ref, pin in nodes:
                    pos = self._pad_abs_position(ref, pin)
                    if pos:
                        pad_positions.append(pos)
                if len(pad_positions) >= 2:
                    # Manhattan MST lower bound: sum of MST edges using Manhattan dist
                    pts = pad_positions
                    n_pts = len(pts)
                    if n_pts == 2:
                        net_manhattan[net_name] = (
                            abs(pts[0][0] - pts[1][0]) +
                            abs(pts[0][1] - pts[1][1])
                        )
                    else:
                        # Prim's with Manhattan distance
                        in_tree = [False] * n_pts
                        min_e = [float("inf")] * n_pts
                        min_e[0] = 0.0
                        total_m = 0.0
                        for _ in range(n_pts):
                            u = -1
                            for vi in range(n_pts):
                                if not in_tree[vi] and (u == -1 or min_e[vi] < min_e[u]):
                                    u = vi
                            in_tree[u] = True
                            total_m += min_e[u]
                            for vi in range(n_pts):
                                if not in_tree[vi]:
                                    d = (abs(pts[u][0] - pts[vi][0]) +
                                         abs(pts[u][1] - pts[vi][1]))
                                    if d < min_e[vi]:
                                        min_e[vi] = d
                        net_manhattan[net_name] = total_m

        if net_manhattan and stats["total_track_length"] > 0:
            total_manhattan = sum(net_manhattan.values())
            stats["manhattan_directness"] = round(
                total_manhattan / stats["total_track_length"], 3
            )
            stats["manhattan_per_net"] = {
                k: round(v, 2) for k, v in net_manhattan.items()
            }
        else:
            stats["manhattan_directness"] = None
            stats["manhattan_per_net"] = {}

        # ── Plane coverage ──
        # Copper pour / ground plane coverage. Since our board has no copper
        # zones/pours, this will report None. Tracked for awareness.
        # In a real board, this would sum zone polygon areas per layer.
        copper_zones = getattr(self, "_zones", [])
        if copper_zones:
            # Future: calculate polygon area per zone
            stats["plane_coverage"] = {
                "zone_count": len(copper_zones),
                "note": "Zone area calculation not yet implemented",
            }
        else:
            stats["plane_coverage"] = {
                "zone_count": 0,
                "coverage_pct": None,
                "note": "No copper zones/pours defined",
            }

        return stats

    def _pad_abs_position(self, ref: str, pad_num: str):
        """Get absolute (x, y) of a pad, accounting for rotation."""
        comp = self._components.get(ref)
        if not comp:
            return None
        for pad in comp.pads:
            if pad["num"] == pad_num:
                lx, ly = pad["local_x"], pad["local_y"]
                if comp.rotation:
                    rad = math.radians(-comp.rotation)
                    rx = lx * math.cos(rad) - ly * math.sin(rad)
                    ry = lx * math.sin(rad) + ly * math.cos(rad)
                    lx, ly = rx, ry
                return (comp.x + lx, comp.y + ly)
        return None

    @staticmethod
    def _mst_length(points: list[tuple[float, float]]) -> float:
        """Compute minimum spanning tree total length (Prim's algorithm)."""
        n = len(points)
        if n < 2:
            return 0.0
        in_tree = [False] * n
        min_edge = [float("inf")] * n
        min_edge[0] = 0.0
        total = 0.0
        for _ in range(n):
            # Pick cheapest vertex not yet in tree
            u = -1
            for v in range(n):
                if not in_tree[v] and (u == -1 or min_edge[v] < min_edge[u]):
                    u = v
            in_tree[u] = True
            total += min_edge[u]
            # Update neighbors
            for v in range(n):
                if not in_tree[v]:
                    d = math.hypot(
                        points[u][0] - points[v][0],
                        points[u][1] - points[v][1],
                    )
                    if d < min_edge[v]:
                        min_edge[v] = d
        return total

    def export_render_data(self, output_path: str, footprint_dir: str = None):
        """Export board data as JSON for drc_rules.py and scripts/render_pcb.py.

        The JSON contains all information needed to rebuild the board in-memory.
        `footprint_dir` is stored relative to the JSON file's directory so the
        file stays valid when the repo moves; readers resolve it the same way.
        """
        fp_dir = footprint_dir or getattr(self, "_footprint_dir", None)
        if fp_dir:
            fp_dir = os.path.relpath(
                Path(fp_dir).resolve(), Path(output_path).resolve().parent
            )

        data = {
            "footprint_dir": fp_dir,
            "outline": list(self._board_outline) if self._board_outline else None,
            "nets": {name: nid for name, nid in self._nets.items()},
            "components": [
                {
                    "ref": c.ref,
                    "footprint": c.footprint,
                    "value": c.value,
                    "x": c.x,
                    "y": c.y,
                    "rotation": c.rotation,
                    "pad_nets": {
                        p["num"]: p.get("net_name", "")
                        for p in c.pads
                    } if c.pads else {},
                }
                for c in self._components.values()
            ],
            "tracks": [
                {
                    "net": t["net_name"],
                    "points": t["points"],
                    "width": t["width"],
                    "layer": t["layer"],
                }
                for t in self._tracks
            ],
            "vias": [
                {
                    "net": v.get("net_name") or next(
                        (name for name, nid in self._nets.items() if nid == v["net"]),
                        "",
                    ),
                    "x": v["x"],
                    "y": v["y"],
                    "drill": v["drill"],
                }
                for v in self._vias
            ],
        }

        Path(output_path).write_text(json.dumps(data, indent=2))

    def save(self, output_path: str = None):
        """Save the modified board.

        For boards loaded from existing files, preserves original footprint data
        and appends new tracks/vias/outline. For boards created via new_board(),
        generates full content from scratch.
        """
        path = output_path or self.pcb_path

        if hasattr(self, "_raw_footprints"):
            # new_board() path — generate from scratch since we have raw footprints
            self._content = self._generate_pcb_content()
        else:
            # Existing PCB path — preserve original content, patch in new elements
            self._content = self._patch_existing_content()

        Path(path).write_text(self._content)

    def _patch_existing_content(self) -> str:
        """Patch existing PCB content: component positions are already updated via
        _update_component_position(). This method adds the board outline, new net
        declarations, tracks, and vias while preserving original footprint blocks.

        Boards generated by this module are treated as regenerable: everything after
        the last footprint (tracks/vias from an earlier save) is replaced. Any other
        board, e.g. one saved by KiCad, is only appended to, so its routing, zones,
        and graphics survive. Pad nets from set_pad_nets() are not written here.
        """
        content = self._content

        # Replace the outline instead of adding a second one
        if self._board_outline:
            content = _remove_edge_rects(content)

        spans = _footprint_spans(content)
        if spans and f'(generator "{_GENERATOR}")' in content[:300]:
            content = content[:spans[-1][1]]
        else:
            content = content[:content.rstrip().rfind(")")]
        content = content.rstrip() + "\n"

        # Declare nets this session introduced (numbered-net formats only)
        new_nets = sorted(
            (nid, name) for name, nid in self._nets.items()
            if nid and name not in self._declared_nets
        )
        if new_nets and not self._named_nets:
            decls = "".join(f"  (net {nid} {_quote(name)})\n" for nid, name in new_nets)
            last_decl = None
            for last_decl in re.finditer(r'^(?:  |\t)\(net\s+\d+\s[^\n]*$', content, re.MULTILINE):
                pass
            if last_decl:
                pos = last_decl.end() + 1
            elif spans:
                pos = content.rfind("\n", 0, _footprint_spans(content)[0][0]) + 1
            else:
                pos = len(content)
            content = content[:pos] + decls + content[pos:]

        def net_ref(net_id: int, net_name: str) -> str:
            return f"(net {_quote(net_name)})" if self._named_nets else f"(net {net_id})"

        lines = []

        # Board outline
        if self._board_outline:
            w, h = self._board_outline
            lines.append(f'  (gr_rect (start 0 0) (end {w} {h})')
            lines.append(f'    (stroke (width 0.05) (type default))')
            lines.append(f'    (fill none)')
            lines.append(f'    (layer "Edge.Cuts")')
            lines.append(f'    (uuid "{_gen_uuid()}")')
            lines.append(f'  )')

        # Tracks
        for track in self._tracks:
            points = track["points"]
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                lines.append(
                    f'  (segment (start {x1} {y1}) (end {x2} {y2}) '
                    f'(width {track["width"]}) (layer "{track["layer"]}") '
                    f'{net_ref(track["net"], track["net_name"])} (uuid "{_gen_uuid()}"))'
                )

        # Vias
        for via in self._vias:
            lines.append(
                f'  (via (at {via["x"]} {via["y"]}) (size 0.6) (drill {via["drill"]}) '
                f'(layers "F.Cu" "B.Cu") {net_ref(via["net"], via.get("net_name", ""))} '
                f'(uuid "{_gen_uuid()}"))'
            )

        content += "\n".join(lines) + "\n)\n"
        return content

    # ── PCB content generation ───────────────────────────────────────────────

    def _generate_pcb_content(self) -> str:
        """Generate complete .kicad_pcb file content as S-expression."""
        lines = []
        lines.append(f'(kicad_pcb (version 20240108) (generator "{_GENERATOR}") (generator_version "8.0")')
        lines.append("  (general")
        lines.append("    (thickness 1.6)")
        lines.append("    (legacy_teardrops no)")
        lines.append("  )")
        lines.append("")

        # Paper size
        lines.append('  (paper "A4")')
        lines.append("")

        # Layers — KiCad 8/9 layer numbering (from pcbnew.BOARD.Save())
        lines.append("  (layers")
        lines.append('    (0 "F.Cu" signal)')
        lines.append('    (2 "B.Cu" signal)')
        lines.append('    (9 "F.Adhes" user "F.Adhesive")')
        lines.append('    (11 "B.Adhes" user "B.Adhesive")')
        lines.append('    (13 "F.Paste" user)')
        lines.append('    (15 "B.Paste" user)')
        lines.append('    (5 "F.SilkS" user "F.Silkscreen")')
        lines.append('    (7 "B.SilkS" user "B.Silkscreen")')
        lines.append('    (1 "F.Mask" user)')
        lines.append('    (3 "B.Mask" user)')
        lines.append('    (17 "Dwgs.User" user "User.Drawings")')
        lines.append('    (19 "Cmts.User" user "User.Comments")')
        lines.append('    (21 "Eco1.User" user "User.Eco1")')
        lines.append('    (23 "Eco2.User" user "User.Eco2")')
        lines.append('    (25 "Edge.Cuts" user)')
        lines.append('    (27 "Margin" user)')
        lines.append('    (31 "F.CrtYd" user "F.Courtyard")')
        lines.append('    (29 "B.CrtYd" user "B.Courtyard")')
        lines.append('    (35 "F.Fab" user)')
        lines.append('    (33 "B.Fab" user)')
        lines.append("  )")
        lines.append("")

        # Setup
        lines.append("  (setup")
        lines.append("    (pad_to_mask_clearance 0)")
        lines.append("    (allow_soldermask_bridges_in_footprints no)")
        lines.append("    (tenting front back)")
        lines.append("    (pcbplotparams")
        lines.append("      (layerselection 0x00010fc_ffffffff)")
        lines.append("      (plot_on_all_layers_selection 0x0000000_00000000)")
        lines.append("    )")
        lines.append("  )")
        lines.append("")

        # Nets: every name registered through add_track(), add_via(), or set_pad_nets()
        lines.append('  (net 0 "")')
        for net_name, net_id in sorted(self._nets.items(), key=lambda kv: kv[1]):
            if net_id:
                lines.append(f"  (net {net_id} {_quote(net_name)})")
        lines.append("")

        # Board outline
        if self._board_outline:
            w, h = self._board_outline
            lines.append(f'  (gr_rect (start 0 0) (end {w} {h})')
            lines.append(f'    (stroke (width 0.05) (type default))')
            lines.append(f'    (fill none)')
            lines.append(f'    (layer "Edge.Cuts")')
            lines.append(f'    (uuid "{_gen_uuid()}")')
            lines.append(f'  )')
            lines.append("")

        # Footprints
        for ref, comp in self._components.items():
            fp_content = self._raw_footprints.get(ref) if hasattr(self, "_raw_footprints") else None
            if fp_content:
                lines.append(self._transform_footprint(fp_content, comp))
            else:
                lines.append(self._generate_placeholder_footprint(comp))
            lines.append("")

        # Tracks
        for track in self._tracks:
            points = track["points"]
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                lines.append(
                    f'  (segment (start {x1} {y1}) (end {x2} {y2}) '
                    f'(width {track["width"]}) (layer "{track["layer"]}") '
                    f'(net {track["net"]}) (uuid "{_gen_uuid()}"))'
                )

        # Vias
        for via in self._vias:
            lines.append(
                f'  (via (at {via["x"]} {via["y"]}) (size 0.6) (drill {via["drill"]}) '
                f'(layers "F.Cu" "B.Cu") (net {via["net"]}) (uuid "{_gen_uuid()}"))'
            )

        lines.append(")")
        return "\n".join(lines)

    def _transform_footprint(self, kicad_mod_content: str, comp: ComponentInfo) -> str:
        """Transform a .kicad_mod file content into a footprint block positioned at comp's location."""
        # The .kicad_mod starts with (footprint "name" ...) — we need to:
        # 1. Add/update (at x y rotation)
        # 2. Update reference text
        # 3. Assign net IDs to pads based on pad_net_map (set via set_pad_nets())

        content = kicad_mod_content.strip()

        # Convert KiCad 5 format (module) to KiCad 8 format (footprint)
        if content.startswith("(module"):
            content = "(footprint" + content[len("(module"):]

        # Pad and text angles inside a placed footprint are stored in board
        # orientation, so they turn with the footprint (library files have no
        # footprint-level (at ...) yet, so every (at ...) here is a pad or text).
        content = _rotate_inner_angles(content, comp.rotation, skip_first=False)

        # Add UUIDs to footprint, pads, and fp_text if missing (KiCad 8 requirement)
        # Footprint-level UUID: insert after first line if missing
        if "(uuid " not in content.split("\n")[0]:
            first_nl = content.index("\n")
            content = content[:first_nl] + f'\n    (uuid "{_gen_uuid()}")' + content[first_nl:]
        # Pad UUIDs
        content = re.sub(
            r'(\(pad\s+"?\w+"?\s+\w+\s+\w+\s+\(at[^)]+\)\s+\(size[^)]+\)\s+\(layers[^)]+\))(\))',
            lambda m: m.group(1) + f'\n      (uuid "{_gen_uuid()}")' + m.group(2),
            content,
        )
        # fp_text UUIDs
        content = re.sub(
            r'(\(fp_text\s+\w+\s+"[^"]*"\s+\(at[^)]+\)\s+\(layer\s+[^)]+\)\s*\n\s*\(effects[^)]+\)(?:\s+hide)?\))(\s*\))',
            lambda m: m.group(1)[:-1] + f'\n      (uuid "{_gen_uuid()}")' + m.group(1)[-1:] + m.group(2),
            content,
        )

        # Insert (at x y) after the first line
        rot_str = f" {comp.rotation}" if comp.rotation else ""
        at_line = f"    (at {comp.x} {comp.y}{rot_str})"

        # Find the first newline after (footprint and insert at
        first_nl = content.index("\n")
        # Check if there's already an (at ...) line
        if "(at " in content.split("\n")[1] if "\n" in content else False:
            content = re.sub(
                r'\(at\s+[\d.+-]+\s+[\d.+-]+(?:\s+[\d.+-]+)?\)',
                f'(at {comp.x} {comp.y}{rot_str})',
                content,
                count=1,
            )
        else:
            content = content[:first_nl] + "\n" + at_line + content[first_nl:]

        # Update reference designator (may be quoted "REF**" or unquoted REF**)
        content = re.sub(
            r'(\(fp_text\s+reference\s+)"?[^"\s)]*"?',
            rf'\1"{comp.ref}"',
            content,
            count=1,
        )

        # Update value (may be quoted or unquoted)
        content = re.sub(
            r'(\(fp_text\s+value\s+)"?[^"\s)]*"?',
            rf'\1"{comp.value}"',
            content,
            count=1,
        )

        # Inject net assignments into pads (KiCad 5 one-line pads or KiCad 8+ blocks)
        pad_nets = getattr(self, "_pad_net_map", {}).get(comp.ref, {})
        if pad_nets:
            out, pos = [], 0
            for m in re.finditer(r'\(pad\s+"?([^"\s)]+)"?', content):
                net_name = pad_nets.get(m.group(1), "")
                if m.start() < pos or not net_name:
                    continue
                end = _sexp_end(content, m.start())
                pad_block = re.sub(r'\s*\(net\s[^()]*\)', "", content[m.start():end])
                net = f"(net {self._net_id(net_name)} {_quote(net_name)})"
                out.append(content[pos:m.start()])
                out.append(pad_block[:-1].rstrip() + f"\n\t\t{net}\n\t)")
                pos = end
            out.append(content[pos:])
            content = "".join(out)

        # Also update (property "Reference"/"Value" ...) if present (KiCad 8+ format)
        content = re.sub(
            r'(\(property "Reference" )"[^"]*"',
            rf'\1"{comp.ref}"',
            content,
            count=1,
        )
        content = re.sub(
            r'(\(property "Value" )"(?:[^"\\]|\\.)*"',
            lambda m: m.group(1) + _quote(comp.value),
            content,
            count=1,
        )

        # Indent the whole block
        indented = "\n".join("  " + line for line in content.split("\n"))
        return indented

    def _generate_placeholder_footprint(self, comp: ComponentInfo) -> str:
        """Generate a minimal placeholder footprint when no .kicad_mod file is available."""
        uid = _gen_uuid()
        rot_str = f" {comp.rotation}" if comp.rotation else ""
        return f"""  (footprint "{comp.footprint}"
    (at {comp.x} {comp.y}{rot_str})
    (uuid "{uid}")
    (fp_text reference "{comp.ref}" (at 0 -2) (layer "F.SilkS")
      (effects (font (size 1 1) (thickness 0.15)))
      (uuid "{_gen_uuid()}")
    )
    (fp_text value "{comp.value}" (at 0 2) (layer "F.Fab")
      (effects (font (size 1 1) (thickness 0.15)))
      (uuid "{_gen_uuid()}")
    )
    (pad "1" smd rect (at -1 0) (size 1 1.2) (layers "F.Cu" "F.Paste" "F.Mask")
      (net 0 "")
      (uuid "{_gen_uuid()}")
    )
    (pad "2" smd rect (at 1 0) (size 1 1.2) (layers "F.Cu" "F.Paste" "F.Mask")
      (net 0 "")
      (uuid "{_gen_uuid()}")
    )
  )"""
