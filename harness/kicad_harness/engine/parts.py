"""Part sourcing: what JLCPCB stocks, and whether a part has a datasheet.

Two sources, each answering a different question:

- **JLCPCB** (``data/jlcpcb-components.sqlite3``) — "can this board actually be made?" Assembly
  is limited to parts in this catalogue; ``basic`` parts cost nothing extra, ``extended`` parts
  carry a per-part reel fee. Stock and price breakpoints come from here.
- **i2cdb** (``https://i2cdb.roboalch.com``, via the ``i2cdb`` CLI) — the datasheet catalogue:
  which manufacturer parts exist, whether a PDF is available, and its content. Also maps an
  LCSC code back to a canonical manufacturer part.

The agent asks these before choosing parts, so a schematic is drawn with parts that can be
ordered and whose pinout can be checked against a real datasheet.

The JLCPCB database is third-party, ~1.2 GB, and read-only: open it with ``immutable=1`` so a
reader never takes write locks or creates a WAL.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DB = REPO / "data" / "jlcpcb-components.sqlite3"
I2CDB_BASE = "https://i2cdb.roboalch.com"


class PartsError(RuntimeError):
    """A lookup could not run: no database, no i2cdb CLI, or a failed call."""


# ---------------------------------------------------------------------------------------------
# JLCPCB


def db_path() -> Path | None:
    """The JLCPCB parts database, or ``None`` if it isn't on this machine."""
    env = os.environ.get("JLC_DB")
    candidates = [Path(env).expanduser()] if env else []
    candidates.append(DEFAULT_DB)
    for path in candidates:
        if path.is_file():
            return path
    return None


def available() -> bool:
    """Whether the JLCPCB catalogue can be queried here."""
    return db_path() is not None


def _connect(readonly: bool = True) -> sqlite3.Connection:
    path = db_path()
    if path is None:
        raise PartsError(
            f"the JLCPCB parts database is not available (looked for {DEFAULT_DB}); "
            "set JLC_DB to its path"
        )
    if readonly:
        uri = f"file:{path}?immutable=1"
        return sqlite3.connect(uri, uri=True, timeout=10)
    return sqlite3.connect(path, timeout=10)


def _price_breaks(raw: str | None) -> list[dict[str, Any]]:
    """Parse the catalogue's ``[{"qFrom","qTo","price"}]`` price column."""
    if not raw:
        return []
    try:
        rows = json.loads(raw)
    except ValueError:
        return []
    return [
        {"qty_from": r.get("qFrom"), "qty_to": r.get("qTo"), "price": r.get("price")}
        for r in rows
        if isinstance(r, dict)
    ]


def _part_row(row: tuple) -> dict[str, Any]:
    lcsc, mfr, package, stock, basic, price, description, datasheet, joints, preferred = row
    breaks = _price_breaks(price)
    return {
        "lcsc": f"C{lcsc}",
        "mpn": mfr,
        "package": package,
        "stock": stock,
        "basic": bool(basic),
        # JLC charges a reel fee for extended parts, so this drives real cost.
        "tier": "basic" if basic else "extended",
        "unit_price": breaks[0]["price"] if breaks else None,
        "price_breaks": breaks,
        "description": (description or "")[:200],
        "datasheet": datasheet,
        "joints": joints,
        "preferred": bool(preferred),
    }


_COLUMNS = "lcsc, mfr, package, stock, basic, price, description, datasheet, joints, preferred"


def search_jlc(
    query: str | None = None,
    *,
    package: str | None = None,
    basic_only: bool = False,
    in_stock: bool = True,
    limit: int = 20,
) -> dict[str, Any]:
    """Search the JLCPCB catalogue by manufacturer part number (and optional package).

    ``query`` matches the MPN as a case-insensitive substring; parts are ranked basic first,
    then by stock.
    """
    if limit < 1 or limit > 100:
        raise PartsError("limit must be between 1 and 100")
    where: list[str] = []
    params: list[Any] = []
    if query:
        where.append("mfr LIKE ?")
        params.append(f"%{query.strip()}%")
    if package:
        where.append("package LIKE ?")
        params.append(f"%{package.strip()}%")
    if basic_only:
        where.append("basic = 1")
    if in_stock:
        where.append("stock > 0")
    sql = f"SELECT {_COLUMNS} FROM components"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY basic DESC, stock DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"source": "jlcpcb", "query": query, "parts": [_part_row(r) for r in rows], "count": len(rows)}


def get_jlc(lcsc: str) -> dict[str, Any] | None:
    """One part by LCSC code (``C7593`` or ``7593``)."""
    digits = re.sub(r"^[Cc]", "", str(lcsc).strip())
    if not digits.isdigit():
        raise PartsError(f"not an LCSC code: {lcsc!r} (expected C12345)")
    with _connect() as conn:
        row = conn.execute(f"SELECT {_COLUMNS} FROM components WHERE lcsc = ?", (int(digits),)).fetchone()
    return _part_row(row) if row else None


@lru_cache(maxsize=1)
def _package_index() -> dict[str, str]:
    """``{footprint name: JLC package}`` built from the footprints the demo library ships.

    Lets a KiCad footprint (``R_0805_2012Metric``) be checked against what JLC lists.
    """
    index: dict[str, str] = {}
    libs = REPO / "demo" / "libs" / "footprints"
    if libs.is_dir():
        for path in libs.glob("*.kicad_mod"):
            index[path.stem.upper()] = path.stem
    return index


def package_hint(footprint: str) -> str | None:
    """Best-effort JLC package for a KiCad footprint.

    ``SOIC-8_3.9x4.9mm_P1.27mm`` -> ``SOIC-8``; ``R_0805_2012Metric`` -> ``0805``.
    """
    name = footprint.split(":")[-1]
    match = re.match(r"([A-Za-z]+-\d+)", name)          # SOIC-8, TQFP-32, SOT-23
    if match:
        return match.group(1)
    match = re.search(r"_(\d{4})_", name)                 # 0805, 0603 (imperial size)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------------------------
# i2cdb (datasheets)


def i2cdb_available() -> bool:
    return shutil.which("i2cdb") is not None


def _i2cdb(args: list[str], timeout: float = 60) -> Any:
    """Run ``i2cdb <args> --json`` and parse the result."""
    if not i2cdb_available():
        raise PartsError("the i2cdb CLI is not installed on this machine")
    env = dict(os.environ)
    env.setdefault("I2CDB_BEARER", _token())
    try:
        proc = subprocess.run(
            ["i2cdb", *args, "--json"], capture_output=True, text=True, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired as exc:
        raise PartsError(f"i2cdb {args[0]} timed out") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise PartsError(f"i2cdb {args[0]} failed: " + " | ".join(detail))
    try:
        return json.loads(proc.stdout or "null")
    except ValueError as exc:
        raise PartsError(f"i2cdb returned unreadable output: {exc}") from exc


def _token() -> str:
    """The i2cdb bearer token, from the environment or gopass."""
    token = os.environ.get("I2CDB_API_KEY") or os.environ.get("I2CDB_BEARER")
    if token:
        return token
    try:
        proc = subprocess.run(
            ["gopass", "show", "-o", "env/I2CDB_API_KEY"], capture_output=True, text=True, timeout=20
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def search_i2cdb(mpn_prefix: str, limit: int = 20) -> dict[str, Any]:
    """Manufacturer parts whose MPN starts with ``mpn_prefix`` (case-sensitive), with datasheet status."""
    prefix = (mpn_prefix or "").strip()
    if not prefix:
        raise PartsError("give an MPN prefix to search, e.g. 'UCC287' (matching is case-sensitive)")
    data = _i2cdb(["parts", "search", prefix, "--limit", str(min(limit, 50))])
    items = data.get("items", []) if isinstance(data, dict) else []
    return {
        "source": "i2cdb",
        "query": prefix,
        "total": (data or {}).get("total", len(items)),
        "parts": [
            {
                "mpn": i.get("mpn"),
                "manufacturer": i.get("manufacturer"),
                "category": i.get("category"),
                "has_pdf": i.get("has_pdf"),
            }
            for i in items
        ],
    }


def datasheet(mfg: str, mpn: str, pages: str | None = None) -> dict[str, Any]:
    """Datasheet metadata and text for ``manufacturer/mpn``.

    ``pages`` is a range like ``"1-3"``. Returns ``{mfg, mpn, has_pdf, text}``; ``text`` is
    empty when no PDF is held.
    """
    ref = f"{mfg.strip()}/{mpn.strip()}"
    args = ["datasheet", "get", ref, "--format", "markdown"]
    if pages:
        args += ["--page", pages]
    if not i2cdb_available():
        raise PartsError("the i2cdb CLI is not installed on this machine")
    env = dict(os.environ)
    env.setdefault("I2CDB_BEARER", _token())
    try:
        proc = subprocess.run(["i2cdb", *args], capture_output=True, text=True, timeout=120, env=env)
    except subprocess.TimeoutExpired as exc:
        raise PartsError(f"i2cdb datasheet {ref} timed out") from exc
    text = proc.stdout or ""
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-3:]
        return {
            "mfg": mfg,
            "mpn": mpn,
            "has_pdf": False,
            "text": "",
            "error": " | ".join(detail) or "no datasheet available",
        }
    return {"mfg": mfg, "mpn": mpn, "has_pdf": bool(text.strip()), "text": text[:12000]}


def resolve_vendor(vendor: str, sku: str) -> dict[str, Any] | None:
    """Map a distributor SKU (e.g. LCSC ``C7593``) to its canonical manufacturer part."""
    data = _i2cdb(["parts", "by-vendor", vendor, sku])
    if not isinstance(data, dict) or "error" in data:
        return None
    return {
        "vendor": vendor,
        "sku": sku,
        "mpn": data.get("mpn"),
        "manufacturer": data.get("manufacturer"),
        "has_pdf": data.get("has_pdf"),
    }


def check_part(mpn: str, lcsc: str | None = None) -> dict[str, Any]:
    """Everything the agent needs to trust a part: JLC stock/price, datasheet, and a verdict.

    Combines the two sources and states whether the part is usable for a JLC-assembled board.
    """
    result: dict[str, Any] = {"mpn": mpn, "checks": {}, "notes": []}
    jlc_hits: list[dict[str, Any]] = []
    if lcsc:
        hit = get_jlc(lcsc)
        if hit:
            jlc_hits = [hit]
    if not jlc_hits:
        try:
            jlc_hits = search_jlc(mpn, limit=5)["parts"]
        except PartsError as exc:
            result["notes"].append(f"JLCPCB: {exc}")
    result["checks"]["jlcpcb"] = {
        "stocked": bool(jlc_hits),
        "matches": jlc_hits,
    }

    datasheet_info: dict[str, Any] | None = None
    try:
        # i2cdb's positional query is a case-sensitive prefix match on the MPN.
        prefix = re.match(r"[A-Za-z0-9-]+", mpn).group(0) if mpn and re.match(r"[A-Za-z0-9-]+", mpn) else mpn
        hits = search_i2cdb(prefix, limit=10)["parts"] if prefix else []
        exact = next((h for h in hits if (h.get("mpn") or "").upper() == mpn.upper()), None)
        if exact:
            datasheet_info = datasheet(exact["manufacturer"], exact["mpn"], pages="1-1")
            result["checks"]["datasheet"] = {
                "found": bool(datasheet_info.get("has_pdf")),
                "manufacturer": exact["manufacturer"],
                "mpn": exact["mpn"],
            }
        else:
            # Not held by i2cdb is not the same as "this part has no datasheet".
            result["checks"]["datasheet"] = {
                "found": None,
                "reason": f"i2cdb has no record for {mpn!r} (it holds {len(hits)} near matches)",
                "near_matches": [h.get("mpn") for h in hits[:5]],
            }
    except PartsError as exc:
        result["checks"]["datasheet"] = {"found": None, "reason": str(exc)}

    # JLCPCB ships a datasheet link per part; surface it when i2cdb has nothing.
    if result["checks"].get("datasheet", {}).get("found") is not True and jlc_hits:
        supplier_ds = next((h.get("datasheet") for h in jlc_hits if h.get("datasheet")), None)
        if supplier_ds:
            result["checks"].setdefault("datasheet", {})["supplier_url"] = supplier_ds

    jlc_ok = bool(jlc_hits)
    has_doc = (result["checks"].get("datasheet") or {}).get("found")
    result["usable_for_jlc"] = jlc_ok
    if not jlc_ok:
        result["notes"].append("not in the JLCPCB catalogue: assembly would need it hand-fitted or redesigned")
    if has_doc is False:
        result["notes"].append("no datasheet found: verify the pinout by another means before wiring it")
    return result
