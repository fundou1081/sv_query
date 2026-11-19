"""P182.6 — old snapshot without MIG must fail explicitly."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILELIST = ROOT / "sim/tests/fixtures/minimal_3module/filelist.f"


def _snapshot_without_mig(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    snap_dir = tmp_path / "snaps"
    snap_dir.mkdir()
    env = dict(os.environ, SVQ_SNAPSHOT_DIR=str(snap_dir))
    save = subprocess.run(
        [sys.executable, "run_cli.py", "snapshot", "save", str(FILELIST),
         "--filelist", str(FILELIST), "--tag", "legacy_no_mig", "--json"],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=120,
    )
    assert save.returncode == 0, save.stderr[-300:]
    snap = next(snap_dir.glob("*.json"))
    data = json.loads(snap.read_text(encoding="utf-8"))
    data.pop("module_graph", None)
    snap.write_text(json.dumps(data), encoding="utf-8")
    return snap, env


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", *args, "--from-snapshot", "legacy_no_mig", "--json"],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=120,
    )


def test_mig_commands_fail_explicitly_without_module_graph(tmp_path):
    _, env = _snapshot_without_mig(tmp_path)
    cases = {
        "instances": ["instances"],
        "hierarchy": ["hierarchy"],
        "connections": ["connections", "top_minimal.sa1"],
    }
    for command, args in cases.items():
        proc = _run(args, env)
        assert proc.returncode == 1, (command, proc.stdout, proc.stderr)
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False, command
        assert payload["error_code"] == "E_SNAPSHOT_NO_MIG", command
        assert "module_graph" in payload["error"], command
