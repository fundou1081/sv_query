"""test_generate_local_scope.py — [iter_274] generate 局部信号的作用域

历史 (iter_273): generate 循环里每轮的 `logic local_wire;` 会塌缩成单个
`top.local_wire`, 并产生跨轮假边 (din[0..3] 全部驱动它, 它又驱动全部 4 个实例端口)。

iter_274 按方案 A 修复: 块内局部信号按块路径限定 (`top.G[i].local_wire`)。
本文件锁定修复后的行为 (不再是 xfail)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from trace.unified_tracer import UnifiedTracer  # noqa: E402

SRC_SV = """
module leaf(input logic a, output logic y);
    assign y = a;
endmodule

module top(input logic [3:0] din, output logic [3:0] dout);
    genvar i;
    generate
        for (i = 0; i < 4; i++) begin : G
            logic local_wire;
            assign local_wire = din[i];
            leaf u_leaf(.a(local_wire), .y(dout[i]));
        end
    endgenerate
endmodule
"""


@pytest.fixture(scope="module")
def graph():
    return UnifiedTracer(sources={"g.sv": SRC_SV}, log_level="ERROR").build_graph()


def test_generate_local_wire_is_scope_qualified(graph):
    nodes = set(map(str, graph.nodes()))
    assert "top.G[0].local_wire" in nodes
    assert "top.G[1].local_wire" in nodes
    assert "top.local_wire" not in nodes, "不应塌缩到模块作用域"


def test_no_cross_iteration_fanout(graph):
    """G[1].u_leaf.a 的驱动应只有本轮局部信号 (当前塌缩成共享的 top.local_wire)。"""
    drivers = {str(n) for n in graph.predecessors("top.G[1].u_leaf.a")}
    assert drivers == {"top.G[1].local_wire"}, drivers
