"""P198.10c — depth=1 bit query keeps bit-driver authority."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _sv(tmp_path: Path) -> Path:
    sv = tmp_path / "asc.sv"
    sv.write_text(
        "module top(input logic [0:7] a, output logic [0:1] y0);\n"
        "  assign y0 = a[2:5];\n"
        "endmodule\n")
    return sv


def test_depth1_bit_fanin_has_no_duplicate_aggregate(tmp_path):
    result = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "top.y0[0]", "--file",
         str(_sv(tmp_path)), "--depth", "1", "--json", "--compact", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-400:]
    ids = {d["id"] for d in json.loads(result.stdout)["result"]["signals"][0]["drivers"]}
    assert ids == {"top.a[5]"}


def test_depth1_bus_fanin_keeps_aggregate(tmp_path):
    result = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "top.y0", "--file",
         str(_sv(tmp_path)), "--depth", "1", "--json", "--compact", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-400:]
    ids = {d["id"] for d in json.loads(result.stdout)["result"]["signals"][0]["drivers"]}
    assert ids == {"top.a[2:5]"}


def test_mixed_part_select_and_bus_driver_keeps_bus(tmp_path):
    sv = tmp_path / "mixed.sv"
    sv.write_text(
        "module top(input logic [0:7] a, input logic [0:1] b,\n"
        "           output wire [0:1] y0);\n"
        "  assign y0 = a[2:5];\n"
        "  assign y0 = b;\n"
        "endmodule\n")
    result = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "top.y0[0]", "--file",
         str(sv), "--depth", "1", "--json", "--compact", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-400:]
    ids = {d["id"] for d in json.loads(result.stdout)["result"]["signals"][0]["drivers"]}
    assert ids == {"top.a[5]", "top.b"}
