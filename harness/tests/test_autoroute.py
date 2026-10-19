"""Freerouting through DSN/SES with the vendored Java 25 runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from _engine_support import board, engine, engine_config  # noqa: F401
from kicad_harness.config import Config
from kicad_harness.engine import freerouting, kicad_cli
from kicad_harness.engine.client import EngineError


def test_unavailable_raises(engine, board, tmp_path):
    cfg = Config(home=tmp_path / "home", java=tmp_path / "no-java", freerouting_jar=tmp_path / "no.jar")
    with pytest.raises(EngineError) as err:
        freerouting.autoroute(engine, board, cfg)
    assert err.value.type == "FreeroutingUnavailable"


def test_command_line(engine_config):
    cmd = freerouting.command(engine_config, Path("/t/in.dsn"), Path("/t/out.ses"), 90, 20)
    assert cmd[1:4] == ["-Djava.awt.headless=true", "-jar", str(engine_config.freerouting_jar)]
    assert ["-de", "/t/in.dsn", "-do", "/t/out.ses"] == cmd[4:8]
    assert "--gui.enabled=false" in cmd and "--router.automatic_neckdown=false" in cmd
    assert "--router.job_timeout=00:01:30" in cmd and "--router.autorouter.max_passes=20" in cmd


@pytest.mark.slow
def test_autoroute_from_scratch(engine, board, engine_config):
    if not freerouting.available(engine_config):
        pytest.skip("Java/Freerouting not vendored (run harness/scripts/fetch_vendor.sh)")
    engine.delete_tracks(board)
    assert kicad_cli.drc(board, config=engine_config)["counts"]["unconnected"] > 0

    res = freerouting.autoroute(engine, board, engine_config, timeout_s=120)
    assert res["routed"] is True and res["unrouted"] == 0
    assert res["tracks"] > 0 and res["seconds"] > 0

    report = kicad_cli.drc(board, config=engine_config)
    assert report["counts"] == {"errors": 0, "warnings": 0, "unconnected": 0}
    idx = engine.index(board)
    assert len(idx["tracks"]) == res["tracks"] and len(idx["vias"]) == res["vias"]
    assert min(t["width"] for t in idx["tracks"]) >= 0.2  # no 0.15 mm neckdown fanouts
    assert not [p for p in board.parent.iterdir() if p.name != board.name]  # no side files
