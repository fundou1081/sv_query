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


def test_compact_preserves_depth_truncation_marker(tmp_path):
    sv = tmp_path / "chain.sv"
    sv.write_text(
        "module top(input logic a, input logic b, input logic c, output logic y);\n"
        "  logic m1, m2;\n"
        "  assign m1 = a & b;\n"
        "  assign m2 = m1 | c;\n"
        "  assign y = m2;\n"
        "endmodule\n")
    proc = _run("drivers", "top.y", "--file", str(sv), "--depth", "1",
                "--no-cache", "--compact")
    assert proc.returncode == 0, proc.stderr[-400:]
    row = json.loads(proc.stdout)["result"]["signals"][0]
    assert row["truncated_by_depth"] is True


def test_compact_preserves_function_call_unknown(tmp_path):
    sv = tmp_path / "fn.sv"
    sv.write_text(
        "module top(input logic a, input logic cond, output logic y);\n"
        "  function automatic logic f(input logic x); return ~x; endfunction\n"
        "  always_comb begin\n"
        "    if (cond) y = f(a);\n"
        "    else y = 1'b0;\n"
        "  end\n"
        "endmodule\n")
    proc = _run("drivers", "top.y", "--file", str(sv), "--no-cache", "--compact")
    assert proc.returncode == 0, proc.stderr[-400:]
    row = json.loads(proc.stdout)["result"]["signals"][0]
    assert row["function_call"] is True
    assert any(item.get("function_call") for item in row["drivers"])
