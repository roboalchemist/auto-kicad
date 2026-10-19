"""Dump footprint/pad/track/via geometry + UUIDs (run with KiCad's Python)."""
import json
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
mm = pcbnew.ToMM
out = {"footprints": [], "pads": [], "tracks": [], "vias": []}
bb = board.GetBoardEdgesBoundingBox()
out["edge_bbox_mm"] = [mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight())]
for fp in board.GetFootprints():
    p = fp.GetPosition()
    fbb = fp.GetBoundingBox(False)
    out["footprints"].append({
        "ref": fp.GetReference(), "uuid": fp.m_Uuid.AsString(),
        "x": mm(p.x), "y": mm(p.y), "rot": fp.GetOrientationDegrees(),
        "layer": fp.GetLayerName(),
        "bbox": [mm(fbb.GetX()), mm(fbb.GetY()), mm(fbb.GetWidth()), mm(fbb.GetHeight())],
    })
    for pad in fp.Pads():
        q = pad.GetPosition()
        sz = pad.GetSize(pcbnew.F_Cu) if hasattr(pcbnew, "F_Cu") else pad.GetSize()
        out["pads"].append({
            "ref": fp.GetReference(), "num": pad.GetNumber(), "uuid": pad.m_Uuid.AsString(),
            "net": pad.GetNetname(), "x": mm(q.x), "y": mm(q.y),
            "w": mm(sz.x), "h": mm(sz.y), "rot": pad.GetOrientationDegrees(),
            "shape": pad.ShowPadShape(pcbnew.F_Cu),
        })
for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA":
        q = t.GetPosition()
        out["vias"].append({"uuid": t.m_Uuid.AsString(), "net": t.GetNetname(), "x": mm(q.x), "y": mm(q.y)})
    else:
        s, e = t.GetStart(), t.GetEnd()
        out["tracks"].append({
            "uuid": t.m_Uuid.AsString(), "net": t.GetNetname(), "layer": t.GetLayerName(),
            "x1": mm(s.x), "y1": mm(s.y), "x2": mm(e.x), "y2": mm(e.y), "w": mm(t.GetWidth()),
        })
json.dump(out, open(sys.argv[2], "w"), indent=1)
print("footprints", len(out["footprints"]), "pads", len(out["pads"]), "tracks", len(out["tracks"]),
      "vias", len(out["vias"]), "edge", out["edge_bbox_mm"])
