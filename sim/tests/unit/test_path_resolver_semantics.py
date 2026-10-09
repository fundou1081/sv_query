"""
test_path_resolver_semantics.py — [iter_237] PathResolver 语义回归 (跨模块修复的守卫)

`PathResolver` 此前**零 CLI 调用方**且是坏的 (iter_237 修):
  ① 只做"进模块"映射不做"出模块" → 跨模块路径恒 None
  ② `find_path` 与 `find_all_paths` 遍历不一致 → 结论互相矛盾

本文件锁定修复后的**不变式与边界**, 用最坏情况 (环/截断/深度) 防回归:
  - 不变式: find_path 结果 ⊆ find_all_paths 结果
  - find_path 是最短跳数解 (不超过 all_paths 里最短的那条)
  - 有环图不炸 (简单路径 + 上限)
  - max_paths / max_depth 真生效
  - 未在图中出现的节点不抛异常 (返回空/None)
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

LOOP_SV = """module loop_top (input logic a, output logic y);
  logic b, c;
  assign b = a | c;
  assign c = b & a;
  assign y = b;
endmodule
"""


@pytest.fixture(scope="module")
def inst_tracer():
    t = UnifiedTracer(sources={"inst_demo.sv": INST_DEMO.read_text()})
    t.build_graph()
    return t


@pytest.fixture(scope="module")
def loop_tracer():
    t = UnifiedTracer(sources={"loop.sv": LOOP_SV})
    t.build_graph()
    return t


class TestPathResolverInvariants:
    def test_find_path_subset_of_find_all_paths(self, inst_tracer):
        pr = inst_tracer.get_path_resolver()
        for src, dst in [("inst_demo.in_a", "inst_demo.add_out"),
                         ("inst_demo.in_c", "inst_demo.mult_out"),
                         ("sub_adder.a", "sub_adder.sum")]:
            one = pr.find_path(src, dst)
            assert one is not None, f"{src}->{dst} 应有路径 (跨模块修复后)"
            assert one in pr.find_all_paths(src, dst)

    def test_find_path_is_shortest_hop(self, inst_tracer):
        """find_path 返回最短跳数解 (契约已在 docstring 明确)。"""
        pr = inst_tracer.get_path_resolver()
        src, dst = "inst_demo.in_a", "inst_demo.add_out"
        one = pr.find_path(src, dst)
        shortest = min(len(p) for p in pr.find_all_paths(src, dst))
        assert len(one) == shortest, f"find_path 不是最短: {len(one)} vs {shortest}"

    def test_cross_module_route_exists(self, inst_tracer):
        """跨模块路线的存在性: 必须有路径穿越模块内部 (端口↔内部信号映射的证明)。"""
        pr = inst_tracer.get_path_resolver()
        allp = pr.find_all_paths("inst_demo.in_a", "inst_demo.add_out")
        interior = [p for p in allp if any(n.startswith("sub_adder.") for n in p)]
        assert interior, "应存在穿越 sub_adder 内部的跨模块路径"
        # 且该路线确实经过内部信号 (不是只走实例节点)
        assert any("sub_adder.sum" in p for p in interior)


class TestPathResolverBounds:
    def test_max_paths_caps_results(self, inst_tracer):
        pr = inst_tracer.get_path_resolver()
        full = pr.find_all_paths("inst_demo.in_a", "inst_demo.add_out")
        assert len(full) >= 2, "该用例需要 >1 条路径"
        capped = pr.find_all_paths("inst_demo.in_a", "inst_demo.add_out", max_paths=1)
        assert len(capped) == 1

    def test_max_depth_bounds_search(self, inst_tracer):
        """max_depth 太小 → 找不到长路径 (不返回违规的超长路径)。"""
        pr = inst_tracer.get_path_resolver()
        assert pr.find_all_paths("inst_demo.in_a", "inst_demo.add_out", max_depth=2) == []
        assert pr.find_all_paths("inst_demo.in_a", "inst_demo.add_out", max_depth=60)

    def test_identical_src_dst(self, inst_tracer):
        pr = inst_tracer.get_path_resolver()
        assert pr.find_path("inst_demo.in_a", "inst_demo.in_a") == ["inst_demo.in_a"]

    def test_unknown_node_does_not_raise(self, inst_tracer):
        """未在图中出现的节点: 返回 None/[] (不抛异常, 也不静默编造路径)。"""
        pr = inst_tracer.get_path_resolver()
        assert pr.find_path("no_such.sig", "inst_demo.add_out") is None
        assert pr.find_all_paths("no_such.sig", "inst_demo.add_out") == []


class TestPathResolverCycleSafety:
    def test_cycle_graph_terminates(self, loop_tracer):
        """有环图 (b ↔ c) 上枚举简单路径必须终止, 且不重复节点。"""
        pr = loop_tracer.get_path_resolver()
        paths = pr.find_all_paths("loop_top.a", "loop_top.y", max_paths=50)
        assert paths, "环图上也应有 (简单) 路径"
        assert len(paths) < 50, "不应触到上限就说明搜索被环卡住"
        for p in paths:
            assert len(p) == len(set(p)), f"路径出现重复节点 (环未剪): {p}"

    def test_cycle_reachable_paths(self, loop_tracer):
        """环内两节点互相可达 (b→c 且 c→b), 都能给出路径。"""
        pr = loop_tracer.get_path_resolver()
        assert pr.find_path("loop_top.b", "loop_top.c") is not None
        assert pr.find_path("loop_top.c", "loop_top.b") is not None
