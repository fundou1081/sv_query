"""P194.5.12 — output reg ports stay in `ports`, matching `connections`."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_output_reg_port_is_reported(tmp_path):
    sv = tmp_path / "regport.sv"
    sv.write_text(
        "module top(input logic clk, input logic a, output reg y);\n"
        "  always_ff @(posedge clk) y <= a;\n"
        "endmodule\n")
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "ports", "top", "-f", str(sv), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-400:]
    data = json.loads(proc.stdout)
    assert data["count"] == 3
    y = next(p for p in data["ports"] if p["port"] == "y")
    assert y["direction"] == "output"
