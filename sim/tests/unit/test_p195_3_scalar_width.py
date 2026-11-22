"""P195.3 — scalar is one bit, not the historical [1,0] / width=2 range."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(path: Path, *args: str, no_cache: bool = True) -> dict:
    cmd = [sys.executable, "run_cli.py", *args, "--file", str(path), "--json"]
    if no_cache:
        cmd.append("--no-cache")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


def test_scalar_port_width_is_one_bit(tmp_path):
    sv = tmp_path / "scalar.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    nodes = _run(sv, "graph", "nodes", "--detail")["result"]["nodes"]
    widths = {n["id"]: n["width"] for n in nodes}
    assert widths["top.a"] == [0, 0]
    assert widths["top.y"] == [0, 0]

    drivers = _run(sv, "drivers", "top.y")["result"]["signals"][0]["drivers"]
    assert drivers[0]["width"] == 1
    assert drivers[0]["width_msb"] == 0
    assert drivers[0]["width_lsb"] == 0


def test_two_bit_vector_keeps_width_two(tmp_path):
    sv = tmp_path / "vector.sv"
    sv.write_text(
        "module top(input logic [1:0] a, output logic [1:0] y); assign y = a; endmodule\n")
    nodes = _run(sv, "graph", "nodes", "--detail")["result"]["nodes"]
    widths = {n["id"]: n["width"] for n in nodes}
    assert widths["top.a"] == [1, 0]
    assert widths["top.y"] == [1, 0]

    drivers = _run(sv, "drivers", "top.y")["result"]["signals"][0]["drivers"]
    assert drivers[0]["width"] == 2


def test_trace_profile_scalar_width_matches_type(tmp_path):
    sv = tmp_path / "profile.sv"
    sv.write_text("module top(input logic a, output logic y); assign y = a; endmodule\n")
    result = _run(sv, "trace", "profile", "top.a", no_cache=False)
    profile = result["result"]["signals"][0]
    assert profile["width"] == [0, 0]
    assert profile["type"]["bit_width"] == 1
    assert profile["width"][1] - profile["width"][0] + 1 == profile["type"]["bit_width"]
