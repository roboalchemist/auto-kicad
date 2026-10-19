"""Review threads anchored to board entities, and anchor carry-forward. See DESIGN.md, "review.py"."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from ._common import from_json, next_updated_at, to_json

if TYPE_CHECKING:
    from .db import Store

KINDS = ("comment", "drc", "agent")
SOURCES = ("user", "agent", "checker")
SEVERITIES = ("info", "suggestion", "warning", "must_fix")
STATUSES = ("open", "addressed", "resolved", "wontfix", "reopened")
# Statuses that still need work. A status filter of "open" matches both.
OPEN_STATUSES = ("open", "reopened")
ANCHOR_KINDS = ("footprint", "pad", "track", "via", "zone", "point", "region")
ENTITY_KINDS = ("footprint", "pad", "track", "via", "zone")
SIDES = ("front", "back")

EXACT_TOLERANCE = 0.001  # mm: an entity this close to its recorded centre hasn't moved
REMAP_RADIUS = 2.0  # mm: how far from the click a replacement track or via may be

_COLLECTIONS = {"footprint": "footprints", "pad": "pads", "track": "tracks", "via": "vias", "zone": "zones"}

Point = tuple[float, float]


def _choice(what: str, value: Any, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise ValueError(f"{what} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def _number(value: Any, what: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"anchor {what} must be a number, not {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"anchor {what} must be a number, not {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"anchor {what} must be finite, not {value!r}")
    return number


def normalize_anchor(anchor: dict[str, Any]) -> dict[str, Any]:
    """Validate an Anchor and return a copy with every key of the DESIGN.md shape present.

    Extra keys are kept. Coordinates become floats, ``pad`` a string, and ``region`` is ordered
    as ``[min_x, min_y, max_x, max_y]``. For entity anchors, a missing click point defaults to
    the entity centre and vice versa; a region's click point defaults to its centre. Raises
    ``ValueError`` for an unknown kind or an anchor that can't identify anything.
    """
    if not isinstance(anchor, dict):
        raise ValueError("anchor must be an object")
    kind = _choice("anchor kind", anchor.get("kind"), ANCHOR_KINDS)
    out: dict[str, Any] = {
        "kind": kind, "uuid": None, "ref": None, "pad": None, "net": None, "layer": None, "side": "front",
        "x": None, "y": None, "entity_x": None, "entity_y": None, "region": None,
    }
    out.update(anchor)
    if out["side"] is None:
        out["side"] = "front"
    _choice("anchor side", out["side"], SIDES)
    for key in ("x", "y", "entity_x", "entity_y"):
        out[key] = _number(out[key], key)
    if out["pad"] is not None:
        out["pad"] = str(out["pad"])
    if out["region"] is not None:
        region = list(out["region"])
        if len(region) != 4:
            raise ValueError("anchor region must be [x1, y1, x2, y2]")
        x1, y1, x2, y2 = (_number(v, "region") for v in region)
        if None in (x1, y1, x2, y2):
            raise ValueError("anchor region must be [x1, y1, x2, y2]")
        out["region"] = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

    has_click = out["x"] is not None and out["y"] is not None
    has_entity = out["entity_x"] is not None and out["entity_y"] is not None
    if kind == "region":
        if out["region"] is None:
            raise ValueError("a region anchor needs region")
        if not has_click:
            x1, y1, x2, y2 = out["region"]
            out["x"], out["y"] = (x1 + x2) / 2, (y1 + y2) / 2
    elif kind == "point":
        if not has_click:
            raise ValueError("a point anchor needs x and y")
    else:
        if not has_click and has_entity:
            out["x"], out["y"] = out["entity_x"], out["entity_y"]
        elif has_click and not has_entity:
            out["entity_x"], out["entity_y"] = out["x"], out["y"]
        has_click = out["x"] is not None and out["y"] is not None
        identified = {
            "footprint": bool(out["uuid"] or out["ref"]),
            "pad": bool(out["uuid"] or (out["ref"] and out["pad"] is not None)),
            "track": bool(out["uuid"] or (out["net"] is not None and has_click)),
            "via": bool(out["uuid"] or (out["net"] is not None and has_click)),
            "zone": bool(out["uuid"]),
        }[kind]
        if not identified:
            raise ValueError(f"a {kind} anchor needs a uuid" + {
                "footprint": " or ref", "pad": " or ref and pad", "track": " or net and x, y",
                "via": " or net and x, y", "zone": "",
            }[kind])
    return out


# ---------------------------------------------------------------------------------------------
# Anchor carry-forward


def _point(x: Any, y: Any) -> Point | None:
    if x is None or y is None:
        return None
    return (float(x), float(y))


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _centre(kind: str, item: dict[str, Any]) -> Point | None:
    """The entity centre as DESIGN.md defines it for ``entity_x/entity_y``."""
    if kind == "track":
        return ((item["x1"] + item["x2"]) / 2, (item["y1"] + item["y2"]) / 2)
    if kind == "zone":
        points = item.get("outline") or [p for poly in item.get("filled") or [] for p in poly]
        if not points:
            return None
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return _point(item.get("x"), item.get("y"))


def _closest_on_segment(p: Point, item: dict[str, Any]) -> Point:
    x1, y1, x2, y2 = item["x1"], item["y1"], item["x2"], item["y2"]
    dx, dy = x2 - x1, y2 - y1
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return (x1, y1)
    t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / length2))
    return (x1 + t * dx, y1 + t * dy)


def _side_layer(layer: str | None, side: str | None) -> str:
    """A footprint's layer for its current side: F.Cu/B.Cu, or the anchor layer moved to that side."""
    prefix = "B." if side == "back" else "F."
    if layer and layer[:2] in ("F.", "B."):
        return prefix + layer[2:]
    return prefix + "Cu"


def _item_layer(kind: str, item: dict[str, Any], anchor_layer: str | None) -> str | None:
    if kind == "footprint":
        return _side_layer(anchor_layer, item.get("side"))
    if kind == "pad":
        layers = item.get("layers") or []
        if anchor_layer in layers or not layers:
            return anchor_layer
        return layers[0]
    if kind in ("track", "zone"):
        return item.get("layer")
    return anchor_layer


def _label(kind: str, item: dict[str, Any]) -> str:
    if kind == "footprint":
        return item.get("ref") or "footprint"
    if kind == "pad":
        return f"pad {item.get('ref')}.{item.get('pad')}"
    net = item.get("net") or "no net"
    if kind == "via":
        return f"via ({net})"
    return f"{kind} ({net}, {item.get('layer')})"


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _result(state: str, point: Point | None, uuid: str | None, layer: str | None, detail: str) -> dict[str, Any]:
    return {
        "state": state,
        "x": _round(point[0]) if point else None,
        "y": _round(point[1]) if point else None,
        "uuid": uuid,
        "layer": layer,
        "detail": detail,
    }


def _closest(items: list[dict[str, Any]], kind: str, target: Point | None) -> dict[str, Any]:
    if target is None or len(items) == 1:
        return items[0]
    return min(items, key=lambda it: _distance(_centre(kind, it) or target, target))


def _follow(
    kind: str,
    anchor: dict[str, Any],
    item: dict[str, Any],
    click: Point | None,
    old: Point | None,
    *,
    remapped: str = "",
) -> dict[str, Any]:
    """Pin onto ``item``: exact if it sits where it was, else moved (or remapped) with the click offset kept."""
    centre = _centre(kind, item)
    layer = _item_layer(kind, item, anchor.get("layer"))
    label = _label(kind, item)
    notes = []
    if kind == "footprint" and item.get("side") and item.get("side") != anchor.get("side", "front"):
        notes.append(f"now on the {item['side']}")
    if centre is None or old is None:
        pin = click if centre is None else centre
        state = "remapped" if remapped else "exact"
        return _result(state, pin, item.get("uuid"), layer, "; ".join([remapped or label, *notes]))
    dx, dy = centre[0] - old[0], centre[1] - old[1]
    unmoved = abs(dx) <= EXACT_TOLERANCE + 1e-9 and abs(dy) <= EXACT_TOLERANCE + 1e-9
    if unmoved:
        pin = click or centre
    elif click is not None:
        pin = (centre[0] + click[0] - old[0], centre[1] + click[1] - old[1])
    else:
        pin = centre
    if remapped:
        state, detail = "remapped", remapped
    elif unmoved:
        state, detail = "exact", f"{label} unchanged"
    else:
        state, detail = "moved", f"{label} moved by ({dx:+.3f}, {dy:+.3f}) mm"
    return _result(state, pin, item.get("uuid"), layer, "; ".join([detail, *notes]))


def resolve_anchor(thread: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    """Carry a thread's anchor forward onto a pick index; returns the ``resolved_anchor`` dict.

    ``thread`` may be a Thread or a bare Anchor. Rules, in order (DESIGN.md, "review.py"):

    1. The anchor's UUID is in the index: ``exact`` if the entity centre is within ±0.001 mm of
       ``entity_x/entity_y``, otherwise ``moved`` with the pin at the new centre plus the
       original click offset. An anchor without a UUID is identified by its ref (and pad), so
       for it a ref match is also exact or moved.
    2. Footprints by ``ref``, pads by ``ref`` + ``pad``: ``remapped`` (the click offset is kept).
    3. Tracks and vias: the nearest item on the same net (tracks: and layer, if the anchor has
       one) within 2 mm of the click: ``remapped``, pinned to the closest point of the track
       centreline or to the via centre.
    4. ``point`` and ``region`` anchors are always ``exact``.
    5. Anything else is ``detached`` at the original click point.

    Entity centres: the index ``x, y`` for footprints, pads and vias; the midpoint for tracks;
    the centre of the outline's bounding box for zones.
    """
    anchor = thread.get("anchor", thread)
    kind = anchor.get("kind")
    click = _point(anchor.get("x"), anchor.get("y"))
    layer = anchor.get("layer")

    if kind in ("point", "region"):
        if click is None and anchor.get("region"):
            x1, y1, x2, y2 = anchor["region"]
            click = ((x1 + x2) / 2, (y1 + y2) / 2)
        return _result("exact", click, None, layer, f"{kind} anchor")

    collection = _COLLECTIONS.get(kind)
    if collection is None:
        return _result("detached", click, None, layer, f"unknown anchor kind {kind!r}")
    items: list[dict[str, Any]] = index.get(collection) or []
    uuid = anchor.get("uuid")
    ref, pad, net = anchor.get("ref"), anchor.get("pad"), anchor.get("net")
    old = _point(anchor.get("entity_x"), anchor.get("entity_y")) or click

    # 1. The same entity, by UUID.
    if uuid:
        found = [it for it in items if it.get("uuid") == uuid]
        if len(found) > 1 and ref:
            # Duplicated UUIDs (unnormalized boards): prefer the item that also matches by name.
            named = [it for it in found if it.get("ref") == ref and (pad is None or str(it.get("pad")) == str(pad))]
            found = named or found
        if found:
            return _follow(kind, anchor, _closest(found, kind, old), click, old)

    # 2. Footprints by ref, pads by ref + pad.
    found = []
    if kind == "footprint" and ref:
        found = [it for it in items if it.get("ref") == ref]
    elif kind == "pad" and ref and pad is not None:
        found = [it for it in items if it.get("ref") == ref and str(it.get("pad")) == str(pad)]
    if found:
        item = _closest(found, kind, old)
        if not uuid:
            return _follow(kind, anchor, item, click, old)
        how = f"{_label(kind, item)} matched by {'ref' if kind == 'footprint' else 'ref and pad'}"
        return _follow(kind, anchor, item, click, old, remapped=f"{how} (uuid {uuid} is gone)")

    # 3. Tracks and vias: the nearest item on the same net (and layer) near the click.
    if kind in ("track", "via") and net is not None and click is not None:
        best: tuple[float, dict[str, Any], Point] | None = None
        for item in items:
            if item.get("net") != net:
                continue
            if kind == "track":
                if layer and item.get("layer") != layer:
                    continue
                pin = _closest_on_segment(click, item)
            else:
                pin = (item["x"], item["y"])
            d = _distance(click, pin)
            if d <= REMAP_RADIUS + 1e-9 and (best is None or d < best[0]):
                best = (d, item, pin)
        if best is not None:
            d, item, pin = best
            detail = f"nearest {_label(kind, item)}, {d:.3f} mm from the original point"
            return _result("remapped", pin, item.get("uuid"), _item_layer(kind, item, layer), detail)

    # 5. Detached.
    if kind == "footprint":
        what = ref or uuid
    elif kind == "pad":
        what = f"pad {ref}.{pad}" if ref else uuid
    elif kind in ("track", "via") and net is not None:
        where = f" on {layer}" if layer and kind == "track" else ""
        return _result("detached", click, None, layer, f"no {net or 'no-net'} {kind}{where} within {REMAP_RADIUS:g} mm")
    else:
        what = f"{kind} {uuid}"
    return _result("detached", click, None, layer, f"{what} is gone")


# ---------------------------------------------------------------------------------------------
# Threads


def _status_filter(status: str | Iterable[str] | None) -> set[str] | None:
    if status is None:
        return None
    wanted = [status] if isinstance(status, str) else list(status)
    out: set[str] = set()
    for value in wanted:
        out.add(_choice("status", value, STATUSES))
        if value == "open":
            out.add("reopened")
    return out


def _same_sha(a: str | None, b: str) -> bool:
    if not a:
        return False
    a, b = a.lower(), b.lower()
    if len(a) >= 4 and len(b) >= 4:
        return a.startswith(b) or b.startswith(a)
    return a == b


def _tags(tags: str | Iterable[str] | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = [tags]
    out: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError(f"tags must be strings, not {tag!r}")
        cleaned = tag.strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


class Review:
    """Review threads: user comments, DRC findings and agent notes anchored to board entities.

    Threads are numbered per design from 1. ``get``/``by_number``/``list`` return Thread dicts
    (DESIGN.md shape plus ``updated_at``) with ``resolved_anchor`` set to ``None``; resolve
    anchors against a pick index with :meth:`resolve_anchor`.
    """

    resolve_anchor = staticmethod(resolve_anchor)

    def __init__(self, store: Store) -> None:
        self._store = store

    def create(
        self,
        design: str,
        sha: str | None,
        anchor: dict[str, Any],
        body: str,
        *,
        title: str | None = None,
        tags: Iterable[str] = (),
        severity: str = "suggestion",
        kind: str = "comment",
        source: str = "user",
        author: str = "user",
        view: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Open a thread on ``design`` against version ``sha`` and return it.

        The thread starts ``open`` with one status-log entry. Raises ``ValueError`` for an
        unknown severity, kind, source or anchor kind, or an anchor that identifies nothing.
        """
        if not isinstance(design, str) or not design:
            raise ValueError("design must be a non-empty string")
        _choice("severity", severity, SEVERITIES)
        _choice("kind", kind, KINDS)
        _choice("source", source, SOURCES)
        if not isinstance(body, str):
            raise ValueError("body must be a string")
        if view is not None and not isinstance(view, dict):
            raise ValueError("view must be an object or null")
        anchor = normalize_anchor(anchor)
        title = title.strip() or None if isinstance(title, str) else None
        with self._store.tx() as conn:
            number = conn.execute(
                "SELECT COALESCE(MAX(number), 0) + 1 FROM threads WHERE design = ?", (design,)
            ).fetchone()[0]
            now = next_updated_at(conn, "threads", design)
            cursor = conn.execute(
                """
                INSERT INTO threads (design, number, kind, source, severity, tags, status, title, body, author,
                                     created_at, created_sha, anchor, view, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (design, number, kind, source, severity, to_json(_tags(tags)), title, body, author,
                 now, sha, to_json(anchor), to_json(view), now),
            )
            thread_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO thread_status_log (thread_id, status, actor, at, sha, note) VALUES (?, ?, ?, ?, ?, NULL)",
                (thread_id, "open", author, now, sha),
            )
            return self._load(conn, "id = ?", (thread_id,))[0]

    def get(self, id: int) -> dict[str, Any] | None:
        """Return thread ``id``, or ``None``."""
        with self._store.tx(write=False) as conn:
            found = self._load(conn, "id = ?", (id,))
        return found[0] if found else None

    def by_number(self, design: str, number: int) -> dict[str, Any] | None:
        """Return thread ``#number`` of ``design``, or ``None``."""
        with self._store.tx(write=False) as conn:
            found = self._load(conn, "design = ? AND number = ?", (design, number))
        return found[0] if found else None

    def delete(self, design: str, number: int) -> bool:
        """Remove thread ``#number`` (and its replies / status log). Returns False if absent."""
        with self._store.tx() as conn:
            row = conn.execute(
                "SELECT id FROM threads WHERE design = ? AND number = ?", (design, number)
            ).fetchone()
            if row is None:
                return False
            thread_id = row["id"]
            conn.execute("DELETE FROM thread_replies WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM thread_status_log WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        return True

    def list(
        self, design: str, status: str | Iterable[str] | None = None, sha: str | None = None
    ) -> list[dict[str, Any]]:
        """Threads of ``design``, oldest first, with replies and status logs.

        ``status`` is one status or several; ``"open"`` also matches ``"reopened"``. ``sha``
        keeps threads linked to that version: created, replied to, or changed status there
        (full SHAs or prefixes of at least 4 characters).
        """
        wanted = _status_filter(status)
        with self._store.tx(write=False) as conn:
            threads = self._load(conn, "design = ?", (design,))
        if wanted is not None:
            threads = [t for t in threads if t["status"] in wanted]
        if sha:
            threads = [t for t in threads if self._linked(t, sha)]
        return threads

    def reply(self, id: int, body: str, *, author: str, sha: str | None = None) -> dict[str, Any]:
        """Add a reply to thread ``id`` and return the thread. Raises ``KeyError`` if it doesn't exist."""
        if not isinstance(body, str):
            raise ValueError("body must be a string")
        with self._store.tx() as conn:
            design = self._design_of(conn, id)
            now = next_updated_at(conn, "threads", design)
            conn.execute(
                "INSERT INTO thread_replies (thread_id, author, body, created_at, sha) VALUES (?, ?, ?, ?, ?)",
                (id, author, body, now, sha),
            )
            conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, id))
            return self._load(conn, "id = ?", (id,))[0]

    def set_status(
        self, id: int, status: str, *, by: str, sha: str | None = None, note: str | None = None
    ) -> dict[str, Any]:
        """Change the status of thread ``id``, log it, and return the thread.

        ``addressed`` sets ``addressed_sha``, ``resolved`` sets ``resolved_sha``, and ``open`` or
        ``reopened`` clear both (the log keeps the history). ``wontfix`` leaves them alone.
        Raises ``ValueError`` for an unknown status and ``KeyError`` for an unknown thread.
        """
        _choice("status", status, STATUSES)
        with self._store.tx() as conn:
            design = self._design_of(conn, id)
            now = next_updated_at(conn, "threads", design)
            columns: dict[str, Any] = {"status": status, "updated_at": now}
            if status == "addressed":
                columns["addressed_sha"] = sha
            elif status == "resolved":
                columns["resolved_sha"] = sha
            elif status in OPEN_STATUSES:
                columns.update(addressed_sha=None, resolved_sha=None)
            assignments = ", ".join(f"{name} = ?" for name in columns)
            conn.execute(f"UPDATE threads SET {assignments} WHERE id = ?", (*columns.values(), id))
            conn.execute(
                "INSERT INTO thread_status_log (thread_id, status, actor, at, sha, note) VALUES (?, ?, ?, ?, ?, ?)",
                (id, status, by, now, sha, note),
            )
            return self._load(conn, "id = ?", (id,))[0]

    def last_updated(self, design: str) -> float:
        """The newest ``updated_at`` among the threads of ``design`` (0.0 if none). Every change
        to a thread (create, reply, status) moves it forward."""
        row = self._store.query_one("SELECT MAX(updated_at) FROM threads WHERE design = ?", (design,))
        return float(row[0]) if row and row[0] is not None else 0.0

    # -- helpers -------------------------------------------------------------------------------

    @staticmethod
    def _design_of(conn: sqlite3.Connection, id: int) -> str:
        row = conn.execute("SELECT design FROM threads WHERE id = ?", (id,)).fetchone()
        if row is None:
            raise KeyError(f"no review thread with id {id}")
        return row["design"]

    @staticmethod
    def _linked(thread: dict[str, Any], sha: str) -> bool:
        shas = [thread["created_sha"], thread["addressed_sha"], thread["resolved_sha"]]
        shas += [r["sha"] for r in thread["replies"]] + [e["sha"] for e in thread["status_log"]]
        return any(_same_sha(s, sha) for s in shas)

    @staticmethod
    def _load(conn: sqlite3.Connection, where: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        rows = conn.execute(f"SELECT * FROM threads WHERE {where} ORDER BY number, id", params).fetchall()
        if not rows:
            return []
        ids = [row["id"] for row in rows]
        marks = ",".join("?" * len(ids))
        replies: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for r in conn.execute(f"SELECT * FROM thread_replies WHERE thread_id IN ({marks}) ORDER BY id", ids):
            replies[r["thread_id"]].append(
                {key: r[key] for key in ("id", "author", "body", "created_at", "sha")}
            )
        log: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for e in conn.execute(f"SELECT * FROM thread_status_log WHERE thread_id IN ({marks}) ORDER BY id", ids):
            log[e["thread_id"]].append(
                {"status": e["status"], "by": e["actor"], "at": e["at"], "sha": e["sha"], "note": e["note"]}
            )
        return [
            {
                "id": row["id"],
                "design": row["design"],
                "number": row["number"],
                "kind": row["kind"],
                "source": row["source"],
                "severity": row["severity"],
                "tags": json.loads(row["tags"]),
                "status": row["status"],
                "title": row["title"],
                "body": row["body"],
                "author": row["author"],
                "created_at": row["created_at"],
                "created_sha": row["created_sha"],
                "anchor": from_json(row["anchor"]),
                "view": from_json(row["view"]),
                "addressed_sha": row["addressed_sha"],
                "resolved_sha": row["resolved_sha"],
                "replies": replies[row["id"]],
                "status_log": log[row["id"]],
                "resolved_anchor": None,
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
