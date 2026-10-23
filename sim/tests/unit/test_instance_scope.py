"""test_instance_scope.py — [iter_269] 实例级图开关 (迁移用)

背景:
  默认图沿用"模块定义命名空间"(节点 id = `模块名.信号`, 如 `sub_adder.sum`),
  另有一套实例作用域 id (`inst_demo.u_adder.sum`)。两套命名空间并存导致:
    - 影子节点占图 30~38%, 从顶层输入有向可达 **0** (POC iter_267)
    - `paths` 需要 MIG 虚拟跳才能"跨模块", 且端点会被改写 (iter_268 修)

  `instance_scope=True` (或环境变量 `SVQ_INSTANCE_SCOPE=1`) 让 DriverExtractor
  按**实例路径**出边, 并清掉其它 extractor 留下的零度模块定义节点 → 单一命名空间。

本文件锁定:
  A. instance_scope 下没有"模块定义命名空间"节点 (只允许顶层实例名 + 常量 0)
  B. 默认模式保持不变 (仍含模块定义节点) —— 开关不改变老行为
  C. instance_scope 下有向路径与 dataflow 结论一致
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


def _tops(tracer) -> set[str]:
    root = tracer._get_compiler().get_root()
    return {str(t.name) for t in root.topInstances}


def _namespace_prefixes(graph) -> set[str]:
    return {n.split(".")[0] for n in graph.nodes()}


class TestInstanceScope:
    @pytest.fixture(scope="class")
    def scoped(self):
        t = UnifiedTracer(filelist=str(FILELIST), log_level="ERROR")
        t.build_graph(instance_scope=True)
        return t

    @pytest.fixture(scope="class")
    def default(self):
        t = UnifiedTracer(filelist=str(FILELIST), log_level="ERROR")
        t.build_graph()
        return t

    def test_no_type_namespace_nodes(self, scoped):
        """A: 只允许顶层实例名 + 常量 "0" 作为前缀。"""
        allowed = _tops(scoped) | {"0"}
        prefixes = _namespace_prefixes(scoped.get_graph())
        extra = prefixes - allowed
        assert not extra, f"instance_scope 下仍有模块定义命名空间: {sorted(extra)}"

    def test_all_nodes_under_instance(self, scoped):
        """A: 每个非 "0" 节点都必须落在某个顶层实例路径下。"""
        tops = _tops(scoped)
        for node in scoped.get_graph().nodes():
            if node == "0":
                continue
            assert any(node == t or node.startswith(t + ".") for t in tops), \
                f"节点不在任何实例命名空间下: {node}"

    def test_default_still_has_type_nodes(self, default):
        """B: 默认模式保持不变 —— 模块定义命名空间仍在 (暂不切换默认)。"""
        tops = _tops(default)
        extra = _namespace_prefixes(default.get_graph()) - (tops | {"0"})
        assert extra, "默认模式应仍包含模块定义命名空间节点 (开关未影响老行为)"

    def test_directed_path_agrees_with_dataflow(self, scoped):
        """C: instance_scope 下 paths(directed) 与 dataflow 结论一致。"""
        from trace.core.graph.dataflow import DataFlowGraph

        pairs = [
            ("top_minimal.valid_i", "top_minimal.sa1.valid_i"),
            ("top_minimal.valid_i", "top_minimal.sa1.lp1.data_i"),
            ("top_minimal.sa1.la1.sum", "top_minimal.data_o"),
            ("top_minimal.data_o", "top_minimal.valid_i"),
        ]
        resolver = scoped.get_path_resolver()
        dfg = DataFlowGraph(scoped.get_graph(), scoped.get_module_graph())
        for src, dst in pairs:
            got = resolver.find_path(src, dst, directed=True) is not None
            want = bool(dfg.analyze(src, dst, max_paths=20).is_reachable)
            assert got == want, f"{src} → {dst}: paths={got}, dataflow={want}"

    def test_type_id_is_unknown(self, scoped):
        """按决策: 实例级图只认实例路径, 模块定义 id 必须查不到 (不静默兜底)。"""
        graph = scoped.get_graph()
        assert "sub_aggregator.valid_i" not in graph.nodes()
        assert "leaf_adder.a" not in graph.nodes()
