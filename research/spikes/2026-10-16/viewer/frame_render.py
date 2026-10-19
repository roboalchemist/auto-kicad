"""Frame a board region by mm coordinates with kicad-cli pcb render, then check the mapping.

Empirical camera model (KiCad 10.0.3, orthographic, --side top|bottom, no --rotate):
  visible height at zoom 1 = K * max(board_w, board_h) of the *requested* -h, K = 1.0355
  px_per_mm = zoom * H_req / (K * maxdim)
  output image center = look-at point = board_center + pivot (pivot in cm, +X right, +Y up = -PCB y)
  bottom view mirrors X.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

KC = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
HERE = Path(__file__).parent
K = 1.0355


def frame(board, items, x, y, view_h_mm, out, w=1600, h=900, side="top", quality="basic", extra=()):
    ex, ey, ew, eh = items["edge_bbox_mm"]
    bw, bh = ew - 0.05, eh - 0.05  # strip Edge.Cuts stroke width
    cx, cy = ex + 0.025 + bw / 2, ey + 0.025 + bh / 2
    maxdim = max(bw, bh)
    zoom = K * maxdim / view_h_mm
    pivot = ((x - cx) / 10.0, (cy - y) / 10.0, 0.0)
    cmd = [KC, "pcb", "render", "-o", str(out), "-w", str(w), "-h", str(h), "--side", side,
           "--quality", quality, "--zoom", f"{zoom:.4f}",
           "--pivot", f"{pivot[0]:.4f},{pivot[1]:.4f},0", *extra, str(board)]
    t0 = time.time()
    subprocess.run(cmd, check=True, capture_output=True)
    dt = time.time() - t0
    im = Image.open(out).convert("RGBA")
    W, H = im.size
    s = h / view_h_mm  # px per mm (requested height drives scale)
    sign = -1 if side == "bottom" else 1

    def to_px(px_mm, py_mm):
        return (W / 2 + sign * (px_mm - x) * s, H / 2 + (py_mm - y) * s)

    return cmd, dt, im, to_px, s


if __name__ == "__main__":
    items = json.load(open(HERE / "items_k10.json"))
    board = HERE / "blinker_k10.kicad_pcb"
    for name, x, y, vh, side, q in [
        ("u1_10mm_basic", 9, 10, 10, "top", "basic"),
        ("u1_10mm_high", 9, 10, 10, "top", "high"),
        ("u1_6mm_basic", 9, 10, 6, "top", "basic"),
        ("d1_6mm_basic", 19, 16, 6, "top", "basic"),
        ("bvia_5mm_bottom", 12.305, 12.57, 5, "bottom", "basic"),
    ]:
        out = HERE / "renders" / f"frame_{name}.png"
        cmd, dt, im, to_px, s = frame(board, items, x, y, vh, out, side=side, quality=q)
        print(f"\n{name}: {dt:.2f}s size={im.size} px/mm={s:.1f}")
        print("  cmd:", " ".join(cmd[3:-1]))
        pts = [p for p in items["pads"]] if side == "top" else [dict(v, ref="via", num="") for v in items["vias"]]
        for p in pts:
            u, v = to_px(p["x"], p["y"])
            if 0 <= u < im.size[0] and 0 <= v < im.size[1]:
                print(f"  {p['ref']}.{p['num']:>2} ({p['x']:.3f},{p['y']:.3f}) -> px ({u:.0f},{v:.0f}) rgba={im.getpixel((int(u), int(v)))}")
