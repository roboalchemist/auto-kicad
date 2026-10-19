"""2D SVG crops and framed 3D renders. Images are saved to tests/output/ for a human to check."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from _engine_support import board, engine, engine_config, fixture_index, pad, save_output  # noqa: F401
from kicad_harness.engine import kicad_cli, render
from kicad_harness.engine.client import EngineError


@pytest.fixture(scope="module")
def svgs(tmp_path_factory, engine_config):
    from _engine_support import FIXTURE

    tmp = tmp_path_factory.mktemp("svg")
    front = kicad_cli.export_svg(FIXTURE, ["F.Cu", "F.Mask", "F.SilkS", "Edge.Cuts"], tmp / "front.svg",
                                 config=engine_config).read_text()
    back = kicad_cli.export_svg(FIXTURE, ["B.Cu", "B.Mask", "B.SilkS", "Edge.Cuts"], tmp / "back.svg", mirror=True,
                                config=engine_config).read_text()
    return {"front": front, "back": back}


def image(png: bytes) -> Image.Image:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return Image.open(io.BytesIO(png)).convert("RGB")


def test_render_2d_whole_board(svgs, fixture_index):
    png = render.render_2d(svgs["front"], fixture_index, pins=[{"x": 22, "y": 3, "label": "7"}])
    save_output("render_2d_board.png", png)
    im = image(png)
    margin = max(0.5, 0.03 * 25)
    assert im.size == (1200, round(1200 * (20 + 2 * margin) / (25 + 2 * margin)))
    s = 1200 / (25 + 2 * margin)  # px per mm
    to_px = lambda x, y: (round((x + margin) * s), round((y + margin) * s))  # noqa: E731
    px, py = to_px(22, 3)
    r, g, b = im.getpixel((px - 7, py))  # pin marker disc (beside its "7"): amber
    assert r > 200 and 120 < g < 220 and b < 80
    r, g, b = im.getpixel(to_px(1, 18))  # empty board area: dark background
    assert max(r, g, b) < 60


def test_render_2d_crop_and_highlight(svgs, fixture_index):
    kw = dict(center=(9, 10), view_mm=10, width_px=600)
    plain = image(render.render_2d(svgs["front"], fixture_index, labels=False, **kw))
    png = render.render_2d(svgs["front"], fixture_index, highlight=["U1.1", "net:VCC"], **kw)
    save_output("render_2d_u1_highlight.png", png)
    lit = image(png)
    assert plain.size == lit.size == (600, 600)
    s = 60.0  # 600 px / 10 mm
    p1 = pad(fixture_index, "U1", "1")
    xy = (round((p1["x"] - 4) * s), round((p1["y"] - 5) * s - 0.6 * s))  # on the pad, off its net label
    assert lit.getpixel(xy)[1] > plain.getpixel(xy)[1] + 30  # green highlight over the pink pad
    far = (round((13 - 4) * s), round((10.5 - 5) * s))  # empty area: unchanged
    assert lit.getpixel(far) == plain.getpixel(far)

    small = image(render.render_2d(svgs["front"], fixture_index, center=(9, 10), view_mm=4, px_per_mm=50))
    assert small.size == (200, 200)


def test_render_2d_back_is_mirrored(svgs, fixture_index):
    png = render.render_2d(svgs["back"], fixture_index, side="back", center=(9, 10), view_mm=10, width_px=600,
                           labels=False)
    save_output("render_2d_back.png", png)
    im = image(png)
    s = 60.0
    # B.Cu VCC track runs from the via at (12.305, 12.57) to (11.57, 12.57); mirrored x' = 14 - x.
    on_track = (round((14 - 11.9) * s), round((12.57 - 5) * s))
    mirror_of_it = (round((11.9 - 4) * s), round((12.57 - 5) * s))
    r, g, b = im.getpixel(on_track)
    assert b > 150 and b > r  # B.Cu blue
    assert max(im.getpixel(mirror_of_it)) < 60


def test_render_2d_errors(svgs, fixture_index):
    with pytest.raises(EngineError):
        render.render_2d(svgs["front"], fixture_index, side="left")
    with pytest.raises(EngineError):
        render.render_2d("<svg></svg>", fixture_index)
    with pytest.raises(EngineError) as err:
        render.render_2d(svgs["front"], fixture_index, highlight=["U42"])
    assert err.value.type == "NotFound"


def test_frame_3d_math(fixture_index):
    cam = render.frame_3d(fixture_index, center=(9, 10), view_mm=10, height=900)
    assert cam["zoom"] == pytest.approx(1.0355 * 25 / 10)
    assert cam["pivot"] == pytest.approx((-0.35, 0.0, 0.0))  # cm from (12.5, 10), +Y up
    assert cam["px_per_mm"] == pytest.approx(90)
    cam = render.frame_3d(fixture_index, center=(20, 4), view_mm=5, height=600, requested_height=664)
    assert cam["pivot"] == pytest.approx((0.75, 0.6, 0.0))
    assert cam["zoom"] == pytest.approx((600 / 5) * 1.0355 * 25 / 664)
    whole = render.frame_3d(fixture_index, height=900)
    assert whole["zoom"] == pytest.approx(1.0) and whole["pivot"] == pytest.approx((0.0, 0.0, 0.0))


def test_render_3d_view_framing(engine_config, fixture_index):
    from _engine_support import FIXTURE

    p1 = pad(fixture_index, "U1", "1")
    png = render.render_3d_view(FIXTURE, fixture_index, center=(p1["x"], p1["y"]), view_mm=4, width=800, height=600,
                                config=engine_config)
    save_output("render_3d_u1_pad1.png", png)
    im = image(png)
    assert im.size == (800, 600)
    s = 150.0  # 600 px / 4 mm
    gray = lambda c: min(c) > 140 and max(c) - min(c) < 20  # noqa: E731  (HASL pad)
    assert gray(im.getpixel((400, 300)))
    assert gray(im.getpixel((400, round(300 + 0.9 * s))))  # still on the 2.05 mm tall pad
    assert not gray(im.getpixel((round(400 + 0.635 * s), 300)))  # gap to pad 2 (1.27 mm pitch)
    assert gray(im.getpixel((round(400 + 1.27 * s), 300)))  # pad 2
    # The pad's left edge is 0.294 mm left of centre.
    assert gray(im.getpixel((round(400 - 0.25 * s), 300))) and not gray(im.getpixel((round(400 - 0.34 * s), 300)))


def test_render_3d_view_bottom_mirrors_x(engine_config, fixture_index):
    from _engine_support import FIXTURE

    png = render.render_3d_view(FIXTURE, fixture_index, center=(9, 10), view_mm=10, side="back", width=800,
                                height=600, config=engine_config)
    save_output("render_3d_bottom.png", png)
    im = image(png)
    s = 60.0
    via = (round(400 - (12.305 - 9) * s), round(300 + (12.57 - 10) * s))  # mirrored
    mirror = (round(400 + (12.305 - 9) * s), via[1])
    assert sum(im.getpixel(via)) > 300  # light via barrel
    assert sum(im.getpixel(mirror)) < 200  # plain solder mask


def test_render_3d_view_rotated(engine_config, fixture_index):
    from _engine_support import FIXTURE

    png = render.render_3d_view(FIXTURE, fixture_index, rotate=(-45, 0, 45), width=640, height=480,
                                config=engine_config)
    save_output("render_3d_iso.png", png)
    assert image(png).size == (640, 480)
    with pytest.raises(EngineError):
        render.render_3d_view(FIXTURE, fixture_index, side="left", config=engine_config)
