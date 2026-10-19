"""Autoroute through Specctra DSN/SES with the vendored Java 25 + Freerouting jar.

See DESIGN.md, "freerouting.py". Freerouting runs headless with neckdown off (otherwise it
fans out with 0.15 mm tracks, below the board's 0.2 mm netclass width), with analytics off,
and with its settings and logs in a temporary user-data directory instead of ~/Library.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ..config import Config
from . import kicad_cli
from .client import Engine, EngineError

# Settings overrides read by Freerouting 2.x (FREEROUTING__<SECTION>__<KEY>). Don't pre-write a
# freerouting.json instead: a partial "profile" without an id makes 2.5.0 crash at startup.
_ENV = {
    "FREEROUTING__USAGE_AND_DIAGNOSTIC_DATA__DISABLE_ANALYTICS": "true",
    "FREEROUTING__PROFILE__ALLOW_TELEMETRY": "false",
    "FREEROUTING__LOGGING__FILE__ENABLED": "false",
    "FREEROUTING__GUI__ENABLED": "false",
}


def available(config: Config) -> bool:
    """True when the configured Java runtime and Freerouting jar both exist."""
    return Path(config.java).exists() and Path(config.freerouting_jar).exists()


def _hms(seconds: float) -> str:
    s = max(1, int(seconds))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def command(config: Config, dsn: Path, ses: Path, timeout_s: float, passes: int | None) -> list[str]:
    """The Freerouting command line (``-mp`` is spelled ``--router.autorouter.max_passes``)."""
    cmd = [str(config.java), "-Djava.awt.headless=true", "-jar", str(config.freerouting_jar),
           "-de", str(dsn), "-do", str(ses), "--gui.enabled=false", "--router.automatic_neckdown=false",
           f"--router.job_timeout={_hms(timeout_s)}"]
    if passes is not None:
        cmd.append(f"--router.autorouter.max_passes={int(passes)}")
    return cmd


def autoroute(engine: Engine, board: str | os.PathLike[str], config: Config | None = None,
              timeout_s: float = 120, passes: int | None = None) -> dict[str, Any]:
    """Route ``board`` in place with Freerouting and report the result.

    Exports a DSN (existing tracks go in as unfixed wiring, so the caller rips up first if
    wanted), runs Freerouting, imports the SES (which replaces the board's tracks and vias with
    the session's), then counts unconnected items with kicad-cli DRC.

    Returns ``{"routed", "unrouted", "tracks", "vias", "seconds"}``. Raises
    ``EngineError("FreeroutingUnavailable")`` when Java or the jar is missing,
    ``FreeroutingTimeout`` or ``FreeroutingFailed`` when no session comes back.
    """
    cfg = config or engine.config
    if not available(cfg):
        raise EngineError("FreeroutingUnavailable",
                          f"need Java at {cfg.java} and Freerouting at {cfg.freerouting_jar} "
                          "(run harness/scripts/fetch_vendor.sh or set HARNESS_JAVA/HARNESS_FREEROUTING_JAR)")
    if passes is not None and int(passes) < 1:
        raise EngineError("InvalidParams", f"passes must be >= 1, got {passes}")
    t0 = time.monotonic()
    board_path = Path(board).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="harness-route-") as tmp_name:
        tmp = Path(tmp_name)
        dsn, ses, userdata = tmp / "board.dsn", tmp / "board.ses", tmp / "userdata"
        userdata.mkdir()
        engine.export_dsn(board_path, dsn)
        env = dict(os.environ, FREEROUTING__USER_DATA_PATH=str(userdata), **_ENV)
        cmd = command(cfg, dsn, ses, timeout_s, passes)
        try:
            proc = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout_s + 30)
        except subprocess.TimeoutExpired as exc:
            raise EngineError("FreeroutingTimeout", f"Freerouting ran longer than {timeout_s + 30:.0f}s") from exc
        if not ses.is_file():
            tail = " | ".join(((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-8:])
            raise EngineError("FreeroutingFailed", f"no session written (exit {proc.returncode}): {tail}")
        counts = engine.import_ses(board_path, ses)
    report = kicad_cli.drc(board_path, config=cfg)
    unrouted = report["counts"]["unconnected"]
    return {"routed": unrouted == 0, "unrouted": unrouted, "tracks": counts["tracks"], "vias": counts["vias"],
            "seconds": round(time.monotonic() - t0, 2)}
