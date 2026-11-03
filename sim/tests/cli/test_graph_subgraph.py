"""[iter_362 / PLAN P60] graph subgraph 局部子图契约。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = """
module top(input clk, input [3:0] a, b, output reg [3:0] y);
  wire [3:0] mid;
  assign mid = a;
  always_ff @(posedge clk) y <= mid;
endmodule
"""


def _run(tmp_path: Path, *args: str):
    sv = tmp_path / "t.sv"
    sv.write_text(SRC)
    cmd = ["sv_query", "graph", "subgraph", *args, "-f", str(sv), "--json"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(ROOT))


def _data(tmp_path: Path, *args: str) -> dict:
    r = _run(tmp_path, *args)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)


def test_subgraph_depth1_boundary(tmp_path):
    d = _data(tmp_path, "top.y", "--depth", "1", "--direction", "in",
              "--edge-kinds", "driver,connection")
    ids = {n["id"] for n in d["result"]["nodes"]}
    assert "top.y" in ids and "top.mid" in ids
    assert d["result"]["truncated"]["depth"] is True
    assert "top.a" in d["result"]["boundary"]


def test_subgraph_depth0_only_seed(tmp_path):
    d = _data(tmp_path, "top.y", "--depth", "0", "--direction", "in")
    assert [n["id"] for n in d["result"]["nodes"]] == ["top.y"]
    assert d["result"]["truncated"]["depth"] is True


def test_subgraph_budget_boundary(tmp_path):
    d = _data(tmp_path, "top.y", "--depth", "2", "--direction", "in",
              "--max-nodes", "1")
    assert [n["id"] for n in d["result"]["nodes"]] == ["top.y"]
    assert d["result"]["truncated"]["nodes"] is True
    assert "top.mid" in d["result"]["boundary"]


def test_subgraph_direction_out(tmp_path):
    d = _data(tmp_path, "top.a", "--depth", "1", "--direction", "out")
    ids = {n["id"] for n in d["result"]["nodes"]}
    assert "top.a" in ids and "top.mid" in ids


def test_subgraph_excludes_clock_by_default(tmp_path):
    d = _data(tmp_path, "top.y", "--depth", "1", "--direction", "in")
    assert "top.clk" not in {n["id"] for n in d["result"]["nodes"]}


def test_subgraph_clock_edge_opt_in(tmp_path):
    d = _data(tmp_path, "top.y", "--depth", "1", "--direction", "in",
              "--edge-kinds", "clock")
    ids = {n["id"] for n in d["result"]["nodes"]}
    assert "top.clk" in ids


def test_subgraph_invalid_seed_is_error(tmp_path):
    r = _run(tmp_path, "top.nope", "--depth", "1")
    assert r.returncode != 0
    d = json.loads(r.stdout)
    assert d["ok"] is False


def test_subgraph_deterministic(tmp_path):
    a = _data(tmp_path, "top.y", "--depth", "2", "--direction", "both")
    b = _data(tmp_path, "top.y", "--depth", "2", "--direction", "both")
    assert a["result"] == b["result"]


def test_subgraph_evidence(tmp_path):
    d = _data(tmp_path, "top.y", "--depth", "0", "--evidence")
    node = d["result"]["nodes"][0]
    assert node["file"].endswith("t.sv") and node["line"] > 0
