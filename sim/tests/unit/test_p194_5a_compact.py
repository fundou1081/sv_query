"""P194.5a — compact capability and result surfaces are additive and small."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", *args, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )


def test_capabilities_compact_is_much_smaller():
    full = _run("capabilities")
    compact = _run("capabilities", "--compact")
    assert full.returncode == compact.returncode == 0
    assert len(compact.stdout) * 3 < len(full.stdout)
    data = json.loads(compact.stdout)
    assert len(data["commands"]) == 39
    assert "json_contract" not in data
    assert "verify_claim" in data["session"]["ops"]


def test_drivers_compact_drops_verbose_condition_trees(tmp_path):
    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    proc = _run("drivers", "top.y", "--file", str(sv), "--no-cache", "--compact")
    assert proc.returncode == 0, proc.stderr[-400:]
    data = json.loads(proc.stdout)
    assert data["result"]["compact"] is True
    driver = data["result"]["signals"][0]["drivers"][0]
    assert "condition_paths" not in driver
    assert "id" in driver and "condition" in driver


def test_evidence_compact_keeps_only_source_projection(tmp_path):
    sv = tmp_path / "onebit.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    proc = _run("trace", "evidence", "top.y", "--file", str(sv),
                "--no-cache", "--compact")
    assert proc.returncode == 0, proc.stderr[-400:]
    data = json.loads(proc.stdout)
    assert data["result"]["compact"] is True
    ev = data["evidence"]
    assert set(ev) == {"signal", "source_location", "source_text",
                       "is_verified", "credibility_score"}
    assert "enclosing_chain" not in ev
