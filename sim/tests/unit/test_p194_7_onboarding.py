"""P194.7 — quickstart links and first-run commands work."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FL = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _run(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "run_cli.py", *args, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


def test_quickstart_is_linked_and_first_queries_work():
    readme = (ROOT / "README.md").read_text()
    quickstart = (ROOT / "docs/QUICKSTART.md").read_text()
    assert "docs/QUICKSTART.md" in readme
    assert "Scheduler_minimal.s0_reg" in quickstart

    assert "schema_version" in _run("capabilities")
    assert _run("graph", "nodes", "--filelist", FL)["ok"] is True
    drivers = _run("drivers", "Scheduler_minimal.s0_reg", "--filelist", FL)
    assert drivers["ok"] is True and drivers["result"]["signals"]
    quiet = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "Scheduler_minimal.s0_reg",
         "--filelist", FL, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert quiet.returncode == 0 and quiet.stderr == ""
    missing = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "Scheduler_minimal.missing",
         "--filelist", FL, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    payload = json.loads(missing.stdout)
    assert payload["ok"] is False
    assert payload["result"]["signals"][0]["resolution"] == "not_found"


def test_quickstart_session_example_works():
    sys.path.insert(0, str(ROOT / "src"))
    from sv_query.graph_session import GraphSession

    gs = GraphSession(filelist=FL, use_cache=False)
    try:
        assert gs.drivers("Scheduler_minimal.s0_reg")["count"] >= 1
    finally:
        gs.close()
