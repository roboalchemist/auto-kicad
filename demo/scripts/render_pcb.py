#!/usr/bin/env python3
"""
Render a colored PCB image from render_data.json.

Builds the board in-memory via the pcbnew API (bypasses LoadBoard() which
fails on our KiCad 5/8 format files), exports per-layer SVGs, then
subprocesses system Python with cairosvg + Pillow for rasterization and
compositing.

  F.Cu     → red   (50% opacity)
  B.Cu     → blue  (50% opacity)
  F.SilkS  → dark gray (80% opacity)
  F.Fab    → dark gray (80% opacity)
  Edge.Cuts→ black
  Vias     → gold annular rings with white drill holes

Must be run with KiCad's Python (which bundles pcbnew).
System Python must have cairosvg and Pillow installed.

Usage:
    $KICAD_PYTHON scripts/render_pcb.py render_data.json [-o blinker_render.png] [--dpi 600]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pcbnew


# ── pcbnew board builder ────────────────────────────────────────────────────

def build_board(data):
    """Build a pcbnew.BOARD in-memory from render_data.json contents."""
    board = pcbnew.BOARD()

    net_map = {}
    for name, nid in data.get("nets", {}).items():
        ni = pcbnew.NETINFO_ITEM(board, name, nid)
        board.Add(ni)
        net_map[name] = ni

    fp_dir = data.get("footprint_dir")
    if not fp_dir:
        print("Warning: render data has no footprint_dir; drawing components without pads",
              file=sys.stderr)

    missing = []
    for comp in data.get("components", []):
        if not _add_footprint(board, comp, fp_dir, net_map):
            if fp_dir:
                missing.append(f"{comp['ref']} ({comp['footprint']})")
                continue
            fp = pcbnew.FOOTPRINT(board)
            fp.SetReference(comp["ref"])
            fp.SetValue(comp.get("value", ""))
            _set_pos(fp, comp)
            board.Add(fp)
    if missing:
        raise SystemExit(f"Error: footprints not found under {fp_dir}: {', '.join(missing)}")

    for t in data.get("tracks", []):
        layer = _layer_id(t["layer"])
        ni = net_map.get(t.get("net", ""))
        width = pcbnew.FromMM(t.get("width", 0.25))
        pts = t["points"]
        for i in range(len(pts) - 1):
            seg = pcbnew.PCB_TRACK(board)
            seg.SetStart(_vec(pts[i]))
            seg.SetEnd(_vec(pts[i + 1]))
            seg.SetWidth(width)
            seg.SetLayer(layer)
            if ni:
                seg.SetNet(ni)
            board.Add(seg)

    for v in data.get("vias", []):
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(_vec([v["x"], v["y"]]))
        via.SetDrill(pcbnew.FromMM(v.get("drill", 0.3)))
        via.SetWidth(pcbnew.FromMM(0.6))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        net_name = v.get("net", "")
        if net_name in net_map:
            via.SetNet(net_map[net_name])
        board.Add(via)

    outline = data.get("outline")
    if outline:
        w, h = pcbnew.FromMM(outline[0]), pcbnew.FromMM(outline[1])
        corners = [(0, 0), (w, 0), (w, h), (0, h)]
        for i in range(4):
            seg = pcbnew.PCB_SHAPE(board)
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(pcbnew.VECTOR2I(*corners[i]))
            seg.SetEnd(pcbnew.VECTOR2I(*corners[(i + 1) % 4]))
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(pcbnew.FromMM(0.05))
            board.Add(seg)

    return board


def _add_footprint(board, comp, fp_dir, net_map):
    """Try to load a real .kicad_mod footprint. Returns True on success."""
    if not fp_dir:
        return False
    fp_name = comp["footprint"].split(":")[-1] if ":" in comp["footprint"] else comp["footprint"]

    candidates = [
        Path(fp_dir) / f"{fp_name}.kicad_mod",
        Path(fp_dir) / "footprints.pretty" / f"{fp_name}.kicad_mod",
    ]
    candidates.extend(Path(fp_dir).rglob(f"{fp_name}.kicad_mod"))

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            loaded = pcbnew.FootprintLoad(str(candidate.parent), fp_name)
        except Exception:
            continue
        if not loaded:
            continue
        loaded.SetReference(comp["ref"])
        loaded.SetValue(comp.get("value", ""))
        _set_pos(loaded, comp)
        pad_nets = comp.get("pad_nets", {})
        for pad in loaded.Pads():
            net_name = pad_nets.get(pad.GetName(), "")
            if net_name in net_map:
                pad.SetNet(net_map[net_name])
        board.Add(loaded)
        return True
    return False


def _set_pos(fp, comp):
    fp.SetPosition(_vec([comp["x"], comp["y"]]))
    if comp.get("rotation"):
        fp.SetOrientationDegrees(comp["rotation"])


def _vec(pt):
    return pcbnew.VECTOR2I(pcbnew.FromMM(pt[0]), pcbnew.FromMM(pt[1]))


_LAYER_MAP = {
    "F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu,
    "F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS,
    "F.Fab": pcbnew.F_Fab, "B.Fab": pcbnew.B_Fab,
    "Edge.Cuts": pcbnew.Edge_Cuts,
    "F.Mask": pcbnew.F_Mask, "B.Mask": pcbnew.B_Mask,
    "F.Paste": pcbnew.F_Paste, "B.Paste": pcbnew.B_Paste,
    "F.CrtYd": pcbnew.F_CrtYd, "B.CrtYd": pcbnew.B_CrtYd,
}


def _layer_id(name):
    return _LAYER_MAP.get(name, pcbnew.F_Cu)


# ── SVG export ──────────────────────────────────────────────────────────────

LAYERS = [
    ("layer_edge", pcbnew.Edge_Cuts, "black", 1.0),
    ("layer_fab", pcbnew.F_Fab, "#333333", 0.8),
    ("layer_silk", pcbnew.F_SilkS, "#333333", 0.8),
    ("layer_bcu", pcbnew.B_Cu, "blue", 0.5),
    ("layer_fcu", pcbnew.F_Cu, "red", 0.5),
]


def export_layer_svg(board, layer_id, output_path):
    """Export a single layer as SVG using pcbnew plot controller."""
    plot_ctrl = pcbnew.PLOT_CONTROLLER(board)
    opts = plot_ctrl.GetPlotOptions()
    opts.SetOutputDirectory(str(Path(output_path).parent))
    opts.SetPlotFrameRef(False)
    opts.SetAutoScale(False)
    opts.SetScale(1.0)
    opts.SetMirror(False)
    opts.SetUseGerberAttributes(False)
    opts.SetPlotReference(True)
    opts.SetPlotValue(True)

    stem = Path(output_path).stem
    plot_ctrl.OpenPlotfile(stem, pcbnew.PLOT_FORMAT_SVG, "")
    plot_ctrl.SetLayer(layer_id)
    plot_ctrl.PlotLayer()
    plot_ctrl.ClosePlot()

    # pcbnew writes e.g. "-layer_edge.svg" (dash prefix + layer suffix).
    # Find and rename to our target.
    outdir = Path(output_path).parent
    target = Path(output_path)
    for f in outdir.glob(f"*{stem}*.svg"):
        if f != target:
            f.rename(target)
            break


# ── Image compositing (runs in system Python subprocess) ────────────────────

# This script is sent to system python3 via subprocess. It uses cairosvg for
# SVG→PNG and Pillow for colorization, compositing, via drawing, and trimming.
_COMPOSITE_SCRIPT = textwrap.dedent(r'''
import json
import re
import sys
from pathlib import Path

import cairosvg
from PIL import Image, ImageColor, ImageDraw


def svg_page_size(svg_path):
    """Read SVG viewBox to get page dimensions in mm."""
    content = Path(svg_path).read_text()[:2000]
    m = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', content)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 297.0, 210.0


def rasterize_svg(svg_path, dpi):
    """Rasterize SVG to RGBA PIL Image."""
    # cairosvg uses 96 DPI by default; scale factor = dpi/96
    png_bytes = cairosvg.svg2png(url=str(Path(svg_path).resolve()), scale=dpi / 96.0)
    from io import BytesIO
    return Image.open(BytesIO(png_bytes)).convert("RGBA")


def colorize(img, color_str, opacity):
    """Recolor all non-transparent pixels to `color_str` at `opacity`."""
    r, g, b = ImageColor.getrgb(color_str)
    # Split into channels
    sr, sg, sb, sa = img.split()
    # Replace RGB with solid color
    solid = Image.new("L", img.size, r)
    sr = solid
    solid = Image.new("L", img.size, g)
    sg = solid
    solid = Image.new("L", img.size, b)
    sb = solid
    # Scale alpha by opacity
    sa = sa.point(lambda a: int(a * opacity))
    return Image.merge("RGBA", (
        Image.new("L", img.size, r),
        Image.new("L", img.size, g),
        Image.new("L", img.size, b),
        sa,
    ))


def draw_vias(canvas, vias, page_mm):
    """Draw gold annular rings with white drill holes onto canvas."""
    if not vias:
        return
    page_w, page_h = page_mm
    px_per_mm_x = canvas.width / page_w
    px_per_mm_y = canvas.height / page_h
    draw = ImageDraw.Draw(canvas)

    for v in vias:
        cx = v["x"] * px_per_mm_x
        cy = v["y"] * px_per_mm_y
        ring_r = 0.3 * px_per_mm_x     # 0.6mm outer / 2
        drill_r = (v.get("drill", 0.3) / 2) * px_per_mm_x

        # Gold annular ring
        draw.ellipse(
            [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
            fill=(255, 215, 0, 255), outline=(184, 134, 11, 255), width=1,
        )
        # White drill hole
        draw.ellipse(
            [cx - drill_r, cy - drill_r, cx + drill_r, cy + drill_r],
            fill=(255, 255, 255, 255),
        )


def trim_and_border(img, border=20):
    """Trim transparent/white edges, add white border."""
    # Find bounding box of non-white content
    bg = Image.new(img.mode, img.size, (255, 255, 255, 255))
    diff = Image.composite(img, bg, img.split()[3] if img.mode == "RGBA" else None)
    # Convert to check for non-white pixels
    gray = diff.convert("L")
    bbox = gray.point(lambda x: 0 if x >= 253 else 255).getbbox()
    if bbox:
        img = img.crop(bbox)
    # Add border
    bordered = Image.new("RGBA", (img.width + 2*border, img.height + 2*border), (255, 255, 255, 255))
    bordered.paste(img, (border, border), img)
    return bordered


def main():
    # Args: json_str, output_path, dpi, layer1_svg, layer1_color, layer1_opacity, ...
    args = sys.argv[1:]
    json_path = args[0]
    output_path = args[1]
    dpi = int(args[2])

    data = json.loads(Path(json_path).read_text())

    # Parse layer triples: svg_path, color, opacity
    layer_args = args[3:]
    layers = []
    for i in range(0, len(layer_args), 3):
        layers.append((layer_args[i], layer_args[i+1], float(layer_args[i+2])))

    # Determine SVG page size from first available SVG
    page_mm = svg_page_size(layers[0][0])

    # Rasterize and colorize each layer
    colored = []
    for svg_path, color, opacity in layers:
        name = Path(svg_path).stem
        print(f"  {name} -> {color} ({opacity*100:.0f}%)")
        img = rasterize_svg(svg_path, dpi)
        img = colorize(img, color, opacity)
        colored.append(img)

    # Composite onto white background
    print("  Compositing...")
    w, h = colored[0].size
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    for layer in colored:
        canvas = Image.alpha_composite(canvas, layer)

    # Draw vias
    vias = data.get("vias", [])
    if vias:
        print(f"  Drawing {len(vias)} vias...")
        draw_vias(canvas, vias, page_mm)

    # Trim and border
    print("  Trimming...")
    canvas = trim_and_border(canvas)

    # Save
    canvas.convert("RGB").save(output_path, dpi=(dpi, dpi))
    print(f"  Saved: {output_path}")


if __name__ == "__main__":
    main()
''')


def run_composite(json_path, svg_layers, output_path, dpi):
    """Subprocess system Python to composite SVGs into final PNG.

    svg_layers: list of (svg_path, color, opacity) tuples.
    """
    # Build args: json_path, output, dpi, then layer triples
    args = [json_path, output_path, str(dpi)]
    for svg_path, color, opacity in svg_layers:
        args.extend([svg_path, color, str(opacity)])

    # Find system Python (not KiCad's)
    sys_python = shutil.which("python3")
    if not sys_python or "KiCad" in sys_python:
        # Fall back to common locations
        for p in ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]:
            if Path(p).exists():
                sys_python = p
                break

    import os
    env = os.environ.copy()
    # Ensure cairocffi can find Homebrew's libcairo
    brew_lib = "/opt/homebrew/lib"
    if Path(brew_lib).exists():
        existing = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        env["DYLD_FALLBACK_LIBRARY_PATH"] = f"{brew_lib}:{existing}" if existing else brew_lib

    r = subprocess.run(
        [sys_python, "-c", _COMPOSITE_SCRIPT] + args,
        capture_output=True, text=True, env=env,
    )
    # Forward stdout/stderr
    if r.stdout:
        print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise RuntimeError(f"Compositing failed (exit {r.returncode})")


# ── main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Render colored PCB image from render_data.json"
    )
    parser.add_argument("json_file", help="Path to render_data.json")
    parser.add_argument("-o", "--output", default="blinker_render.png",
                        help="Output PNG (default: blinker_render.png)")
    parser.add_argument("--dpi", type=int, default=600, help="Render DPI")
    parser.add_argument("--keep-svg", action="store_true",
                        help="Keep intermediate SVGs (written next to output)")
    args = parser.parse_args()

    data = json.loads(Path(args.json_file).read_text())

    # A relative footprint_dir is relative to the JSON file, not the CWD
    fp_dir = data.get("footprint_dir")
    if fp_dir:
        fp_path = Path(fp_dir)
        if not fp_path.is_absolute():
            fp_path = Path(args.json_file).resolve().parent / fp_path
        if not fp_path.is_dir():
            raise SystemExit(f"Error: footprint_dir {fp_dir!r} does not exist (resolved to {fp_path})")
        data["footprint_dir"] = str(fp_path)

    # Work in a temp dir so intermediates don't litter the project
    tmpdir = tempfile.mkdtemp(prefix="pcb_render_")
    try:
        _render(data, args, tmpdir)
    finally:
        if not args.keep_svg:
            shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            print(f"SVGs kept in {tmpdir}")


def _render(data, args, tmpdir):
    print("Building board from JSON...")
    board = build_board(data)

    # Export per-layer SVGs
    svg_layers = []
    for stem, layer_id, color, opacity in LAYERS:
        svg = str(Path(tmpdir) / f"{stem}.svg")
        print(f"  Exporting {stem}.svg...")
        export_layer_svg(board, layer_id, svg)
        svg_layers.append((svg, color, opacity))

    # Copy SVGs next to output if requested
    if args.keep_svg:
        outdir = Path(args.output).parent
        for (svg, _, _), (stem, _, _, _) in zip(svg_layers, LAYERS):
            shutil.copy2(svg, outdir / f"{stem}.svg")

    # Composite via system Python (cairosvg + Pillow)
    print(f"Compositing {len(svg_layers)} layers at {args.dpi} DPI...")
    run_composite(
        str(Path(args.json_file).resolve()),
        svg_layers,
        str(Path(args.output).resolve()),
        args.dpi,
    )
    print(f"Done: {args.output}")


if __name__ == "__main__":
    main()
