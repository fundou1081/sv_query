"""
[iter_082] C 组: generate-for 链 1:1 truth — golden_dataflow_29_generate_for_chain

1:1 truth 金标准 (truth 层): 对固定 fixture, 图结构 (节点/边) 必须精确匹配
预期 — 任何提取逻辑变化 (pyslang API / generate 展开 / 位选) 导致偏离时此测试失败。

Fixture: golden_dataflow_29_generate_for_chain.sv (3 级 generate-for 链, N=4)
- stage1: for i in 0..2 → buf1[i+1] = buf1[i] + prod   (3 iterations)
- stage2: for i in 0..2 → buf2[i]   = buf1[i+1] + prod (3, 依赖 stage1)
- stage3: for i in 0..2 → buf3[i]   = buf2[i] + prod   (3, 依赖 stage2)
- 头尾: buf1[0] = data; prod = data + weights; chain_out = buf3[N-2]

1:1 预期 (实测于 iter_082):
- 节点: buf1[0..3] (4 索引) / buf2[0..2] (3) / buf3[0..2] (3) + 各 base 节点
- 边: data→buf1[0]; buf1[i+1]→buf1 (3 条); buf1→buf2[i] (3); buf2→buf3[i] (3);
      buf3→chain_out; buf1[0]→buf1 等索引→base 回边
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_29_generate_for_chain.sv"
MOD = "generate_for_chain"


def _build_graph():
    """构建 fixture 的 1:1 图 (每次独立编译, 无缓存污染)."""
    source = FIXTURE.read_text()
    tracer = UnifiedTracer(sources={"t.sv": source})
    return tracer.build_graph()


class TestGenerateForChainTruth(unittest.TestCase):
    """[1:1 truth] generate-for 链展开的精确图结构"""

    @classmethod
    def setUpClass(cls):
        cls.graph = _build_graph()

    def test_nodes_generate_expanded(self):
        """generate-for 展开的索引信号节点必须精确存在:
        buf1[0..3] (4) / buf2[0..2] (3) / buf3[0..2] (3)."""
        g = self.graph
        for i in range(4):
            self.assertIn(f"{MOD}.buf1[{i}]", g.nodes(), f"buf1[{i}] 节点应存在")
        for i in range(3):
            self.assertIn(f"{MOD}.buf2[{i}]", g.nodes(), f"buf2[{i}] 节点应存在")
            self.assertIn(f"{MOD}.buf3[{i}]", g.nodes(), f"buf3[{i}] 节点应存在")
        # base 节点
        for base in ("buf1", "buf2", "buf3", "prod", "data", "weights", "chain_out"):
            self.assertIn(f"{MOD}.{base}", g.nodes(), f"{base} 节点应存在")

    def test_edge_head_tail(self):
        """链头尾: data→buf1[0] 和 buf3→chain_out 必须存在."""
        g = self.graph
        self.assertIsNotNone(g.get_edge(f"{MOD}.data", f"{MOD}.buf1[0]"),
                             "data→buf1[0] 应存在 (链头)")
        self.assertIsNotNone(g.get_edge(f"{MOD}.buf3", f"{MOD}.chain_out"),
                             "buf3→chain_out 应存在 (链尾)")

    def test_edge_stage1_expansion(self):
        """stage1 展开: buf1[i+1]→buf1 回边 (i=1..3, 3 条) + buf1[0]→buf1."""
        g = self.graph
        for i in range(1, 4):
            self.assertIsNotNone(
                g.get_edge(f"{MOD}.buf1[{i}]", f"{MOD}.buf1"),
                f"buf1[{i}]→buf1 应存在 (stage1 展开 {i})",
            )
        self.assertIsNotNone(g.get_edge(f"{MOD}.buf1[0]", f"{MOD}.buf1"),
                             "buf1[0]→buf1 应存在")

    def test_edge_stage_chain(self):
        """级间链: buf1→buf2[i] 和 buf2→buf3[i] (每级 3 条)."""
        g = self.graph
        for i in range(3):
            self.assertIsNotNone(
                g.get_edge(f"{MOD}.buf1", f"{MOD}.buf2[{i}]"),
                f"buf1→buf2[{i}] 应存在 (stage1→2)",
            )
            self.assertIsNotNone(
                g.get_edge(f"{MOD}.buf2", f"{MOD}.buf3[{i}]"),
                f"buf2→buf3[{i}] 应存在 (stage2→3)",
            )

    def test_edge_prod_drives_stages(self):
        """prod 驱动各级: prod 在 stage1/2/3 的 RHS, 实测驱动各展开索引节点."""
        g = self.graph
        self.assertIsNotNone(g.get_edge(f"{MOD}.prod", f"{MOD}.buf1[1]"),
                             "prod→buf1[1] 应存在 (stage1 RHS)")
        self.assertIsNotNone(g.get_edge(f"{MOD}.prod", f"{MOD}.buf2[0]"),
                             "prod→buf2[0] 应存在 (stage2 RHS)")
        self.assertIsNotNone(g.get_edge(f"{MOD}.prod", f"{MOD}.buf3[0]"),
                             "prod→buf3[0] 应存在 (stage3 RHS)")
        # data 同时驱动 buf1[0] (链头) 和 prod (prod = data + weights)
        self.assertIsNotNone(g.get_edge(f"{MOD}.data", f"{MOD}.prod"),
                             "data→prod 应存在 (prod = data + weights)")

    def test_no_genvar_signal_nodes(self):
        """genvar i 不产生信号节点."""
        g = self.graph
        self.assertNotIn(f"{MOD}.i", g.nodes(), "genvar i 不应是信号节点")


if __name__ == "__main__":
    unittest.main()
