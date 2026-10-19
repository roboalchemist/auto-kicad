"""Per-board-content artifact cache (DESIGN.md, "artifacts.py").

Everything is keyed by the board hash, ``sha256(board bytes)[:16]``, so a commit and an
identical working copy share one cache entry. Layout under ``config.cache``::

    <CACHE_FORMAT>/<hash>/board.kicad_pcb   materialized board
    <hash>/index.json        pick index
    <hash>/front.svg         F.Cu, F.Mask, F.SilkS, Edge.Cuts
    <hash>/back.svg          B.Cu, B.Mask, B.SilkS, Edge.Cuts, mirrored
    <hash>/drc.json          normalized DRC
    <hash>/stats.json        kicad-cli stats

Renders go to ``config.renders/<CACHE_FORMAT>-<hash>-<spec_hash>.png`` and are served at
``/api/renders/<file>``. Each artifact is built at most once per hash: builds run under a
per-artifact lock and are written atomically.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from ..config import Config
from . import kicad_cli, render
from .client import Engine, EngineError

LAYERS = {
    "front": ["F.Cu", "F.Mask", "F.SilkS", "Edge.Cuts"],
    "back": ["B.Cu", "B.Mask", "B.SilkS", "Edge.Cuts"],
}
RENDER_URL = "/api/renders/"
# Bump whenever the bytes of a cached artifact change for the same board (theme/plot changes).
# Included in both cache paths so old entries are simply ignored.
CACHE_FORMAT = "f2"
SPEC_2D = {"mode", "side", "center", "view_mm", "px_per_mm", "width_px", "highlight", "labels", "pins"}
SPEC_3D = {"mode", "side", "center", "view_mm", "rotate", "quality", "width", "height"}


def board_hash(board_bytes: bytes) -> str:
    """``sha256(board_bytes)[:16]``, the cache key."""
    return hashlib.sha256(board_bytes).hexdigest()[:16]


def spec_hash(spec: dict[str, Any]) -> str:
    """Stable hash of a render spec (key order doesn't matter)."""
    canon = json.dumps(spec, sort_keys=True, separators=(",", ":"), default=list)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


class Artifacts:
    """Builds and caches index, SVGs, DRC, stats and renders per board hash."""

    def __init__(self, config: Config, engine: Engine) -> None:
        self.config = config
        self.engine = engine
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    # ------------------------------------------------------------------ plumbing

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = self._locks[key] = threading.Lock()
            return lock

    def dir(self, hash: str) -> Path:
        """Cache directory of a board hash."""
        if not hash or not all(c in "0123456789abcdef" for c in hash):
            raise EngineError("InvalidParams", f"not a board hash: {hash!r}")
        return Path(self.config.cache) / CACHE_FORMAT / hash

    def board_path(self, hash: str) -> Path:
        """Path of the materialized board; ``NotFound`` if it was never materialized."""
        path = self.dir(hash) / "board.kicad_pcb"
        if not path.is_file():
            raise EngineError("NotFound", f"board {hash} is not materialized")
        return path

    def _build(self, key: str, target: Path, build: Callable[[Path], None]) -> Path:
        if target.exists():
            return target
        with self._lock(key):
            if target.exists():
                return target
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.stem}.{uuid.uuid4().hex[:8]}.tmp{target.suffix}")
            try:
                build(tmp)
                os.replace(tmp, target)
            finally:
                if tmp.exists():
                    tmp.unlink()
        return target

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    # ------------------------------------------------------------------ artifacts

    def materialize(self, board_bytes: bytes) -> tuple[str, Path]:
        """Write ``cache/<hash>/board.kicad_pcb`` (once) and return ``(hash, path)``."""
        h = board_hash(board_bytes)
        target = self.dir(h) / "board.kicad_pcb"
        self._build(f"{h}/board", target, lambda tmp: tmp.write_bytes(board_bytes))
        return h, target

    def materialize_file(self, path: str | os.PathLike[str]) -> tuple[str, Path]:
        """``materialize`` the bytes of a board file."""
        return self.materialize(Path(path).read_bytes())

    def index(self, hash: str) -> dict[str, Any]:
        """Pick index of the board."""
        board = self.board_path(hash)
        target = self._build(f"{hash}/index", board.parent / "index.json",
                             lambda tmp: self._write_json(tmp, self.engine.index(board)))
        return json.loads(target.read_text(encoding="utf-8"))

    def svg_path(self, hash: str, side: str) -> Path:
        """Path of the front or back SVG (back is mirrored), building it if needed."""
        if side not in LAYERS:
            raise EngineError("InvalidParams", f"side must be 'front' or 'back', got {side!r}")
        board = self.board_path(hash)
        return self._build(f"{hash}/svg-{side}", board.parent / f"{side}.svg",
                           lambda tmp: kicad_cli.export_svg(board, LAYERS[side], tmp, mirror=side == "back",
                                                            config=self.config))

    def glb_path(self, hash: str) -> Path:
        """Path of the board's GLB model (cached per content hash)."""
        board = self.board_path(hash)
        return self._build(f"{hash}/glb", board.parent / "board.glb",
                           lambda tmp: kicad_cli.export_glb(board, tmp, config=self.config))

    def svg(self, hash: str, side: str) -> str:
        """SVG text of the front or back of the board."""
        return self.svg_path(hash, side).read_text(encoding="utf-8")

    def drc(self, hash: str) -> dict[str, Any]:
        """Normalized DRC report."""
        board = self.board_path(hash)
        target = self._build(f"{hash}/drc", board.parent / "drc.json",
                             lambda tmp: self._write_json(tmp, kicad_cli.drc(board, config=self.config)))
        return json.loads(target.read_text(encoding="utf-8"))

    def stats(self, hash: str) -> dict[str, Any]:
        """kicad-cli board statistics."""
        board = self.board_path(hash)
        target = self._build(f"{hash}/stats", board.parent / "stats.json",
                             lambda tmp: self._write_json(tmp, kicad_cli.stats(board, config=self.config)))
        return json.loads(target.read_text(encoding="utf-8"))

    def render(self, hash: str, spec: dict[str, Any]) -> tuple[Path, str]:
        """Render a view once per (hash, spec); returns ``(png_path, url)``.

        ``spec["mode"]`` is ``"2d"`` (default; keys: side, center, view_mm, px_per_mm, width_px,
        highlight, labels, pins, as ``render.render_2d``) or ``"3d"`` (side, center, view_mm,
        rotate, quality, width, height, as ``render.render_3d_view``).
        """
        mode = spec.get("mode", "2d")
        allowed = SPEC_2D if mode == "2d" else SPEC_3D if mode == "3d" else None
        if allowed is None:
            raise EngineError("InvalidParams", f"render mode must be '2d' or '3d', got {mode!r}")
        unknown = sorted(set(spec) - allowed)
        if unknown:
            raise EngineError("InvalidParams", f"unknown {mode} render keys {unknown}; allowed: {sorted(allowed)}")
        board = self.board_path(hash)
        name = f"{CACHE_FORMAT}-{hash}-{spec_hash(spec)}.png"
        target = Path(self.config.renders) / name
        params = {k: v for k, v in spec.items() if k != "mode"}

        def build(tmp: Path) -> None:
            index = self.index(hash)
            if mode == "2d":
                side = params.pop("side", "front")
                png = render.render_2d(self.svg(hash, side), index, side=side, **params)
            else:
                png = render.render_3d_view(board, index, config=self.config, **params)
            tmp.write_bytes(png)

        self._build(f"render/{name}", target, build)
        return target, RENDER_URL + name
