"""test_path_directed_parity.py — [iter_268] 有向路径语义的一致性守卫

背景（POC iter_267 实测）:
  - `PathResolver` 是**无向**的 (successors + predecessors + MIG 虚拟跳),
    所以 `sync0 → async_i` 这类逆流查询也会"找到路径"
  - `DataFlowGraph` 是**有向**的, 但 `_resolve_cross_module` 会把实例端口改写成
    模块定义命名空间的影子节点 (孤立节点) → 一切跨模块查询报 unreachable

iter_268 的修法:
  ① `_resolve_cross_module`: 图里已存在的 id 原样返回 (不再改写)
  ② `PathResolver` 增加 `directed` 模式: 只走 successors, 与 dataflow 同一张图
  ③ `paths --directed` 暴露该模式

本文件锁定三条不变式:
  A. 有向下 `paths --directed` 与 `dataflow analyze` 对同一对信号**结论一致**
  B. 有向模式下逆流查询必须不可达; 无向模式必须可达 (语义差异显式)
  C. 返回路径必须以用户请求的 dst 结尾 (端点不漂移 — iter_268 修的 bug)
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

FILELIST = PROJECT_ROOT / "sim/tests/fixtures/minimal_3module/filelist.f"

# 正向 (数据流方向) / 逆流 / 分支, 覆盖跨模块与同步器两类结构
PAIRS = [
    ("top_minimal.valid_i", "top_minimal.sa1.valid_i"),        # 顶层端口 → 实例端口
    ("top_minimal.valid_i", "top_minimal.sa1.lp1.data_i"),     # 顶层端口 → 孙实例内部
    ("top_minimal.sa1.la1.sum", "top_minimal.data_o"),         # 叶内部 → 顶层输出
    ("synchronizer.async_i", "synchronizer.sync1"),            # 同步器链
    ("top_minimal.data_o", "top_minimal.valid_i"),             # 逆流
    ("synchronizer.sync0", "synchronizer.async_i"),            # 逆流
]


@pytest.fixture(scope="module")
def tracer():
    t = UnifiedTracer(filelist=str(FILELIST), log_level="ERROR")
    t.build_graph()
    return t


@pytest.fixture(scope="module")
def resolver(tracer):
    return tracer.get_path_resolver()


def _dataflow_reachable(tracer, src: str, dst: str) -> bool:
    from trace.core.graph.dataflow import DataFlowGraph

    dfg = DataFlowGraph(tracer.get_graph(), tracer.get_module_graph())
    return bool(dfg.analyze(src, dst, max_paths=20).is_reachable)


class TestDirectedParity:
    @pytest.mark.parametrize("src,dst", PAIRS)
    def test_directed_agrees_with_dataflow(self, tracer, resolver, src, dst):
        """不变式 A: 有向 paths 与 dataflow 的 is_reachable 必须一致。"""
        got = resolver.find_path(src, dst, directed=True) is not None
        want = _dataflow_reachable(tracer, src, dst)
        assert got == want, f"{src} → {dst}: paths(directed)={got}, dataflow={want}"

    @pytest.mark.parametrize("src,dst", [
        ("top_minimal.data_o", "top_minimal.valid_i"),
        ("synchronizer.sync0", "synchronizer.async_i"),
    ])
    def test_reverse_is_unreachable_directed_but_reachable_undirected(self, resolver, src, dst):
        """不变式 B: 逆流查询 —— 有向不可达、无向可达 (两种语义都要显式)。"""
        assert resolver.find_path(src, dst, directed=True) is None, \
            f"{src} → {dst} 是逆流, 有向模式必须不可达"
        assert resolver.find_path(src, dst, directed=False) is not None, \
            f"{src} → {dst} 无向模式应可达 (结构连通)"


class TestEndpointFidelity:
    @pytest.mark.parametrize("src,dst", PAIRS)
    def test_path_ends_at_requested_dst(self, resolver, src, dst):
        """不变式 C: 路径最后一项 == 用户请求的 dst (iter_268 修掉的端点漂移)。"""
        for directed in (False, True):
            path = resolver.find_path(src, dst, directed=directed)
            if path is None:
                continue
            assert path[0] == src, f"路径起点不是 src: {path[0]}"
            assert path[-1] == dst, (
                f"路径终点漂移: 请求 {dst}, 实际 {path[-1]} (directed={directed})"
            )

    @pytest.mark.parametrize("src,dst", PAIRS)
    def test_all_paths_end_at_requested_dst(self, resolver, src, dst):
        """find_all_paths 同样不允许端点漂移。"""
        for path in resolver.find_all_paths(src, dst, max_paths=10):
            assert path[-1] == dst, f"all_paths 端点漂移: {path}"
