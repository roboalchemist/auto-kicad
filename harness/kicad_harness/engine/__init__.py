"""CAD engine: everything that touches KiCad (DESIGN.md, "Engine").

``Engine`` (client.py) drives pcbnew in a KiCad-Python worker; kicad_cli, render, geometry,
freerouting and artifacts are imported on demand.
"""

from .client import Engine, EngineError

__all__ = ["Engine", "EngineError"]
