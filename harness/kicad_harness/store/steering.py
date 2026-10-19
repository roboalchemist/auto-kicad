"""Messages for the agent while it is working ("steering"). See DESIGN.md, "Steering".

CopilotKit can't add a message to an AG-UI run that is already streaming, so the UI (or the CLI,
from another terminal) stores the message here. The running agent claims pending messages at its
next model request and sees them as user input. Messages not aimed at a specific run go to whichever
run of the design asks first, which is the next run if none is active.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .db import Store

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS steering (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        design        TEXT    NOT NULL,
        run_id        TEXT,
        message       TEXT    NOT NULL,
        author        TEXT    NOT NULL,
        created_at    REAL    NOT NULL,
        delivered_at  REAL,
        delivered_run TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS steering_pending ON steering (design, delivered_at)",
)


class Steering:
    """Pending and delivered steering messages, per design."""

    def __init__(self, store: Store) -> None:
        self._store = store

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return {k: row[k] for k in row.keys()}

    def push(self, design: str, message: str, *, author: str = "user", run_id: str | None = None) -> dict[str, Any]:
        """Queue `message` for the design's running agent (or for `run_id` only)."""
        message = message.strip()
        if not message:
            raise ValueError("message is empty")
        with self._store.tx() as conn:
            cur = conn.execute(
                "INSERT INTO steering (design, run_id, message, author, created_at) VALUES (?, ?, ?, ?, ?)",
                (design, run_id, message, author, time.time()),
            )
            return self._row(conn.execute("SELECT * FROM steering WHERE id = ?", (cur.lastrowid,)).fetchone())

    def take(self, design: str, run_id: str) -> list[dict[str, Any]]:
        """Claim every pending message for this run, oldest first, marking them delivered."""
        now = time.time()
        with self._store.tx() as conn:
            rows = conn.execute(
                "SELECT * FROM steering WHERE design = ? AND delivered_at IS NULL AND (run_id IS NULL OR run_id = ?)"
                " ORDER BY id",
                (design, run_id),
            ).fetchall()
            if rows:
                conn.executemany(
                    "UPDATE steering SET delivered_at = ?, delivered_run = ? WHERE id = ?",
                    [(now, run_id, row["id"]) for row in rows],
                )
            return [{**self._row(row), "delivered_at": now, "delivered_run": run_id} for row in rows]

    def list(self, design: str, limit: int = 50) -> list[dict[str, Any]]:
        """Recent messages, newest first."""
        rows = self._store.query("SELECT * FROM steering WHERE design = ? ORDER BY id DESC LIMIT ?", (design, limit))
        return [self._row(row) for row in rows]

    def last_updated(self, design: str) -> float:
        row = self._store.query_one(
            "SELECT MAX(MAX(created_at), COALESCE(MAX(delivered_at), 0)) AS t FROM steering WHERE design = ?",
            (design,),
        )
        return float(row["t"] or 0.0) if row else 0.0
