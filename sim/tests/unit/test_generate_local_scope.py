"""test_generate_local_scope.py — [iter_273] generate 局部信号的作用域 (已知缺陷)

现状 (见 docs/KNOWN_LIMITATIONS.md §3.5):
  generate 循环里每轮的 `logic local_wire;` 会塌缩成单个 `top.local_wire`,
  并产生跨轮假边 (din[0..3] 全部驱动它, 它又驱动全部 4 个实例端口)。

本文件断言**期望行为** (块限定命名 `top.G[i].local_wire`), 当前标记 xfail:
  - 修好 (方案 A: 限定作用域) 后 xfail 自动转 xpass → 届时删掉 marker
  - 不修则一直记录这个缺口, 避免"看起来绿"
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


@pytest.mark.xfail(
    reason="generate 局部信号尚未按块限定命名 (KNOWN_LIMITATIONS §3.5, 方案 A 待做)",
    strict=False,
)
def test_generate_local_wire_is_scope_qualified(graph):
    nodes = set(map(str, graph.nodes()))
    assert "top.G[0].local_wire" in nodes
    assert "top.G[1].local_wire" in nodes
    assert "top.local_wire" not in nodes, "不应塌缩到模块作用域"


@pytest.mark.xfail(
    reason="同上: 塌缩导致跨轮假边 (din[0..3] 全部驱动同一个 local_wire)",
    strict=False,
)
def test_no_cross_iteration_fanout(graph):
    """G[1].u_leaf.a 的驱动应只有本轮局部信号 (当前塌缩成共享的 top.local_wire)。"""
    drivers = {str(n) for n in graph.predecessors("top.G[1].u_leaf.a")}
    assert drivers == {"top.G[1].local_wire"}, drivers
