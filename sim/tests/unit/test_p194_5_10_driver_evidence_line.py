"""P194.5.10 — drivers --evidence must bind the assignment, not condition text."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_driver_evidence_uses_assignment_line(tmp_path):
    sv = tmp_path / "trap_line.sv"
    sv.write_text(
        "module top(input logic clk, state, output reg trap);\n"
        "  logic dbg;\n"
        "  always_comb begin\n"
        "    if (state) dbg = \"trap\";\n"
        "  end\n"
        "  always_ff @(posedge clk) begin\n"
        "    trap <= 0;\n"
        "    if (state) trap <= 1;\n"
        "  end\n"
        "endmodule\n")
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "top.trap", "-f", str(sv),
         "--json", "--evidence", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    row = json.loads(proc.stdout)["result"]["signals"][0]
    conditioned = [d for d in row["drivers"] if d.get("condition")]
    assert conditioned
    lines = [d["evidence"]["line"] for d in conditioned]
    assert lines and all(lines), conditioned
    source = sv.read_text().splitlines()
    assert all("trap <=" in source[line - 1] for line in lines)
    assert not any('dbg = "trap"' in source[line - 1] for line in lines)
