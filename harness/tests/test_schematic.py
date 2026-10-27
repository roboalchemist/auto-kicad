"""Schematic documents: S-expression round-trip, symbol placement, and real-KiCad validation.

The last test is the important one: it writes a schematic, then asks ``kicad-cli`` to render it
and to run ERC. Anything the writer emits that KiCad cannot parse fails there. See WORKLOG.md
for the format rules these tests protect.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from kicad_harness.config import Config
from kicad_harness.engine import schematic as sch

REPO = Path(__file__).resolve().parent.parent.parent
JLC_LIB = REPO / "demo" / "libs" / "symbols" / "jlcpcb.kicad_sym"
SYSTEM_LIB = Path("/usr/share/kicad/symbols/Device.kicad_sym")


def _library_file() -> tuple[Path, str]:
    """The symbol library to test against, and the library name symbols are addressed by."""
    if JLC_LIB.is_file():
        return JLC_LIB, "jlcpcb"
    if SYSTEM_LIB.is_file():
        return SYSTEM_LIB, "Device"
    pytest.skip("no symbol library available")


@pytest.fixture(scope="module")
def jlc() -> dict[str, sch.LibrarySymbol]:
    path, _ = _library_file()
    return sch.read_library(path)


@pytest.fixture(scope="module")
def libraries(jlc: dict[str, sch.LibrarySymbol]) -> dict[str, dict[str, sch.LibrarySymbol]]:
    _, name = _library_file()
    return {name: jlc}


def _two_pin(lib: dict[str, sch.LibrarySymbol]) -> sch.LibrarySymbol:
    return next(s for s in lib.values() if len(s.pins) == 2)


def _many_pin(lib: dict[str, sch.LibrarySymbol]) -> sch.LibrarySymbol:
    return next(s for s in lib.values() if len(s.pins) >= 3)


@pytest.fixture
def ids(jlc: dict[str, sch.LibrarySymbol]) -> tuple[str, str]:
    """(two-pin lib_id, many-pin lib_id)."""
    return _two_pin(jlc).lib_id, _many_pin(jlc).lib_id


def _kicad_cli(tmp_path: Path) -> str | None:
    return shutil.which(str(Config(home=tmp_path / "home").kicad_cli or ""))


# ---------------------------------------------------------------------------------------------
# Parsing and writing


def test_empty_schematic_round_trips() -> None:
    text = sch.empty_schematic("A3")
    tree = sch.parse(text)
    assert tree[0] == "kicad_sch"
    paper = sch.find_one(tree, "paper")
    assert paper is not None and paper[1] == "A3"
    assert sch.write_top(sch.parse(text)) == text.rstrip("\n")


def test_parse_keeps_nesting_and_strings() -> None:
    tree = sch.parse('(root (a "x y") (b (c 1)))')
    assert tree[0] == "root"
    assert tree[1] == ["a", "x y"]
    assert sch.find_one(tree, "b") == ["b", ["c", "1"]]


def test_parse_rejects_unbalanced() -> None:
    with pytest.raises(ValueError):
        sch.parse("(root (a 1)")
    with pytest.raises(ValueError):
        sch.parse('(root "unterminated)')


def test_writer_drops_negative_zero() -> None:
    assert sch.quote("-0.0") == "0"
    assert sch.quote(-0.0) == "0"


# ---------------------------------------------------------------------------------------------
# Libraries and placement


def test_library_reads_pins(jlc: dict[str, sch.LibrarySymbol], ids) -> None:
    assert jlc
    two_pin = jlc[ids[0].split(":", 1)[1]]
    assert len(two_pin.pins) == 2
    many = jlc[ids[1].split(":", 1)[1]]
    assert len(many.pins) >= 3


def test_place_symbol_and_read_it_back(tmp_path: Path, libraries, ids) -> None:
    path = tmp_path / "s.kicad_sch"
    doc = sch.Schematic.create(path, libraries=libraries)
    doc.add_symbol(ids[0], "R1", 100.0, 100.0)
    doc.save()

    again = sch.Schematic.load(path, libraries=libraries)
    (placed,) = again.placements()
    assert placed.reference == "R1"
    assert placed.lib_id == ids[0]
    # Coordinates snap to KiCad's 1.27 mm grid, so the offset from it is tiny.
    offset = placed.x / sch.GRID_MM
    assert abs(offset - round(offset)) < 1e-6


def test_duplicate_reference_is_rejected(tmp_path: Path, libraries, ids) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    doc.add_symbol(ids[0], "R1", 100.0, 100.0)
    with pytest.raises(ValueError, match="already placed"):
        doc.add_symbol(ids[1], "R1", 120.0, 100.0)


def test_unknown_symbol_lists_alternatives(tmp_path: Path, libraries) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    with pytest.raises(ValueError, match="available:"):
        doc.add_symbol("nope:Missing", "X1", 10.0, 10.0)


def test_pin_position_respects_rotation(tmp_path: Path, libraries, ids) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    flat = doc.add_symbol(ids[0], "R1", 100.0, 100.0)
    turned = doc.add_symbol(ids[0], "R2", 100.0, 100.0, rotation=90.0)
    assert doc.pin_position(flat, "1") != doc.pin_position(turned, "1")


def test_remove_symbol_drops_its_wires(tmp_path: Path, libraries, ids) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    doc.add_symbol(ids[0], "R1", 100.0, 100.0)
    doc.add_symbol(ids[0], "R2", 120.0, 100.0)
    doc.connect_pins(("R1", "1"), ("R2", "1"), net="N")
    before = len(doc.wires)
    assert before
    assert doc.remove_symbol("R2")
    assert len(doc.wires) < before
    assert [p.reference for p in doc.placements()] == ["R1"]


# ---------------------------------------------------------------------------------------------
# Connectivity


def test_connect_pins_names_a_net(tmp_path: Path, libraries, ids) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    many, two = ids[1], ids[0]
    doc.add_symbol(many, "U1", 100.0, 100.0)
    doc.add_symbol(two, "R1", 140.0, 100.0)
    first_pin = next(iter(doc.lookup(many).pins))
    second_pin = next(iter(doc.lookup(two).pins))
    assert doc.connect_pins(("U1", first_pin), ("R1", second_pin), net="OUT") == "OUT"
    doc.save()

    again = sch.Schematic.load(doc.path, libraries=libraries)
    members = again.nets()["OUT"]
    assert {(m["ref"], m["pin"]) for m in members} == {("U1", first_pin), ("R1", second_pin)}


def test_wire_splits_into_segments(tmp_path: Path, libraries) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    nodes = doc.add_wire([(0.0, 0.0), (12.7, 0.0), (12.7, 12.7)])
    assert len(nodes) == 2
    for node in nodes:
        pts = sch.find_one(node, "pts")
        assert pts is not None and len(sch.find_all(pts, "xy")) == 2


def test_unconnected_pins_reports_floating(tmp_path: Path, libraries, ids) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    placed = doc.add_symbol(ids[0], "R1", 100.0, 100.0)
    first = next(iter(doc.lookup(ids[0]).pins))
    assert {f["pin"] for f in doc.unconnected_pins()} == set(doc.lookup(ids[0]).pins)
    doc.add_label("A", *doc.pin_position(placed, first))
    assert first not in {f["pin"] for f in doc.unconnected_pins()}


def test_board_netlist_exposes_components(tmp_path: Path, libraries, ids) -> None:
    doc = sch.Schematic.create(tmp_path / "s.kicad_sch", libraries=libraries)
    many, two = ids[1], ids[0]
    doc.add_symbol(many, "U1", 100.0, 100.0)
    doc.add_symbol(two, "R1", 140.0, 100.0)
    first_pin = next(iter(doc.lookup(many).pins))
    second_pin = next(iter(doc.lookup(two).pins))
    doc.connect_pins(("U1", first_pin), ("R1", second_pin), net="OUT")

    netlist = sch.board_netlist(doc)
    assert {c["ref"] for c in netlist["components"]} == {"U1", "R1"}
    assert {m["ref"] for m in netlist["nets"]["OUT"]} == {"U1", "R1"}


# ---------------------------------------------------------------------------------------------
# The check that matters: real KiCad


def test_kicad_renders_and_erc_passes(tmp_path: Path, libraries, ids) -> None:
    """The writer must produce a file real KiCad loads, plots, and finds electrically clean."""
    cli = _kicad_cli(tmp_path)
    if not cli:
        pytest.skip("kicad-cli is not available")

    path = tmp_path / "board.kicad_sch"
    doc = sch.Schematic.create(path, libraries=libraries)
    many, two = ids[1], ids[0]
    doc.add_symbol(many, "U1", 100.0, 100.0)
    doc.add_symbol(two, "R1", 145.0, 100.0)
    first_pin = next(iter(doc.lookup(many).pins))
    second_pin = next(iter(doc.lookup(two).pins))
    doc.connect_pins(("U1", first_pin), ("R1", second_pin), net="OUT")
    doc.save()

    svg = subprocess.run(
        [cli, "sch", "export", "svg", str(path), "-o", str(tmp_path / "svg")],
        capture_output=True,
        text=True,
    )
    assert svg.returncode == 0, svg.stdout + svg.stderr
    assert list((tmp_path / "svg").glob("*.svg")), "kicad-cli produced no SVG"

    erc_path = tmp_path / "erc.json"
    erc = subprocess.run(
        [cli, "sch", "erc", str(path), "--format", "json", "-o", str(erc_path)],
        capture_output=True,
        text=True,
    )
    assert erc.returncode == 0, erc.stdout + erc.stderr
    report = json.loads(erc_path.read_text(encoding="utf-8"))
    errors = [v for v in report.get("violations", []) if v.get("severity") == "error"]
    assert not errors, errors
