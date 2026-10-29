"""The bill of materials: grouping and the endpoint, in both project phases."""

from __future__ import annotations

import json
import re

import httpx
import pytest

from kicad_harness.server import create_app, group_bom, ref_sort_key
from kicad_harness.store.workspace import Workspace
from tests.test_agent import FIXTURE

# Real KiCad + the shared services fixture from the phase tests.
from tests.test_phase import services  # noqa: F401  (pytest fixture)


def test_refs_sort_naturally() -> None:
    refs = ["R10", "R2", "R1", "C1", "R9"]
    assert sorted(refs, key=ref_sort_key) == ["C1", "R1", "R2", "R9", "R10"]


def test_group_bom_collapses_identical_parts() -> None:
    rows = [
        {"ref": "R1", "value": "10k", "footprint": "R_0805"},
        {"ref": "R10", "value": "10k", "footprint": "R_0805"},
        {"ref": "R2", "value": "10k", "footprint": "R_0805"},
        {"ref": "C1", "value": "100nF", "footprint": "C_0805"},
    ]
    lines, total = group_bom(rows)
    assert total == 4
    assert len(lines) == 2
    resistor = next(line for line in lines if line["value"] == "10k")
    assert resistor["refs"] == ["R1", "R2", "R10"]
    assert resistor["qty"] == 3


def test_group_bom_keeps_different_values_apart() -> None:
    rows = [
        {"ref": "R1", "value": "10k", "footprint": "R_0805"},
        {"ref": "R2", "value": "47k", "footprint": "R_0805"},
        {"ref": "R3", "value": "10k", "footprint": "R_0603"},
    ]
    lines, total = group_bom(rows)
    assert total == 3
    assert len(lines) == 3, "value and footprint both distinguish parts"


def _client(services) -> httpx.AsyncClient:
    app = create_app()
    app.state.services, app.state.metric_tasks = services, set()
    app.state.stop_flags = {}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_bom_falls_back_to_the_board_for_an_imported_design(services, tmp_path) -> None:
    """A project made from a .kicad_pcb has no schematic, so the BOM comes from the board."""
    name = "bom-imported"
    Workspace.create(services.config, name, FIXTURE, None, services.engine)
    async with _client(services) as client:
        response = await client.get(f"/api/designs/{name}/bom")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "board"
    assert body["line_count"] > 0
    refs = {ref for line in body["lines"] for ref in line["refs"]}
    assert "D1" in refs and "R1" in refs


async def test_bom_comes_from_the_schematic_when_one_exists(services) -> None:
    name = "bom-schematic"
    ws = Workspace.create_schematic(services.config, name, "an RC filter")
    from kicad_harness.engine.schematic import Schematic

    doc = Schematic.load(ws.schematic_path)
    lib = __import__("kicad_harness.engine.schematic", fromlist=["read_library"]).read_library(
        "/usr/share/kicad/symbols/Device.kicad_sym"
    )
    doc.libraries["Device"] = lib
    doc.add_symbol("Device:R", "R1", 100.0, 100.0, value="10k", footprint="Resistor_SMD:R_0805_2012Metric")
    doc.add_symbol("Device:R", "R2", 120.0, 100.0, value="10k", footprint="Resistor_SMD:R_0805_2012Metric")
    doc.set_symbol_property("R1", "LCSC", "C17414")
    doc.set_symbol_property("R2", "LCSC", "C17414")
    doc.save()

    async with _client(services) as client:
        body = (await client.get(f"/api/designs/{name}/bom")).json()
    assert body["source"] == "schematic"
    assert body["total_qty"] == 2
    line = body["lines"][0]
    assert line["refs"] == ["R1", "R2"]
    assert line["lcsc"] == "C17414"
    # Enriched from the JLCPCB catalogue when the database is present.
    from kicad_harness.engine import parts

    if parts.available():
        assert line["tier"] in ("basic", "extended")
        assert line["stock"] and line["stock"] > 0


async def test_bom_of_an_empty_project_is_empty_not_an_error(services) -> None:
    name = "bom-empty"
    Workspace.create_schematic(services.config, name, "nothing drawn yet")
    async with _client(services) as client:
        response = await client.get(f"/api/designs/{name}/bom")
    assert response.status_code == 200
    body = response.json()
    assert body["lines"] == [] and body["total_qty"] == 0
