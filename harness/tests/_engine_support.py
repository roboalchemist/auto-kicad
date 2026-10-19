"""Shared fixtures for the engine tests (imported by test modules; kept out of conftest.py).

Everything runs against the real KiCad 10 install; boards are copied into tmp dirs first.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kicad_harness.config import Config
from kicad_harness.engine.client import Engine

TESTS = Path(__file__).resolve().parent
FIXTURE = TESTS / "fixtures" / "blinker.kicad_pcb"
OUTPUT = TESTS / "output"  # gitignored; renders saved for a human to look at

REFS = ["C1", "C2", "C3", "D1", "R1", "R2", "R3", "U1"]
NETS = ["", "CONTROL", "DISCHARGE", "GND", "LED_ANODE", "OUTPUT", "THRESHOLD", "VCC"]


def save_output(name: str, data: bytes) -> Path:
    """Write a test artifact to tests/output/ and return its path."""
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / name
    path.write_bytes(data)
    return path


@pytest.fixture(scope="session")
def engine_config(tmp_path_factory: pytest.TempPathFactory) -> Config:
    return Config(home=tmp_path_factory.mktemp("harness-home")).ensure_dirs()


@pytest.fixture(scope="session")
def engine(engine_config: Config):
    eng = Engine(engine_config)
    yield eng
    eng.close()


@pytest.fixture
def board(tmp_path: Path) -> Path:
    """A private copy of the blinker fixture."""
    dst = tmp_path / "board.kicad_pcb"
    shutil.copyfile(FIXTURE, dst)
    return dst


@pytest.fixture(scope="session")
def fixture_index(engine: Engine, tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Index of an untouched copy of the fixture (don't mutate it)."""
    dst = tmp_path_factory.mktemp("fixture") / "board.kicad_pcb"
    shutil.copyfile(FIXTURE, dst)
    return engine.index(dst)


def by_ref(index: dict, ref: str) -> dict:
    return next(f for f in index["footprints"] if f["ref"] == ref)


def pad(index: dict, ref: str, number: str) -> dict:
    return next(p for p in index["pads"] if p["ref"] == ref and p["pad"] == number)
