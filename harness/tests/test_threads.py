"""Stale token-limit errors must not be replayed once a thread has moved on."""

from __future__ import annotations

import json
import sqlite3

from kicad_harness.store.threads import is_budget_error, is_stale_run_error, prune_stale_token_errors

LIMIT_ERR = {
    "type": "RUN_ERROR",
    "message": (
        "Model token limit (20000) exceeded before any response was generated. Increase the "
        "`max_tokens` model setting, or simplify the prompt to result in a shorter response "
        "that will fit within the limit."
    ),
}
OTHER_ERR = {"type": "RUN_ERROR", "message": "something else broke"}


def _db(path, runs):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE agent_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT, run_id TEXT, parent_run_id TEXT, events TEXT, input TEXT)")
    for thread_id, events in runs:
        conn.execute(
            "INSERT INTO agent_runs (thread_id, run_id, events, input) VALUES (?, ?, ?, ?)",
            (thread_id, "run", json.dumps(events), "{}"),
        )
    conn.commit()
    conn.close()


def test_detects_both_budget_messages() -> None:
    assert is_budget_error(LIMIT_ERR)
    assert is_budget_error({"type": "RUN_ERROR", "message": "Tool 'x' exceeded max retries count of 5"})
    assert not is_budget_error(OTHER_ERR)
    assert not is_budget_error({"type": "RUN_FINISHED"})
    # Staleness needs a reason: a later run, or a changed limit.
    assert is_stale_run_error(LIMIT_ERR, None, superseded=True)
    assert not is_stale_run_error(LIMIT_ERR)
    assert is_stale_run_error(LIMIT_ERR, current_budget=64000)   # quoted 20000 != 64000
    assert not is_stale_run_error(LIMIT_ERR, current_budget=20000)


def test_prunes_only_threads_that_moved_on(tmp_path) -> None:
    db = tmp_path / "threads.db"
    ok = [{"type": "RUN_STARTED"}, {"type": "RUN_FINISHED"}]
    # thread A: failed, then succeeded -> the error is stale and goes
    # thread B: its only run failed -> keep it, it is still the current state
    _db(db, [("A", [{"type": "RUN_STARTED"}, LIMIT_ERR]), ("A", ok), ("B", [LIMIT_ERR])])

    stats = prune_stale_token_errors(db)
    assert stats["events_removed"] == 1, stats
    assert stats["runs_changed"] == 1

    conn = sqlite3.connect(db)
    a = [json.loads(r[0]) for r in conn.execute("SELECT events FROM agent_runs WHERE thread_id='A' ORDER BY id")]
    b = json.loads(conn.execute("SELECT events FROM agent_runs WHERE thread_id='B'").fetchone()[0])
    conn.close()
    assert not any(is_budget_error(e) for run in a for e in run)
    assert any(is_budget_error(e) for e in b), "the newest run's error must survive"
    # Everything else is untouched.
    assert a[1] == ok


def test_other_errors_are_kept(tmp_path) -> None:
    db = tmp_path / "threads.db"
    _db(db, [("A", [OTHER_ERR]), ("A", [{"type": "RUN_FINISHED"}])])
    assert prune_stale_token_errors(db)["events_removed"] == 0


def test_missing_database_is_not_an_error(tmp_path) -> None:
    assert prune_stale_token_errors(tmp_path / "nope.db") == {
        "runs_scanned": 0, "runs_changed": 0, "events_removed": 0,
    }


def test_is_idempotent(tmp_path) -> None:
    db = tmp_path / "threads.db"
    _db(db, [("A", [LIMIT_ERR]), ("A", [{"type": "RUN_FINISHED"}])])
    assert prune_stale_token_errors(db)["events_removed"] == 1
    assert prune_stale_token_errors(db)["events_removed"] == 0


def test_prune_reasoning_strips_token_deltas(tmp_path) -> None:
    """Reasoning streams are ~99% of stored events and are useless for replay."""
    from kicad_harness.store.threads import prune_reasoning

    db = tmp_path / "threads.db"
    events = (
        [{"type": "REASONING_MESSAGE_CONTENT", "delta": "hmm"} for _ in range(50)]
        + [{"type": "REASONING_START"}, {"type": "TOOL_CALL_START", "toolCallName": "check"}]
        + [{"type": "TEXT_MESSAGE_CONTENT", "delta": "done"}]
    )
    _db(db, [("A", events)])
    stats = prune_reasoning(db)
    assert stats["events_removed"] == 51, stats

    conn = sqlite3.connect(db)
    kept = json.loads(conn.execute("SELECT events FROM agent_runs").fetchone()[0])
    conn.close()
    assert [e["type"] for e in kept] == ["TOOL_CALL_START", "TEXT_MESSAGE_CONTENT"]
