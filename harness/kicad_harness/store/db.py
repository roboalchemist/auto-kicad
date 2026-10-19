"""The harness database: one SQLite file at ``config.db_path``. See DESIGN.md, "Store"."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from ._common import from_json, to_json
from .review import Review
from .runs import Runs
from .steering import SCHEMA as STEERING_SCHEMA
from .steering import Steering

if TYPE_CHECKING:
    from ..config import Config

SCHEMA_VERSION = 3

# runs.thread_id and agent_history.thread_id are AG-UI thread ids; thread_replies.thread_id and
# thread_status_log.thread_id point at review threads.
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS threads (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        design        TEXT    NOT NULL,
        number        INTEGER NOT NULL,
        kind          TEXT    NOT NULL,
        source        TEXT    NOT NULL,
        severity      TEXT    NOT NULL,
        tags          TEXT    NOT NULL DEFAULT '[]',
        status        TEXT    NOT NULL,
        title         TEXT,
        body          TEXT    NOT NULL,
        author        TEXT    NOT NULL,
        created_at    REAL    NOT NULL,
        created_sha   TEXT,
        anchor        TEXT    NOT NULL,
        view          TEXT,
        addressed_sha TEXT,
        resolved_sha  TEXT,
        updated_at    REAL    NOT NULL,
        UNIQUE (design, number)
    )
    """,
    "CREATE INDEX IF NOT EXISTS threads_design_updated ON threads (design, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS thread_replies (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id  INTEGER NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
        author     TEXT    NOT NULL,
        body       TEXT    NOT NULL,
        created_at REAL    NOT NULL,
        sha        TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS thread_replies_thread ON thread_replies (thread_id)",
    """
    CREATE TABLE IF NOT EXISTS thread_status_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id INTEGER NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
        status    TEXT    NOT NULL,
        actor     TEXT    NOT NULL,
        at        REAL    NOT NULL,
        sha       TEXT,
        note      TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS thread_status_log_thread ON thread_status_log (thread_id)",
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id      TEXT    PRIMARY KEY,
        design      TEXT    NOT NULL,
        thread_id   TEXT,
        model       TEXT,
        prompt      TEXT,
        source      TEXT    NOT NULL,
        status      TEXT    NOT NULL,
        started_at  REAL    NOT NULL,
        finished_at REAL,
        updated_at  REAL    NOT NULL,
        usage       TEXT,
        error       TEXT,
        last_seq    INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS runs_design_started ON runs (design, started_at)",
    "CREATE INDEX IF NOT EXISTS runs_design_updated ON runs (design, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS run_events (
        run_id TEXT    NOT NULL REFERENCES runs (run_id) ON DELETE CASCADE,
        seq    INTEGER NOT NULL,
        type   TEXT,
        at     REAL    NOT NULL,
        data   TEXT    NOT NULL,
        PRIMARY KEY (run_id, seq)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE IF NOT EXISTS version_meta (
        design     TEXT NOT NULL,
        sha        TEXT NOT NULL,
        board_hash TEXT,
        metrics    TEXT,
        diff       TEXT,
        summary    TEXT,
        summary_at REAL,
        updated_at REAL NOT NULL,
        PRIMARY KEY (design, sha)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_history (
        thread_id  TEXT PRIMARY KEY,
        design     TEXT,
        data       BLOB NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    *STEERING_SCHEMA,
)


class Store:
    """The harness database: review threads, agent runs, version metadata and chat history.

    One SQLite file in WAL mode, shared by the server and CLI processes. Inside a process, one
    connection (``check_same_thread=False``) is shared by every thread and each statement runs
    under ``lock``. Writes use ``BEGIN IMMEDIATE`` so a writer in another process waits up to
    ``busy_timeout`` (5 s) instead of failing.

    Attributes: ``review`` (:class:`Review`), ``runs`` (:class:`Runs`), ``versions``
    (:class:`VersionMeta`) and ``history`` (:class:`History`).
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.path = Path(config.db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._depth = 0
        self._writing = False
        self.conn = sqlite3.connect(str(self.path), timeout=5.0, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        self.review = Review(self)
        self.runs = Runs(self)
        self.versions = VersionMeta(self)
        self.history = History(self)
        self.steering = Steering(self)

    def _create_schema(self) -> None:
        with self.tx() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"{self.path} has schema v{version}; this code knows v{SCHEMA_VERSION}")
            for statement in _SCHEMA:
                conn.execute(statement)
            # Columns added after the first release: ALTER TABLE only when missing.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(version_meta)")}
            for name, kind in (("diff", "TEXT"), ("summary", "TEXT"), ("summary_at", "REAL")):
                if name not in columns:
                    conn.execute(f"ALTER TABLE version_meta ADD COLUMN {name} {kind}")
            if version < SCHEMA_VERSION:
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    # ------------------------------------------------------------------ settings

    def get_setting(self, key: str) -> str | None:
        """A persisted preference (e.g. the selected model), or None."""
        with self.tx(write=False) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        import time as _time

        with self.tx() as conn:
            conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, _time.time()),
            )

    @contextmanager
    def tx(self, write: bool = True) -> Iterator[sqlite3.Connection]:
        """Hold the connection for one transaction and yield it.

        ``write=True`` starts ``BEGIN IMMEDIATE``; ``write=False`` takes a consistent read
        snapshot. Nested calls join the outer transaction, except that a write can't nest
        inside a read. The transaction commits when the outermost block exits normally and
        rolls back if it raises.
        """
        with self.lock:
            if self._depth:
                if write and not self._writing:
                    raise RuntimeError("can't start a write inside a read transaction")
                self._depth += 1
                try:
                    yield self.conn
                finally:
                    self._depth -= 1
                return
            self.conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self._depth, self._writing = 1, write
            try:
                yield self.conn
                self.conn.execute("COMMIT")
            except BaseException:
                if self.conn.in_transaction:
                    self.conn.execute("ROLLBACK")
                raise
            finally:
                self._depth, self._writing = 0, False

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Run one read statement and return all rows."""
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        """Run one read statement and return the first row, or ``None``."""
        with self.lock:
            return self.conn.execute(sql, params).fetchone()

    def close(self) -> None:
        """Close the connection. The store can't be used afterwards."""
        with self.lock:
            self.conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class VersionMeta:
    """Cache of per-version metadata: ``(design, sha) -> {"board_hash", "metrics"}``.

    Commits never change, so entries never go stale; the server fills them lazily.
    """

    def __init__(self, store: Store) -> None:
        self._store = store

    def get(self, design: str, sha: str) -> dict[str, Any] | None:
        """Cached metadata for a version (``board_hash``, ``metrics``, ``diff``, ``summary``)."""
        row = self._store.query_one(
            "SELECT board_hash, metrics, diff, summary, summary_at FROM version_meta "
            "WHERE design = ? AND sha = ?", (design, sha)
        )
        if row is None:
            return None
        return {
            "board_hash": row["board_hash"],
            "metrics": from_json(row["metrics"]),
            "diff": from_json(row["diff"]),
            "summary": row["summary"],
            "summary_at": row["summary_at"],
        }

    def put(self, design: str, sha: str, board_hash: str | None = None, metrics: dict[str, Any] | None = None,
            *, diff: dict[str, Any] | None = None, summary: str | None = None) -> None:
        """Store metadata for a version. A ``None`` field keeps whatever is already cached."""
        with self._store.tx() as conn:
            conn.execute(
                """
                INSERT INTO version_meta (design, sha, board_hash, metrics, diff, summary, summary_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (design, sha) DO UPDATE SET
                    board_hash = COALESCE(excluded.board_hash, version_meta.board_hash),
                    metrics = COALESCE(excluded.metrics, version_meta.metrics),
                    diff = COALESCE(excluded.diff, version_meta.diff),
                    summary = COALESCE(excluded.summary, version_meta.summary),
                    summary_at = COALESCE(excluded.summary_at, version_meta.summary_at),
                    updated_at = excluded.updated_at
                """,
                (design, sha, board_hash, to_json(metrics), to_json(diff), summary,
                 time.time() if summary else None, time.time()),
            )


class History:
    """Agent message history per AG-UI thread, stored as opaque bytes (for example
    ``ModelMessagesTypeAdapter.dump_json(messages)``)."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def save(self, thread_id: str, design: str, data: bytes) -> None:
        """Replace the stored history of ``thread_id``. ``str`` data is stored as UTF-8."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"history data must be bytes, not {type(data).__name__}")
        with self._store.tx() as conn:
            conn.execute(
                """
                INSERT INTO agent_history (thread_id, design, data, updated_at) VALUES (?, ?, ?, ?)
                ON CONFLICT (thread_id) DO UPDATE SET
                    design = excluded.design, data = excluded.data, updated_at = excluded.updated_at
                """,
                (thread_id, design, bytes(data), time.time()),
            )

    def load(self, thread_id: str) -> bytes | None:
        """Return the stored history of ``thread_id``, or ``None`` if there is none."""
        row = self._store.query_one("SELECT data FROM agent_history WHERE thread_id = ?", (thread_id,))
        return None if row is None else bytes(row["data"])
