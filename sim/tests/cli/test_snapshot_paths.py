"""[P92/D] paths --from-snapshot parity."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FL = ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"


def _run(*args, env):
    return subprocess.run(["sv_query", *args], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, timeout=60)


def test_paths_from_snapshot_matches_filelist():
    snap_dir = tempfile.mkdtemp(prefix="svq_d_paths_")
    env = {**os.environ, "SVQ_SNAPSHOT_DIR": snap_dir}
    r = _run("snapshot", "save", str(FL), "--filelist", str(FL),
             "--tag", "d_paths", "--json", env=env)
    assert r.returncode == 0, r.stderr[-300:]
    src, dst = "uart_top.rx_fifo.push_i", "uart_top.rx_fifo.count_q"
    live = _run("paths", src, dst, "--filelist", str(FL), "--json", env=env)
    snap = _run("paths", src, dst, "--from-snapshot", "d_paths", "--json", env=env)
    assert live.returncode == snap.returncode == 0
    a = json.loads(live.stdout)
    b = json.loads(snap.stdout)
    assert a["found"] is b["found"] is True
    assert a["path"] == b["path"]


def test_paths_from_snapshot_invalid_and_mutually_exclusive():
    env = {**os.environ, "SVQ_SNAPSHOT_DIR": tempfile.mkdtemp(prefix="svq_d_bad_")}
    r = _run("paths", "a", "b", "--from-snapshot", "missing", "--json", env=env)
    assert r.returncode != 0
    assert json.loads(r.stdout)["ok"] is False

    r = _run("paths", "a", "b", "--from-snapshot", "missing",
             "--filelist", str(FL), "--json", env=env)
    assert r.returncode != 0
    assert "mutually exclusive" in json.loads(r.stdout)["error"].lower()
