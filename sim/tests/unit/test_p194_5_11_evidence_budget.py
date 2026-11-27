"""P194.5.11 — evidence payload is bounded without losing verification."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_large_enclosing_block_is_truncated_and_still_verified(tmp_path):
    padding = "\n".join(f"    // padding line {i}" for i in range(400))
    sv = tmp_path / "large_evidence.sv"
    sv.write_text(
        "module top(input logic clk, d, output logic q);\n"
        "  always_ff @(posedge clk) begin\n"
        "    q <= d;\n"
        f"{padding}\n"
        "  end\n"
        "endmodule\n")
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "trace", "evidence", "top.q",
         "-f", str(sv), "--json", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    assert len(proc.stdout.encode()) < 50_000, len(proc.stdout.encode())
    ev = json.loads(proc.stdout)["result"]["signals"][0]["evidence"]
    assert ev["is_verified"] is True
    assert ev["enclosing_always"]["truncated"] is True
    assert ev["enclosing_always"]["original_length"] > 1_600
    assert ev["enclosing_always"]["text"].endswith("[truncated]")
