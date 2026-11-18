"""P182.1a — read-only envelope inventory (no command execution)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/check_envelope_contract.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


def test_inventory_counts_and_layers():
    proc = _run("--inventory", "--json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["mode"] == "read-only-static"
    assert data["counts"] == {
        "total": 45,
        "by_layer": {"core": 39, "exp": 6},
        "by_envelope": {"direct": 13, "standard": 32},
        "aliases": 2,
    }
    assert data["envelope_mismatches"] == []


def test_standard_and_direct_rows_are_explicit():
    rows = json.loads(_run("--inventory", "--json").stdout)["rows"]
    assert len(rows) == 45
    standard = {r["name"] for r in rows if r["envelope"] == "standard"}
    assert "stats" in standard
    direct = {r["name"] for r in rows if r["envelope"] == "direct"}
    assert direct == {
        "instances", "connections", "hierarchy", "params", "ports", "class",
        "search", "capabilities", "paths", "snapshot save", "snapshot list",
        "snapshot compare", "snapshot delete",
    }
    assert all(r["shape"] in {"standard", "direct-contract", "direct-no-contract"} for r in rows)
    paths = next(r for r in rows if r["name"] == "paths")
    assert paths["envelope"] == "direct"
    assert paths["envelope_mismatch"] is False


def test_inventory_text_output_shape_and_no_command_execution(tmp_path):
    env = dict(__import__("os").environ)
    env["SVQ_SNAPSHOT_DIR"] = str(tmp_path / "snap")
    proc = subprocess.run(
        [sys.executable, "tools/check_envelope_contract.py", "--inventory"],
        cwd=ROOT, capture_output=True, text=True, timeout=30, env=env,
    )
    assert proc.returncode == 0
    assert "total=45" in proc.stdout
    assert "by_envelope=" in proc.stdout
    assert not (tmp_path / "snap").exists()
