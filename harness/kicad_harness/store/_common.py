"""Small helpers shared by the store modules."""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import time
from typing import Any


def jsonable(value: Any) -> Any:
    """Turn pydantic models and dataclasses into plain data; leave everything else alone."""
    dump = getattr(value, "model_dump", None)
    if callable(dump) and not isinstance(value, type):
        try:
            return dump(mode="json", by_alias=True, exclude_none=True)
        except TypeError:
            return dump()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


def to_json(value: Any) -> str | None:
    """Serialize ``value`` for a JSON column. ``None`` stays NULL."""
    if value is None:
        return None
    return json.dumps(jsonable(value), default=str, ensure_ascii=False, separators=(",", ":"))


def from_json(text: str | None) -> Any:
    return None if text is None else json.loads(text)


def next_updated_at(conn: sqlite3.Connection, table: str, design: str) -> float:
    """A timestamp strictly greater than every ``updated_at`` stored for ``design`` in ``table``.

    The live stream compares ``max(updated_at)`` between polls, so it must never repeat or go
    backwards, even when two writes land in the same clock tick or the clock steps back.
    """
    prev = conn.execute(f"SELECT MAX(updated_at) FROM {table} WHERE design = ?", (design,)).fetchone()[0]
    now = time.time()
    if prev is not None and now <= prev:
        now = prev + 1e-6
    return now
