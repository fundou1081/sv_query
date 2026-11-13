"""[iter_307 / PLAN P13.6] drivers JSON 的多驱动/条件分支标记。

- driver_count: 直接 DRIVER 边不同源数（含条件分支）
- multi_driver: >=2 个**无条件**直接源（潜在冲突；条件 mux 不算）
- conditional_drivers: 存在带条件的直接驱动（ternary/case/if）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from cli.core.semantic.trace_common import driver_stats
from sv_query.trace.core.graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run(sig: str, src: str, tmp_path: Path) -> dict:
    p = tmp_path / "t.sv"
    p.write_text(src)
    r = subprocess.run(
        ["sv_query", "trace", "fanin", sig, "--file", str(p), "--json", "--no-cache"],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)["result"]["signals"][0]


MULTI = """
module top(input [7:0] a, b, output [7:0] y);
  assign y = a;
  assign y = b;
endmodule
"""

MUX = """
module top(input sel, input [7:0] a, b, output [7:0] m);
  assign m = sel ? a : b;
endmodule
"""

SINGLE = """
module top(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
"""


class TestDriverStats:
    def test_multi_driver_unconditional(self, tmp_path):
        s = _run("top.y", MULTI, tmp_path)
        assert s["driver_count"] == 2
        assert s["multi_driver"] is True
        assert s["conditional_drivers"] is False
        assert {d["id"] for d in s["drivers"]} == {"top.a", "top.b"}

    def test_conditional_mux_not_multi_driver(self, tmp_path):
        s = _run("top.m", MUX, tmp_path)
        assert s["driver_count"] == 2
        assert s["multi_driver"] is False
        assert s["conditional_drivers"] is True

    def test_single_driver(self, tmp_path):
        s = _run("top.y", SINGLE, tmp_path)
        assert s["driver_count"] == 1
        assert s["multi_driver"] is False
        assert s["conditional_drivers"] is False

    def test_bit_query_uses_parent_stats(self, tmp_path):
        src = """
module top(input [7:0] a, b, output [7:0] y, output z);
  assign y = a;
  assign y = b;
  assign z = y[3];
endmodule"""
        s = _run("top.y[3]", src, tmp_path)
        assert s["driver_count"] == 2
        assert s["multi_driver"] is True


def test_self_port_edge_not_counted_as_driver():
    g = SignalGraph()
    for nid in ("top.y", "top.a"):
        g.add_trace_node(TraceNode(id=nid, name=nid.split(".")[-1], module="top",
                                   kind=NodeKind.SIGNAL, width=(7, 0)))
    g.add_trace_edge(TraceEdge(src="top.a", dst="top.y", kind=EdgeKind.DRIVER))
    g.add_trace_edge(TraceEdge(src="top.y", dst="top.y", kind=EdgeKind.DRIVER))
    assert driver_stats(g, "top.y")[:2] == (1, False)
