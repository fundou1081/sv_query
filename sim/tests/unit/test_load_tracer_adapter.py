"""
test_load_tracer_adapter.py — [iter_241] LoadTracer 是 SignalTracer 的薄适配层

背景: `LoadTracer` 此前自带一份**平行**的图遍历 (`GraphTraversal` 子类) + 自己的
id 拼接规则, 与 `SignalTracer` (`svq loads` 实际走的路) 长期分叉, 三个缺陷:

  L1 `f"{module}.{signal}"` 在 `module=None` 时得到 `"None.sig"`
     → 结果恒空, 且 `LoadChain.root` 是**永不存在的 id**
  L2 没有 MIG → 跨模块 loads 永远丢失
  L3 不支持 `depth`; `confidence` 词表与 `SignalChain` 不一致

修复方式: 删掉 `GraphTraversal` 与 `LoadTracer` 自己的遍历, 只保留
**入参解析 + 结果打包**, 遍历唯一真相源 = `SignalTracer.trace_fanout`。

本文件锁定的契约:
  1. 全局 (module=None) 的完整 id 能解析, root 不是伪造的
  2. 跨模块结果在 (L2)
  3. depth 生效 (L3)
  4. 与 `trace_fanout` **逐节点一致** — 这条是防"再分叉"的核心
  5. `LoadTracer` 不得再长出私有遍历方法 (结构性回归锁)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from trace.core.query.load import LoadTracer  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

INST_DEMO = PROJECT_ROOT / "sim/tests/fixtures/golden_mini/inst_demo.sv"
SINGLE_MODULE = """
module top(input clk, input d, output logic q);
    logic tmp;
    always_ff @(posedge clk) begin
        tmp <= d;
        q <= tmp;
    end
endmodule"""


@pytest.fixture(scope="module")
def multi(tracer_factory):
    return tracer_factory({"inst_demo.sv": INST_DEMO.read_text()})


@pytest.fixture(scope="module")
def single(tracer_factory):
    return tracer_factory({"test.sv": SINGLE_MODULE})


@pytest.fixture(scope="module")
def tracer_factory():
    cache = {}

    def _make(sources):
        key = tuple(sorted(sources))
        if key not in cache:
            t = UnifiedTracer(sources=sources)
            t.build_graph()
            cache[key] = t
        return cache[key]

    return _make


def _ids(nodes) -> list[str]:
    return [n.id for n in (nodes or [])]


class TestL1RootResolution:
    """L1: module=None 时不得伪造 `"None.sig"`, 且要能解析完整 id。"""

    def test_qualified_id_without_module_is_not_empty(self, multi):
        chain = multi.trace_loads("inst_demo.in_a")
        assert chain.root == "inst_demo.in_a"
        assert chain.loads, "完整 id + module=None 必须能查出 loads (旧实现恒空)"

    def test_root_never_contains_none_prefix(self, multi):
        for sig in ("inst_demo.in_a", "inst_demo.u_adder.sum", "sub_adder.a"):
            root = multi.trace_loads(sig).root
            assert not root.startswith("None."), f"root 被伪造成 {root!r}"
            assert root == sig

    def test_short_name_without_module_is_unknown_not_fabricated(self, single):
        # 短名 + module=None 不该被当成 "None.d"; 它是查不到的, 必须如实报 unknown
        chain = single.trace_loads("d")
        assert chain.root == "d"
        assert chain.confidence == "unknown"
        assert chain.loads == []

    def test_unknown_signal_returns_unknown_confidence(self, single):
        chain = single.trace_loads("top.nosuch")
        assert chain.confidence == "unknown"
        assert chain.loads == []


class TestL2CrossModule:
    """L2: 跨模块端口映射必须进入遍历 (不再是兜底补丁)。"""

    def test_internal_signal_crosses_out(self, multi):
        # [iter_271] 实例级图: 跨模块由**图边**完成 (不再依赖 MIG 虚拟跳),
        # 所以 MIG 的"进入模块"中间节点不存在了。
        ids = _ids(multi.trace_loads("inst_demo.u_adder.sum").loads)
        assert "inst_demo.add_out" in ids, "应跨到外层消费者"

    def test_top_input_full_chain(self, multi):
        ids = _ids(multi.trace_loads("inst_demo.in_a").loads)
        for expected in ("inst_demo.u_adder.a", "inst_demo.u_adder.sum",
                         "inst_demo.add_out"):
            assert expected in ids, f"链条缺 {expected}: {sorted(ids)}"

    def test_scoped_query_does_not_cross_module(self, multi):
        """限定查询 (给了 module) 只看该模块内 —— 与 CLI 作用域规则一致。"""
        # 实例作用域下的"限定查询": module 参数是实例路径
        ids = _ids(multi.trace_loads("a", "inst_demo.u_adder").loads)
        assert all(i.startswith("inst_demo.u_adder.") for i in ids), f"越界: {ids}"

class TestL3DepthAndConfidence:
    """L3: depth 生效, confidence 词表保持向后兼容。"""

    def test_depth_1_is_direct_only(self, multi):
        ids = _ids(multi.trace_loads("inst_demo.in_a", depth=1).loads)
        assert ids == ["inst_demo.u_adder.a"], f"depth=1 应只有直接后继: {ids}"

    def test_depth_2_reaches_two_hops(self, multi):
        ids = _ids(multi.trace_loads("inst_demo.in_a", depth=2).loads)
        assert "inst_demo.u_adder.a" in ids
        assert "inst_demo.u_adder.sum" in ids
        assert "inst_demo.add_out" not in ids, "depth=2 不应追到最外层"

    def test_depth_none_is_full_closure(self, multi):
        short = _ids(multi.trace_loads("inst_demo.in_a", depth=2).loads)
        full = _ids(multi.trace_loads("inst_demo.in_a").loads)
        assert len(full) > len(short)

    def test_confidence_vocabulary_preserved(self, single):
        assert single.trace_loads("top.d").confidence == "medium"  # d → tmp → q
        assert single.trace_loads("top.q").confidence == "no_load"

    def test_get_loads_takes_full_id(self, single):
        lt = LoadTracer(single.get_graph())
        assert lt.get_loads("top.d") == ["top.tmp", "top.q"]

    def test_get_loads_is_deduped_and_ordered(self, single):
        lt = LoadTracer(single.get_graph())
        ids = lt.get_loads("top.d")
        assert len(ids) == len(set(ids))
        assert ids[0] == "top.tmp", "直接后继应排在前面"


class TestNoSecondImplementation:
    """结构性回归锁: 遍历只允许有一份。

    旧 bug 的成因不是某一行写错, 而是**存在第二份遍历**。所以这里直接锁住
    "LoadTracer 不再拥有自己的遍历方法", 让重新引入平行实现时立刻失败。
    """

    def test_loadtracer_has_no_private_traversal(self):
        for attr in ("_collect_all_loads", "_find_loads", "_find_by_edge_kind",
                     "_collect_all_by_edge_kind"):
            assert not hasattr(LoadTracer, attr), (
                f"LoadTracer.{attr} 又出现了 —— 遍历只允许在 SignalTracer 里有一份"
            )

    def test_graph_traversal_module_is_gone(self):
        import importlib.util
        assert importlib.util.find_spec("trace.core.graph_traversal") is None, (
            "死基类 graph_traversal.py 不应复活"
        )

    def test_loadtracer_delegates_to_signal_tracer(self, single):
        from trace.core.query.signal import SignalTracer
        assert isinstance(single._load_tracer._signal_tracer, SignalTracer)


@pytest.mark.parametrize("signal,module", [
    ("inst_demo.in_a", None),
    ("inst_demo.u_adder.sum", None),
    ("sub_adder.a", None),
    ("inst_demo.u_adder.sum", None),
    ("sum", "sub_adder"),
    ("in_a", "inst_demo"),
])
def test_parity_with_trace_fanout(multi, signal, module):
    """核心契约: `trace_loads` 与 `trace_fanout` 对同一查询给出**同一批节点**。

    这两个入口分别服务 Python API 与 CLI; 它们曾经分叉就是因为各有一份实现。
    """
    from_api = sorted(_ids(multi.trace_loads(signal, module).loads))
    from_cli = sorted(_ids(multi.trace_fanout(signal, module)))
    assert from_api == from_cli, f"{signal}/{module}: API 与 CLI 结果不一致"
