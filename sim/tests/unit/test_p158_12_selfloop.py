"""test_p158_12_selfloop.py — [P158.12 / R-026] 空 expression DRIVER 自环清除

背景:
  connection_extractor 对每个**实例 output port** 恒加一条
  `child_signal_id -> inst_port_id` 的 DRIVER 边; 两者同为
  `f"{inst_path}.{port_name}"` — 这条边**恒为自环**且 expression 为空,
  不携带任何信息 (大图上 408 条, R-026 判定为图污染)。
  原先当作"模块内部驱动实例输出"标记, 依赖它的断言已随 2026-08-13
  test_cross_module_tracking 更新移除。

本文件锁定:
  A. 实例 output port 不再产生空 expression 的 DRIVER 自环 (真 408 模式);
  B. **真实自依赖不受影响**: SignalGraph 仍接受带 expression 的自环边
     (assign a = a + 1 语义), 修复不得一刀切禁止自环;
  C. 实例输出链路端到端仍通 (输出端口仍有上游, 查询不因删边断链)。
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
from trace.core.graph.models import EdgeKind, SignalGraph, TraceEdge, TraceNode  # noqa: E402
from trace.core.graph.models import NodeKind  # noqa: E402

MINIMAL_FILELIST = str(PROJECT_ROOT / "sim/tests/fixtures/minimal_3module/filelist.f")


@pytest.fixture(scope="module")
def minimal_graph():
    tracer = UnifiedTracer(filelist=MINIMAL_FILELIST, log_level="ERROR")
    tracer.build_graph()
    return tracer.get_graph()


class TestNoEmptyExpressionSelfLoop:
    def test_no_driver_self_loop_with_empty_expression(self, minimal_graph):
        """R-026 模式归零: 任意 (src==dst) 且 expression 空的边不存在。"""
        g = minimal_graph
        bad = [
            (s, e.kind)
            for (s, d), edges in g._edge_data.items()
            for e in edges
            if s == d and not (e.expression or "").strip()
        ]
        assert bad == [], f"空 expression 自环残留: {bad}"

    def test_instance_output_ports_exist_and_are_ports(self, minimal_graph):
        """fixture 覆盖确认: 实例 output port 节点真实存在 (不是测空气)。"""
        g = minimal_graph
        inst_out_ports = [
            nid for nid in g.nodes()
            if g.get_node(nid).kind == NodeKind.PORT_OUT
            and "." in nid  # 实例级 (层级路径)
        ]
        assert len(inst_out_ports) >= 3, "fixture 无实例输出端口, 测试在测空气"


class TestRealSelfDependencyPreserved:
    def test_graph_still_accepts_self_loop_edge_with_expression(self):
        """真实自依赖 (带 expression) 不被一刀切禁止 — 修的是 extractor 侧,
        不是图模型侧。"""
        g = SignalGraph()
        g.add_trace_node(TraceNode(id="top.acc", name="acc", module="top",
                                   kind=NodeKind.SIGNAL, width=(31, 0)))
        g.add_trace_edge(TraceEdge(src="top.acc", dst="top.acc", kind=EdgeKind.DRIVER,
                                   assign_type="always_ff", expression="acc + 1"))
        edges = g._edge_data[("top.acc", "top.acc")]
        assert len(edges) == 1
        assert edges[0].expression == "acc + 1"


class TestInstanceOutputChainStillWorks:
    def test_output_port_has_real_upstream(self, minimal_graph):
        """删边不得断链: 实例输出端口仍有非自环上游边 (sub 内部驱动)。"""
        g = minimal_graph
        # top_minimal.data_o 是顶层输出, 来自 sa1 (实例) 的 sum_o
        found = False
        for (s, d), edges in g._edge_data.items():
            if d.startswith("top_minimal.sa1") and s != d:
                found = True
                break
        assert found, "实例端口上游边全部消失 — 删边过猛"
