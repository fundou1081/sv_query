"""
[iter_109] generate-for 实例化链 1:1 truth (缺陷 #45 + 连接提取修复)

1:1 truth 金标准: generate for 内实例化子模块 (经数组端口互连) 的精确图结构 —
实例路径按 entry 区分、端口连接边完整、无自环/占位。任何 generate 实例枚举或
端口连接提取逻辑变化导致偏离时此测试失败。

Fixture: golden_dataflow_38_genfor_instance_chain.sv
    generate for (i=0..3) rot U (.x(arr[i]), .xo(arr[i+1]));

1:1 预期 (实测于 iter_109, 修复前: 实例折叠成单 top.g.U + 0 连接边):
- 实例节点: top.g[0..3].U 各带 x/xo 端口 (路径带 entry 索引)
- CONNECTION: top.arr[i]→g[i].U.x ×4 + g[i].U.xo→top.arr[i+1] ×4
- 子模块 rot: rot.x→rot.xo DRIVER (内部逻辑)
- 链完整可追踪: a→arr[0]→U0→arr[1]→...→arr[4]→out
- 无 '?' 占位节点, 无自环边
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

# [iter_113] target 模式: 无 target 时 driver 走 type-level 旧路径, generate 实例
# 内部只在类型作用域 (rot.x→rot.xo) 而非实例作用域 (top.g[i].U.x→xo) — 升级后
# rot 内部逻辑按 4 个 entry 实例分别断言 (iter_111 盲区同 cordic)

FIXTURE = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_38_genfor_instance_chain.sv"


def _build_graph():
    from trace.core.compiler import SVCompiler  # noqa: E402
    from trace.core.graph_builder import GraphBuilder  # noqa: E402
    from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402
    comp = SVCompiler({str(FIXTURE): FIXTURE.read_text()})
    adapter = SemanticAdapter(comp.get_root(), target_module="top")
    return GraphBuilder(adapter, target_module="top").build()


def _edge_triples(graph):
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            out.add((s, d, e.kind.name))
    return out


class TestGenForInstanceChainTruth(unittest.TestCase):
    """[1:1 truth] generate-for 实例化链"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph()

    def test_instance_nodes_distinct(self):
        """4 个 entry 实例路径区分: top.g[0..3].U (修复前折叠成单 top.g.U)."""
        for i in range(4):
            self.assertIsNotNone(self.g.get_node(f"top.g[{i}].U"),
                                 f"top.g[{i}].U 实例节点应存在")
            self.assertIsNotNone(self.g.get_node(f"top.g[{i}].U.x"),
                                 f"top.g[{i}].U.x 端口应存在")
            self.assertIsNotNone(self.g.get_node(f"top.g[{i}].U.xo"),
                                 f"top.g[{i}].U.xo 端口应存在")

    def test_input_connections(self):
        """input CONNECTION: top.arr[i] → top.g[i].U.x (索引解析正确)."""
        m = "top"
        edges = _edge_triples(self.g)
        for i in range(4):
            self.assertIn((f"{m}.arr[{i}]", f"{m}.g[{i}].U.x", "CONNECTION"),
                          edges, f"arr[{i}]→g[{i}].U.x 应存在")

    def test_output_connections(self):
        """output CONNECTION: top.g[i].U.xo → top.arr[i+1] (i+1 索引折叠正确)."""
        m = "top"
        edges = _edge_triples(self.g)
        for i in range(4):
            self.assertIn((f"{m}.g[{i}].U.xo", f"{m}.arr[{i+1}]", "CONNECTION"),
                          edges, f"g[{i}].U.xo→arr[{i+1}] 应存在")

    def test_submodule_logic(self):
        """[iter_113] rot 内部逻辑按 4 个 entry 实例作用域提取:
        top.g[i].U.x→top.g[i].U.xo (修复前只以类型作用域 rot.x→rot.xo 出现,
        generate 实例内部 0 提取)."""
        edges = _edge_triples(self.g)
        # 类型作用域残留不应存在 (target 过滤)
        self.assertNotIn(("rot.x", "rot.xo", "DRIVER"), edges,
                         "rot 内部应落在实例作用域而非类型作用域")
        for i in range(4):
            self.assertIn((f"top.g[{i}].U.x", f"top.g[{i}].U.xo", "DRIVER"),
                          edges, f"g[{i}].U 内部 assign x→xo 应提取")

    def test_chain_complete(self):
        """链完整: 头 a→arr[0] + 尾 arr[4]→out + 中间连接齐全."""
        edges = _edge_triples(self.g)
        self.assertIn(("top.a", "top.arr[0]", "DRIVER"), edges, "链头 a→arr[0]")
        self.assertIn(("top.arr[4]", "top.out", "DRIVER"), edges, "链尾 arr[4]→out")

    def test_no_placeholder_or_bad_selfloop(self):
        """无 '?' 占位节点; CONNECTION 无自环 (输出端口 DRIVER 自环是
        connection_extractor 的'模块内部驱动'设计标记 [FIX 2026-07-08], 允许)."""
        for n in self.g.nodes():
            self.assertNotIn("?", n, f"占位节点不应存在: {n}")
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                if e.kind.name == "CONNECTION":
                    self.assertNotEqual(s, d, f"CONNECTION 自环不应存在: {s}->{d}")


if __name__ == "__main__":
    unittest.main()
