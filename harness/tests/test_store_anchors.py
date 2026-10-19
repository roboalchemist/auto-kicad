"""Anchor normalization and carry-forward (store/review.py) against synthetic pick indexes."""

import copy

import pytest

from kicad_harness.store import Review, normalize_anchor, resolve_anchor

BASE_INDEX = {
    "board": {"bbox": [0, 0, 40, 30], "edge_bbox": [0, 0, 40, 30], "layers": ["F.Cu", "B.Cu"], "thickness": 1.6},
    "nets": ["", "GND", "OUT", "VCC"],
    "footprints": [
        {"uuid": "fp-u1", "ref": "U1", "value": "NE555", "footprint": "SOIC-8", "x": 10.0, "y": 12.0,
         "rotation": 0.0, "side": "front", "bbox": [7.0, 9.5, 6.0, 5.0], "courtyard": None,
         "ref_text": {"x": 10.0, "y": 8.5, "bbox": [9.0, 8.0, 2.0, 1.0], "visible": True, "layer": "F.SilkS",
                      "height": 1.0}},
        {"uuid": "fp-c3", "ref": "C3", "value": "100n", "footprint": "C0805", "x": 20.0, "y": 12.0,
         "rotation": 90.0, "side": "front", "bbox": [19.0, 11.0, 2.0, 2.0], "courtyard": None,
         "ref_text": {"x": 20.0, "y": 10.0, "bbox": [19.5, 9.5, 1.0, 1.0], "visible": True, "layer": "F.SilkS",
                      "height": 1.0}},
    ],
    "pads": [
        {"uuid": "pad-u1-3", "ref": "U1", "pad": "3", "net": "OUT", "x": 8.0, "y": 13.0, "w": 0.6, "h": 1.5,
         "rotation": 0.0, "shape": "roundrect", "layers": ["F.Cu"], "through": False, "drill": 0.0,
         "polygon": [[7.7, 12.25], [8.3, 12.25], [8.3, 13.75], [7.7, 13.75]]},
        {"uuid": "pad-u1-8", "ref": "U1", "pad": "8", "net": "VCC", "x": 8.0, "y": 11.0, "w": 0.6, "h": 1.5,
         "rotation": 0.0, "shape": "roundrect", "layers": ["F.Cu"], "through": False, "drill": 0.0,
         "polygon": [[7.7, 10.25], [8.3, 10.25], [8.3, 11.75], [7.7, 11.75]]},
    ],
    "tracks": [
        {"uuid": "trk-gnd", "net": "GND", "layer": "F.Cu", "x1": 0.0, "y1": 20.0, "x2": 10.0, "y2": 20.0,
         "width": 0.25},
        {"uuid": "trk-vcc", "net": "VCC", "layer": "F.Cu", "x1": 0.0, "y1": 25.0, "x2": 10.0, "y2": 25.0,
         "width": 0.25},
    ],
    "vias": [{"uuid": "via-gnd", "net": "GND", "x": 15.0, "y": 20.0, "size": 0.6, "drill": 0.3}],
    "zones": [{"uuid": "zone-gnd", "net": "GND", "layer": "B.Cu",
               "outline": [[1.0, 1.0], [39.0, 1.0], [39.0, 29.0], [1.0, 29.0]],
               "filled": [[[1.5, 1.5], [38.5, 1.5], [38.5, 28.5], [1.5, 28.5]]]}],
}

FP_U1 = {"kind": "footprint", "uuid": "fp-u1", "ref": "U1", "layer": "F.Cu", "side": "front",
         "x": 10.4, "y": 12.3, "entity_x": 10.0, "entity_y": 12.0}
PAD_U1_3 = {"kind": "pad", "uuid": "pad-u1-3", "ref": "U1", "pad": "3", "net": "OUT", "layer": "F.Cu",
            "x": 8.1, "y": 13.2, "entity_x": 8.0, "entity_y": 13.0}
TRK_GND = {"kind": "track", "uuid": "trk-gnd", "net": "GND", "layer": "F.Cu",
           "x": 4.0, "y": 20.05, "entity_x": 5.0, "entity_y": 20.0}
VIA_GND = {"kind": "via", "uuid": "via-gnd", "net": "GND", "x": 15.1, "y": 20.0, "entity_x": 15.0, "entity_y": 20.0}


def index(**changes):
    out = copy.deepcopy(BASE_INDEX)
    out.update(copy.deepcopy(changes))
    return out


def item(idx, collection, uuid):
    return next(it for it in idx[collection] if it["uuid"] == uuid)


def test_exact_when_entity_is_unchanged():
    got = resolve_anchor({"anchor": FP_U1}, index())
    assert got == {"state": "exact", "x": 10.4, "y": 12.3, "uuid": "fp-u1", "layer": "F.Cu", "detail": "U1 unchanged"}


def test_exact_within_tolerance():
    idx = index()
    item(idx, "footprints", "fp-u1").update(x=10.0009, y=11.9991)
    got = resolve_anchor(FP_U1, idx)
    assert (got["state"], got["x"], got["y"]) == ("exact", 10.4, 12.3)


def test_moved_keeps_click_offset():
    idx = index()
    item(idx, "footprints", "fp-u1").update(x=15.0, y=18.0)
    got = resolve_anchor(FP_U1, idx)
    assert got["state"] == "moved"
    assert (got["x"], got["y"]) == pytest.approx((15.4, 18.3))
    assert got["uuid"] == "fp-u1"
    assert "moved by (+5.000, +6.000)" in got["detail"]


def test_moved_pad():
    idx = index()
    item(idx, "pads", "pad-u1-3").update(x=9.0, y=14.0)
    got = resolve_anchor(PAD_U1_3, idx)
    assert (got["state"], got["uuid"], got["layer"]) == ("moved", "pad-u1-3", "F.Cu")
    assert (got["x"], got["y"]) == pytest.approx((9.1, 14.2))


def test_flipped_footprint_reports_the_new_side():
    idx = index()
    item(idx, "footprints", "fp-u1").update(side="back")
    got = resolve_anchor(dict(FP_U1, layer="F.SilkS"), idx)
    assert (got["state"], got["layer"]) == ("exact", "B.SilkS")
    assert "now on the back" in got["detail"]


def test_remapped_footprint_by_ref():
    idx = index()
    item(idx, "footprints", "fp-u1").update(uuid="fp-u1-new", x=11.0, y=12.0)
    got = resolve_anchor(FP_U1, idx)
    assert (got["state"], got["uuid"]) == ("remapped", "fp-u1-new")
    assert (got["x"], got["y"]) == pytest.approx((11.4, 12.3))
    assert "matched by ref" in got["detail"]


def test_remapped_pad_by_ref_and_pad():
    idx = index()
    item(idx, "pads", "pad-u1-3").update(uuid="pad-u1-3-new")
    got = resolve_anchor(PAD_U1_3, idx)
    assert (got["state"], got["uuid"], got["x"], got["y"]) == ("remapped", "pad-u1-3-new", 8.1, 13.2)
    assert "matched by ref and pad" in got["detail"]


def test_pad_whose_number_is_gone_is_detached():
    idx = index()
    idx["pads"] = [p for p in idx["pads"] if p["pad"] != "3"]
    got = resolve_anchor(PAD_U1_3, idx)
    assert got == {"state": "detached", "x": 8.1, "y": 13.2, "uuid": None, "layer": "F.Cu",
                   "detail": "pad U1.3 is gone"}


def test_remapped_track_by_net_proximity():
    idx = index(tracks=[
        # Closest of all, but on another layer.
        {"uuid": "t-back", "net": "GND", "layer": "B.Cu", "x1": 0.0, "y1": 20.1, "x2": 10.0, "y2": 20.1, "width": 0.25},
        # Close, but another net.
        {"uuid": "t-vcc", "net": "VCC", "layer": "F.Cu", "x1": 0.0, "y1": 20.2, "x2": 10.0, "y2": 20.2, "width": 0.25},
        {"uuid": "t-far", "net": "GND", "layer": "F.Cu", "x1": 0.0, "y1": 21.9, "x2": 10.0, "y2": 21.9, "width": 0.25},
        {"uuid": "t-near", "net": "GND", "layer": "F.Cu", "x1": 4.5, "y1": 21.0, "x2": 4.5, "y2": 28.0, "width": 0.25},
        {"uuid": "t-out", "net": "GND", "layer": "F.Cu", "x1": 2.0, "y1": 22.1, "x2": 9.0, "y2": 22.1, "width": 0.25},
    ])
    got = resolve_anchor(TRK_GND, idx)
    # The click (4.0, 20.05) is 1.85 mm from t-far, 1.074 mm from t-near's end (4.5, 21.0) and
    # 2.05 mm (out of range) from t-out.
    assert (got["state"], got["uuid"], got["layer"]) == ("remapped", "t-near", "F.Cu")
    assert (got["x"], got["y"]) == pytest.approx((4.5, 21.0))
    assert "1.074 mm" in got["detail"]


def test_track_without_layer_matches_any_layer():
    idx = index(tracks=[
        {"uuid": "t-back", "net": "GND", "layer": "B.Cu", "x1": 0.0, "y1": 20.1, "x2": 10.0, "y2": 20.1, "width": 0.25},
    ])
    got = resolve_anchor(dict(TRK_GND, layer=None), idx)
    assert (got["state"], got["uuid"], got["layer"]) == ("remapped", "t-back", "B.Cu")


def test_track_beyond_two_mm_is_detached():
    idx = index(tracks=[
        {"uuid": "t-far", "net": "GND", "layer": "F.Cu", "x1": 0.0, "y1": 22.1, "x2": 10.0, "y2": 22.1, "width": 0.25},
    ])
    got = resolve_anchor(TRK_GND, idx)
    assert got == {"state": "detached", "x": 4.0, "y": 20.05, "uuid": None, "layer": "F.Cu",
                   "detail": "no GND track on F.Cu within 2 mm"}


def test_track_found_by_uuid_is_exact():
    got = resolve_anchor(TRK_GND, index())
    assert (got["state"], got["uuid"], got["x"], got["y"]) == ("exact", "trk-gnd", 4.0, 20.05)


def test_remapped_via_by_net_proximity():
    idx = index(vias=[
        {"uuid": "v-vcc", "net": "VCC", "x": 15.2, "y": 20.0, "size": 0.6, "drill": 0.3},
        {"uuid": "v-new", "net": "GND", "x": 16.0, "y": 20.5, "size": 0.6, "drill": 0.3},
    ])
    got = resolve_anchor(VIA_GND, idx)
    assert (got["state"], got["uuid"], got["x"], got["y"]) == ("remapped", "v-new", 16.0, 20.5)


def test_point_and_region_are_always_exact():
    point = {"kind": "point", "x": 3.0, "y": 4.0, "layer": "F.Cu"}
    assert resolve_anchor(point, {}) == {"state": "exact", "x": 3.0, "y": 4.0, "uuid": None, "layer": "F.Cu",
                                         "detail": "point anchor"}
    region = {"kind": "region", "region": [2.0, 2.0, 6.0, 10.0]}
    got = resolve_anchor(region, index())
    assert (got["state"], got["x"], got["y"]) == ("exact", 4.0, 6.0)


def test_detached_footprint_keeps_original_point():
    idx = index()
    idx["footprints"] = [fp for fp in idx["footprints"] if fp["ref"] != "U1"]
    got = resolve_anchor(FP_U1, idx)
    assert got == {"state": "detached", "x": 10.4, "y": 12.3, "uuid": None, "layer": "F.Cu", "detail": "U1 is gone"}


def test_zone_by_uuid_and_gone():
    zone = {"kind": "zone", "uuid": "zone-gnd", "net": "GND", "layer": "B.Cu", "x": 5.0, "y": 5.0,
            "entity_x": 20.0, "entity_y": 15.0}
    assert resolve_anchor(zone, index())["state"] == "exact"
    idx = index()
    for p in item(idx, "zones", "zone-gnd")["outline"]:
        p[0] += 1.0
    got = resolve_anchor(zone, idx)
    assert (got["state"], got["x"], got["y"]) == ("moved", 6.0, 5.0)
    assert resolve_anchor(zone, index(zones=[]))["state"] == "detached"


def test_anchor_without_uuid_is_identified_by_ref():
    anchor = normalize_anchor({"kind": "footprint", "ref": "U1"})
    got = resolve_anchor(anchor, index())
    assert (got["state"], got["uuid"], got["x"], got["y"]) == ("exact", "fp-u1", 10.0, 12.0)

    pinned = normalize_anchor({"kind": "pad", "ref": "U1", "pad": 3, "x": 8.0, "y": 13.0})
    idx = index()
    item(idx, "pads", "pad-u1-3").update(x=8.5)
    got = resolve_anchor(pinned, idx)
    assert (got["state"], got["uuid"], got["x"], got["y"]) == ("moved", "pad-u1-3", 8.5, 13.0)


def test_duplicate_uuids_prefer_the_named_item():
    idx = index()
    item(idx, "pads", "pad-u1-8").update(uuid="pad-u1-3")  # unnormalized board: U1.3 and U1.8 share a UUID
    got = resolve_anchor(dict(PAD_U1_3, ref="U1", pad="8", entity_x=8.0, entity_y=11.0, x=8.0, y=11.0), idx)
    assert (got["state"], got["x"], got["y"]) == ("exact", 8.0, 11.0)
    got = resolve_anchor(PAD_U1_3, idx)
    assert (got["state"], got["x"], got["y"]) == ("exact", 8.1, 13.2)


def test_review_exposes_resolve_anchor_and_accepts_threads():
    thread = {"kind": "comment", "anchor": FP_U1}
    assert Review.resolve_anchor(thread, index()) == resolve_anchor(FP_U1, index())


def test_normalize_anchor_fills_the_full_shape():
    out = normalize_anchor({"kind": "pad", "uuid": "p", "pad": 3, "x": "1.5", "y": 2, "extra": "kept"})
    assert out == {
        "kind": "pad", "uuid": "p", "ref": None, "pad": "3", "net": None, "layer": None, "side": "front",
        "x": 1.5, "y": 2.0, "entity_x": 1.5, "entity_y": 2.0, "region": None, "extra": "kept",
    }
    region = normalize_anchor({"kind": "region", "region": [6, 10, 2, 2]})
    assert region["region"] == [2.0, 2.0, 6.0, 10.0]
    assert (region["x"], region["y"]) == (4.0, 6.0)
    entity = normalize_anchor({"kind": "footprint", "ref": "U1", "entity_x": 1, "entity_y": 2})
    assert (entity["x"], entity["y"]) == (1.0, 2.0)


@pytest.mark.parametrize("anchor", [
    {"kind": "net"},
    {"kind": "footprint"},
    {"kind": "pad", "ref": "U1"},
    {"kind": "track", "net": "GND"},
    {"kind": "zone", "net": "GND"},
    {"kind": "point", "x": 1.0},
    {"kind": "region", "x": 1.0, "y": 1.0},
    {"kind": "region", "region": [1, 2, 3]},
    {"kind": "point", "x": float("nan"), "y": 1.0},
    {"kind": "point", "x": True, "y": 1.0},
    {"kind": "footprint", "ref": "U1", "side": "top"},
    "U1",
])
def test_normalize_anchor_rejects_bad_anchors(anchor):
    with pytest.raises(ValueError):
        normalize_anchor(anchor)
