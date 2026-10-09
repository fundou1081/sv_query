"""
test_cross_module_traversal.py — [iter_240] loads/drivers 的跨模块传递闭包

背景: `SignalTracer` 把 MIG 端口映射 (例化端口 ↔ 模块定义侧信号) 当成"图上零结果时
补一条"的**兜底**, 带来三个缺陷:

  D1 **不传递**: 只能跨出一跳 (`loads sub_adder.sum` 到不了 `inst_demo.add_out`)
  D2 **被抑制**: 图上有任何结果时兜底不触发 → 跨模块路径被"部分结果"掩盖
  D3 **depth 不一致**: `depth=1` 走 `_find_loads`(不查 MIG) → 同一查询不同 depth 答案不同

修复: 端口映射成为**遍历的一步** (`_mig_neighbors` 注入到两个递归入口 + 两个 depth=1 入口),
每跳记 1 层深度; `use_mig=False` 时行为不变。

契约: 结果是修复前的**超集** (不丢任何旧结果) + 跨模块链条完整。
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

INST_DEMO = PROJECT_ROOT / "sim/tests/fixtures/golden_mini/inst_demo.sv"


@pytest.fixture(scope="module")
def tracer():
    t = UnifiedTracer(sources={"inst_demo.sv": INST_DEMO.read_text()})
    t.build_graph()
    return t


def _ids(nodes) -> set[str]:
    return {n.id for n in (nodes or [])}


class TestLoadsTransitivity:
    def test_internal_signal_reaches_outer_consumer(self, tracer):
        """D1: 从模块内部信号出发, 必须能跨出端口到达外层消费者。"""
        ids = _ids(tracer.trace_fanout("sub_adder.sum"))
        assert "inst_demo.u_adder.sum" in ids, "应跨出到例化端口"
        assert "inst_demo.add_out" in ids, "应继续到外层消费者 (旧实现到此为止)"

    def test_top_input_full_chain(self, tracer):
        """D2: 从顶层输入出发, 整条 输入→端口→内部→端口→输出 链都要在结果里。"""
        ids = _ids(tracer.trace_fanout("inst_demo.in_a"))
        for expected in ("inst_demo.u_adder.a", "sub_adder.a", "sub_adder.sum",
                         "inst_demo.u_adder.sum", "inst_demo.add_out"):
            assert expected in ids, f"链条缺 {expected}: {sorted(ids)}"

    def test_instance_port_reaches_both_sides(self, tracer):
        ids = _ids(tracer.trace_fanout("inst_demo.u_adder.sum"))
        assert "sub_adder.sum" in ids      # 进入模块
        assert "inst_demo.add_out" in ids  # 外层消费者


class TestDriversTransitivity:
    def test_internal_signal_traces_back_to_top_inputs(self, tracer):
        ids = _ids(tracer.trace_fanin("sub_adder.sum"))
        assert "inst_demo.u_adder.a" in ids, "应跨出到例化端口"
        assert "inst_demo.in_a" in ids, "应继续回溯到顶层输入"

    def test_output_signal_traces_into_module(self, tracer):
        ids = _ids(tracer.trace_fanin("inst_demo.add_out"))
        assert "inst_demo.u_adder.sum" in ids


class TestDepthConsistency:
    def test_depth_one_is_subset_and_nonempty(self, tracer):
        """D3: depth=1 与更深 depth 必须自洽 (旧实现 depth=1 返回空)。"""
        d1 = _ids(tracer.trace_fanout("sub_adder.sum", depth=1))
        d2 = _ids(tracer.trace_fanout("sub_adder.sum", depth=2))
        dall = _ids(tracer.trace_fanout("sub_adder.sum"))
        assert d1, "depth=1 不应为空 (旧实现 bug: 空)"
        assert d1 <= d2 <= dall, f"depth 单调性被破坏: {d1=} {d2=} {dall=}"

    def test_drivers_depth_one_nonempty(self, tracer):
        d1 = _ids(tracer.trace_fanin("sub_adder.sum", depth=1))
        assert d1, "drivers depth=1 不应为空"


class TestSupersetAndFlags:
    def test_results_are_superset_of_graph_only(self, tracer):
        """修复前的旧结果 (纯图遍历) 必须仍全部在结果里 (不丢信息)。"""
        # sub_adder.sum 在纯图上是 0 条 (旧实现的 MIG 兜底给了 inst_demo.u_adder.sum)
        assert "inst_demo.u_adder.sum" in _ids(tracer.trace_fanout("sub_adder.sum"))
        # inst_demo.u_adder.sum 在纯图上是 inst_demo.add_out
        assert "inst_demo.add_out" in _ids(tracer.trace_fanout("inst_demo.u_adder.sum"))

    def test_use_mig_false_keeps_graph_only(self, tracer):
        """use_mig=False → 不跨模块 (旧行为, 开关必须仍然有效)。"""
        from trace.core.query.signal import SignalTracer

        st = SignalTracer(tracer.get_graph(), mig=None, use_mig=False)
        assert _ids(st.trace_fanout("sub_adder.sum")) == set()
        assert "inst_demo.add_out" in _ids(st.trace_fanout("inst_demo.u_adder.sum"))


class TestTermination:
    def test_port_internal_pingpong_terminates(self, tracer):
        """端口↔内部是双向映射, 遍历必须靠 visited 收敛 (不重复、不无限循环)。"""
        loads = tracer.trace_fanout("sub_adder.sum")
        ids = [n.id for n in loads]
        assert len(ids) == len(set(ids)), f"结果出现重复: {ids}"

    def test_drivers_terminates(self, tracer):
        drivers = tracer.trace_fanin("sub_adder.sum")
        ids = [n.id for n in drivers]
        assert len(ids) == len(set(ids))
