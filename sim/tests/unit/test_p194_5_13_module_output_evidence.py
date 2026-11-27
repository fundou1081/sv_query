"""P194.5.13 — module-output evidence follows connection edges to the driver."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_output_port_and_connected_top_signal_have_driver_evidence(tmp_path):
    sv = tmp_path / "module_output.sv"
    sv.write_text(
        "module sub(input logic clk, input logic d, output logic q);\n"
        "  always_ff @(posedge clk) q <= d;\n"
        "endmodule\n"
        "module top(input logic clk, input logic d, output logic y);\n"
        "  sub u(.clk(clk), .d(d), .q(y));\n"
        "endmodule\n")
    for signal in ("top.u.q", "top.y"):
        proc = subprocess.run(
            [sys.executable, "run_cli.py", "trace", "evidence", signal,
             "-f", str(sv), "--json", "--no-cache"],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr[-400:]
        ev = json.loads(proc.stdout)["result"]["signals"][0]["evidence"]
        assert ev["source_location"]["line_start"] == 2
        assert "q <= d" in ev["source_text"]
        assert ev["is_verified"] is True
