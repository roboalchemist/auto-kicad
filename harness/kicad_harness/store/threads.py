"""Housekeeping for the CopilotKit thread store.

The web runtime keeps every AG-UI event of every run so a thread can be replayed. That is what
makes reopening a conversation work — but it also means a transient failure is replayed forever.
A "Model token limit … exceeded before any response was generated" event is especially
misleading: it describes one request that never produced output, long after the agent moved on,
and it reads like a live error every time the thread is opened.

``prune_stale_token_errors`` removes exactly those events, and only from runs that have a later
run in the same thread — i.e. only once the loop got past them. A thread whose newest run failed
keeps its error, because there it is still the current state.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

# The messages pydantic-ai raises when a run produced nothing because the completion budget ran
# out. Matched case-insensitively against a RUN_ERROR event's `message`.
_TOKEN_LIMIT_RE = re.compile(
    r"model\s+token\s+limit.*exceeded\s+before\s+any\s+response"
    r"|exceeded\s+max\s+retries\s+count",
    re.IGNORECASE | re.DOTALL,
)


_STATED_LIMIT_RE = re.compile(r"token\s+limit\s*\((\d+)\)", re.IGNORECASE)


def stated_limit(event: dict) -> int | None:
    """The completion budget quoted in a token-limit error, if it names one."""
    message = event.get("message") if isinstance(event, dict) else None
    if not isinstance(message, str):
        return None
    match = _STATED_LIMIT_RE.search(message)
    return int(match.group(1)) if match else None


def is_budget_error(event: dict) -> bool:
    """Whether ``event`` reports an exhausted token or tool-retry budget."""
    if not isinstance(event, dict) or event.get("type") != "RUN_ERROR":
        return False
    message = event.get("message")
    return isinstance(message, str) and bool(_TOKEN_LIMIT_RE.search(message))


def is_stale_run_error(event: dict, current_budget: int | None = None, superseded: bool = False) -> bool:
    """Whether a budget error should stop being replayed.

    Two independent reasons, because the user should never be shown a failure the current setup
    cannot reproduce:

    - it quotes a completion limit that differs from ``current_budget`` (the configuration has
      changed since), or
    - ``superseded``: a later run in the same thread moved past it.
    """
    if not is_budget_error(event):
        return False
    quoted = stated_limit(event)
    if current_budget and quoted and quoted != current_budget:
        return True
    return superseded


def _is_reasoning(event: dict) -> bool:
    """Reasoning streams arrive as one event per token delta: thousands per run, worth nothing
    to a replay (the transcript is reconstructible without them)."""
    return isinstance(event, dict) and str(event.get("type", "")).startswith("REASONING")


def prune_reasoning(db_path: str | Path) -> dict[str, int]:
    """Drop reasoning events from stored runs; returns the same shape of stats."""
    path = Path(db_path)
    stats = {"runs_scanned": 0, "runs_changed": 0, "events_removed": 0}
    if not path.is_file():
        return stats
    try:
        conn = sqlite3.connect(path, timeout=30)
    except sqlite3.Error:
        return stats
    try:
        try:
            rows = list(conn.execute("SELECT id, events FROM agent_runs WHERE events LIKE '%REASONING%'"))
        except sqlite3.Error:
            return stats
        for row_id, raw in rows:
            stats["runs_scanned"] += 1
            try:
                events = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(events, list):
                continue
            kept = [e for e in events if not _is_reasoning(e)]
            removed = len(events) - len(kept)
            if not removed:
                continue
            conn.execute("UPDATE agent_runs SET events = ? WHERE id = ?", (json.dumps(kept), row_id))
            stats["runs_changed"] += 1
            stats["events_removed"] += removed
        conn.commit()
    finally:
        conn.close()
    return stats


def prune_stale_token_errors(db_path: str | Path, current_budget: int | None = None) -> dict[str, int]:
    """Drop token-limit RUN_ERROR events from runs that a later run superseded.

    Returns ``{"runs_scanned", "runs_changed", "events_removed"}``. A missing database or an
    unexpected schema is not an error — this is best-effort housekeeping.
    """
    path = Path(db_path)
    stats = {"runs_scanned": 0, "runs_changed": 0, "events_removed": 0}
    if not path.is_file():
        return stats
    try:
        conn = sqlite3.connect(path, timeout=10)
    except sqlite3.Error:
        return stats
    try:
        try:
            rows = list(
                conn.execute(
                    """
                    SELECT r.id, r.thread_id, r.events
                    FROM agent_runs r
                    WHERE r.events LIKE '%exceeded before any response%'
                       OR r.events LIKE '%exceeded max retries count%'
                    """
                )
            )
        except sqlite3.Error:
            return stats  # different schema (older runtime): nothing to do

        for row_id, thread_id, raw in rows:
            stats["runs_scanned"] += 1
            try:
                events = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(events, list):
                continue
            later = bool(
                conn.execute(
                    "SELECT 1 FROM agent_runs WHERE thread_id = ? AND id > ? LIMIT 1", (thread_id, row_id)
                ).fetchone()
            )
            kept = [e for e in events if not is_stale_run_error(e, current_budget, later)]
            removed = len(events) - len(kept)
            if not removed:
                continue
            conn.execute("UPDATE agent_runs SET events = ? WHERE id = ?", (json.dumps(kept), row_id))
            stats["runs_changed"] += 1
            stats["events_removed"] += removed
        conn.commit()
    finally:
        conn.close()
    return stats
