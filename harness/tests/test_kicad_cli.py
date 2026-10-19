"""kicad-cli wrappers: DRC normalization, board-area SVG export, stats."""

from __future__ import annotations

import re

import pytest

from _engine_support import board, by_ref, engine, engine_config, fixture_index, pad  # noqa: F401
from kicad_harness.engine import kicad_cli
from kicad_harness.engine.client import EngineError

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def viewbox(svg: str) -> list[float]:
    return [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]


def test_drc_clean_board(board, engine_config):
    report = kicad_cli.drc(board, config=engine_config)
    assert report == {"counts": {"errors": 0, "warnings": 0, "unconnected": 0}, "violations": [], "unconnected": []}
    assert not board.with_suffix(".kicad_prl").exists()  # kicad-cli's side file is cleaned up


def test_drc_broken_board(engine, board, engine_config, fixture_index):
    engine.move_footprint(board, "R3", 9, 10)  # straight onto U1 and its tracks
    report = kicad_cli.drc(board, config=engine_config)
    counts = report["counts"]
    assert counts["errors"] > 0 and counts["unconnected"] > 0
    assert counts["errors"] == sum(v["severity"] == "error" for v in report["violations"])
    assert counts["unconnected"] == len(report["unconnected"])
    types = {v["type"] for v in report["violations"]}
    assert "shorting_items" in types
    for entry in report["violations"] + report["unconnected"]:
        assert set(entry) == {"type", "severity", "description", "items"}
        for item in entry["items"]:
            assert set(item) == {"uuid", "description", "x", "y"}
            assert UUID.match(item["uuid"])
            assert isinstance(item["x"], float) and isinstance(item["y"], float)
    r3_pads = {pad(fixture_index, "R3", n)["uuid"] for n in ("1", "2")}
    short = [v for v in report["violations"] if v["type"] == "shorting_items"]
    assert any(i["uuid"] in r3_pads for v in short for i in v["items"])
    hit = next(i for v in short for i in v["items"] if i["uuid"] in r3_pads)
    assert 7.5 < hit["x"] < 10.5 and 9.5 < hit["y"] < 10.5  # R3 now sits at (9, 10)


def test_normalize_drc_counts():
    raw = {"coordinate_units": "mm",
           "violations": [
               {"type": "clearance", "severity": "error", "description": "d", "items": [
                   {"uuid": "u", "description": "x", "pos": {"x": 1.0, "y": 2.0}}]},
               {"type": "silk_overlap", "severity": "warning", "description": "w", "items": []},
               {"type": "clearance", "severity": "exclusion", "description": "excluded", "items": []}],
           "unconnected_items": [{"type": "unconnected_items", "severity": "error", "description": "m", "items": []}],
           "schematic_parity": [{"type": "missing_footprint", "severity": "warning", "description": "p", "items": []}]}
    out = kicad_cli.normalize_drc(raw)
    assert out["counts"] == {"errors": 1, "warnings": 2, "unconnected": 1}
    assert out["violations"][0]["items"] == [{"uuid": "u", "description": "x", "x": 1.0, "y": 2.0}]
    with pytest.raises(EngineError):
        kicad_cli.normalize_drc({"coordinate_units": "in"})


def test_export_svg_units_and_origin(engine, board, engine_config, tmp_path):
    svg = kicad_cli.export_svg(board, ["F.Cu", "F.Mask", "F.SilkS", "Edge.Cuts"], tmp_path / "f.svg",
                               config=engine_config).read_text()
    assert 'width="24.9936mm"' in svg and 'height="19.9898mm"' in svg  # mm, page rounded down to mils
    assert viewbox(svg) == [0, 0, 24.9936, 19.9898]
    assert "M 10.7050,15.8250" in svg  # C1 pad 1 corner: origin is the outline's top-left (0, 0)
    # U1's oval mask openings are strokes; they get the 0.4 opacity of the other mask shapes.
    assert "stroke:#D864FF; stroke-width:0.5880; stroke-opacity:0.4" in svg
    assert "stroke:#D864FF; stroke-width:0.5880; stroke-opacity:1" not in svg
    assert not board.with_suffix(".kicad_prl").exists()

    # Move the outline: the SVG origin follows edge_bbox's top-left.
    engine.set_outline(board, 25, 20, x=3, y=2)
    assert engine.index(board)["board"]["edge_bbox"] == [3.0, 2.0, 25.0, 20.0]
    svg = kicad_cli.export_svg(board, ["F.Cu", "Edge.Cuts"], tmp_path / "f2.svg", config=engine_config).read_text()
    assert "M 7.7050,13.8250" in svg  # (10.705 - 3, 15.825 - 2)

    back = kicad_cli.export_svg(board, ["B.Cu", "B.Mask", "B.SilkS", "Edge.Cuts"], tmp_path / "b.svg", mirror=True,
                                config=engine_config).read_text()
    page_w = viewbox(back)[2]
    # VCC via at (12.305, 12.57): x' = page_w - (x - ex)
    assert f'cx="{page_w - (12.305 - 3):.4f}" cy="{12.57 - 2:.4f}"' in back


def test_export_svg_errors(engine_config, tmp_path):
    with pytest.raises(EngineError) as err:
        kicad_cli.export_svg(tmp_path / "missing.kicad_pcb", ["F.Cu"], tmp_path / "x.svg", config=engine_config)
    assert err.value.type == "NotFound"


def test_stats(board, engine_config):
    stats = kicad_cli.stats(board, config=engine_config)
    assert stats["board"]["width"] == 25.0 and stats["board"]["height"] == 20.0
    assert stats["board"]["min_track_width"] == 0.25
    assert stats["components"]["smd"]["front"] == 8
    assert stats["vias"]["through"] == 2
    assert stats["pads"]["smd"] == 22


def test_render_3d_cli(board, engine_config, tmp_path):
    out = kicad_cli.render_3d(board, tmp_path / "r.png", width=400, height=300, pivot=(-0.35, 0, 0), zoom=2,
                              config=engine_config)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_export_svg_uses_kicad_default_dark_theme(engine, board, engine_config, tmp_path):
    """The viewer canvas is KiCad Default (dark); plots must not leave white holes on it."""
    svg = kicad_cli.export_svg(board, ["F.Cu", "F.Mask", "F.SilkS", "Edge.Cuts"], tmp_path / "dark.svg",
                               config=engine_config).read_text()
    # Theme is pinned so a user's PCB editor theme cannot change the output.
    assert kicad_cli.SVG_THEME == "_builtin_default"
    # KiCad Default layer colours (dark theme): F.Cu, F.SilkS, Edge.Cuts.
    assert "fill:#C83434" in svg
    assert "stroke:#F2EDA1" in svg
    assert "stroke:#D0D2CD" in svg
    # Drill holes are plotted as an opaque white group; they must punch through to the
    # dark board background instead of reading as white dots.
    assert "fill:#001023; fill-opacity:1.0000; stroke:none;" in svg
    assert "fill:#FFFFFF; fill-opacity:1.0000; stroke:none;" not in svg


def test_render_background_matches_svg_background():
    from kicad_harness.engine import render

    assert render.BACKGROUND.lower() == kicad_cli.SVG_BACKGROUND.lower() == "#001023"


def test_export_glb_is_a_valid_model(engine, board, engine_config, tmp_path):
    """The 3D tab loads this file with three.js, so it must be a real binary glTF."""
    import struct

    glb = kicad_cli.export_glb(board, tmp_path / "board.glb", config=engine_config)
    data = glb.read_bytes()
    magic, version, length = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF" and version == 2
    assert length == len(data) and len(data) > 10_000  # a bare board is already ~100 KB
    assert not board.with_suffix(".kicad_prl").exists()


def test_via_geometry_is_exact_and_reaches_the_model(engine, board, engine_config, tmp_path, monkeypatch):
    """Vias must carry the board's real width/drill/hole centre, and the GLB must cut the hole."""
    engine.add_via(board, 11.25, 9.5, "GND", size=0.8, drill=0.4)
    vias = [v for v in engine.index(board)["vias"] if abs(v["x"] - 11.25) < 1e-6 and abs(v["y"] - 9.5) < 1e-6]
    assert len(vias) == 1
    via = vias[0]
    # Hole centre, outer diameter and drill all round-trip exactly (pcbnew stores them in nm).
    assert (via["x"], via["y"]) == (11.25, 9.5)
    assert via["size"] == pytest.approx(0.8, abs=1e-6)
    assert via["drill"] == pytest.approx(0.4, abs=1e-6)
    assert via["drill"] < via["size"]

    captured: list[list[str]] = []
    real_run = kicad_cli.run

    def spy(args, **kwargs):
        captured.append(list(args))
        return real_run(args, **kwargs)

    monkeypatch.setattr(kicad_cli, "run", spy)
    glb = kicad_cli.export_glb(board, tmp_path / "vias.glb", config=engine_config)
    args = captured[-1]
    assert "--include-tracks" in args and "--cut-vias-in-body" in args
    assert "--fill-all-vias" not in args  # filling would hide the hole
    assert glb.stat().st_size > 10_000
