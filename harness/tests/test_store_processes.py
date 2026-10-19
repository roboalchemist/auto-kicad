"""The store and workspaces under real concurrent processes (a server and a CLI run at once)."""

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from kicad_harness.config import Config
from kicad_harness.store import Store, Workspace

FIXTURE = Path(__file__).parent / "fixtures" / "blinker.kicad_pcb"

WRITER = textwrap.dedent("""
    import sys
    from pathlib import Path
    from kicad_harness.config import Config
    from kicad_harness.store import Store, Workspace

    home, tag = Path(sys.argv[1]), sys.argv[2]
    config = Config(home=home)
    ws = Workspace.open(config, "blinker")
    with Store(config) as store:
        for i in range(15):
            store.runs.event("run-1", {"type": "X", "writer": tag, "n": i})
            store.review.create("blinker", None, {"kind": "point", "x": 1.0, "y": 2.0}, f"{tag} {i}")
            with ws.lock:
                (ws.path / f"{tag}.txt").write_text(f"{i}\\n")
                assert ws.commit(f"{tag} {i}", author="agent") is not None
""")


def test_store_and_workspace_across_processes(tmp_path):
    config = Config(home=tmp_path / "home")
    src = tmp_path / "blinker.kicad_pcb"
    shutil.copy(FIXTURE, src)
    ws = Workspace.create(config, "blinker", src)
    with Store(config) as store:
        store.runs.start("blinker", run_id="run-1", thread_id="t", model="m", prompt="p")

    writers = [
        subprocess.Popen([sys.executable, "-c", WRITER, str(config.home), tag], stderr=subprocess.PIPE, text=True)
        for tag in ("server", "cli", "third")
    ]
    for proc in writers:
        _, stderr = proc.communicate(timeout=120)
        assert proc.returncode == 0, stderr

    with Store(config) as store:
        events = store.runs.events("run-1")
        assert [e["seq"] for e in events] == list(range(1, 46))
        for tag in ("server", "cli", "third"):
            assert [e["event"]["n"] for e in events if e["event"]["writer"] == tag] == list(range(15))
        threads = store.review.list("blinker")
        assert [t["number"] for t in threads] == list(range(1, 46))
    log = ws.log(limit=None)
    assert len(log) == 46
    assert sorted(v["subject"] for v in log[:-1]) == sorted(f"{tag} {i}" for tag in ("server", "cli", "third")
                                                           for i in range(15))
    assert not ws.dirty()
