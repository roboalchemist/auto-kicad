"""Steering messages: queued by the user, claimed once by the running agent."""

import pytest

from kicad_harness.config import Config
from kicad_harness.store.db import Store


@pytest.fixture
def store(tmp_path):
    with Store(Config(home=tmp_path).ensure_dirs()) as s:
        yield s


def test_take_delivers_pending_messages_once_in_order(store):
    store.steering.push("d", "first")
    store.steering.push("d", "second")
    store.steering.push("other", "not mine")
    taken = store.steering.take("d", "run-1")
    assert [m["message"] for m in taken] == ["first", "second"]
    assert all(m["delivered_run"] == "run-1" and m["delivered_at"] for m in taken)
    assert store.steering.take("d", "run-1") == []
    assert store.steering.take("d", "run-2") == []
    assert [m["message"] for m in store.steering.take("other", "run-9")] == ["not mine"]


def test_targeted_messages_wait_for_their_run(store):
    store.steering.push("d", "for run 2", run_id="run-2")
    assert store.steering.take("d", "run-1") == []
    assert [m["message"] for m in store.steering.take("d", "run-2")] == ["for run 2"]


def test_list_and_last_updated(store):
    assert store.steering.last_updated("d") == 0.0
    store.steering.push("d", "hello")
    first = store.steering.last_updated("d")
    store.steering.take("d", "run-1")
    assert store.steering.last_updated("d") >= first > 0
    listed = store.steering.list("d")
    assert listed[0]["message"] == "hello" and listed[0]["delivered_run"] == "run-1"


def test_empty_message_rejected(store):
    with pytest.raises(ValueError):
        store.steering.push("d", "   ")
