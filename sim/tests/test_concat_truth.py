"""
[iter_091] T5: concat RHS 1:1 truth (+ iter_101 缺陷 C: LHS 位置映射)

1:1 truth 金标准: RHS 拼接 `y = {a, b}` 的精确图结构 — 拼接的每个操作数都必须
驱动目标 (a→y, b→y), 且**不产生跨边** (a→y 只一条, 无 a→其他目标)。
[iter_101] 缺陷 C 修复后追加 LHS 拼接: `{y_hi, y_lo} = {a, b}` 按**位置**对齐
(a→y_hi, b→y_lo), 无笛卡尔积跨边。

Fixtures:
- golden_dataflow_4_concat.sv (with_concat): assign y = {a, b};
- golden_dataflow_36_lhs_concat.sv (lhs_concat): assign {y_hi, y_lo} = {a, b};

1:1 预期:
- with_concat: 3 节点 / 2 条 DRIVER 边 (a→y, b→y, 总边数 2)
- lhs_concat: 4 节点 / 2 条 DRIVER 边 (a→y_hi, b→y_lo, 总边数 2)

⚠️ 缺陷 C (iter_091 发现, **iter_101 已修**): LHS 拼接原实现嵌套循环 = 笛卡尔积
4 条边, 位置映射丢失 — 修复后按 zip 位置对齐, 本文件已补断言。
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"


def _build_graph(fn: str):
    path = FIXTURE_DIR / fn
    tracer = UnifiedTracer(sources={str(path): path.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


class TestWithConcatTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_4_concat: RHS 拼接"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_4_concat.sv")
        cls.m = "with_concat"

    def test_node_set_exact(self):
        """节点集精确: a, b, y (拼接本身不产生节点)."""
        expected = {f"{self.m}.a", f"{self.m}.b", f"{self.m}.y"}
        self.assertEqual(set(self.g.nodes()), expected, "with_concat 节点集偏离")

    def test_edge_set_exact(self):
        """边集精确: a→y + b→y 两条 DRIVER (拼接操作数都驱动目标)."""
        m = self.m
        expected = {(f"{m}.a", f"{m}.y", "DRIVER"), (f"{m}.b", f"{m}.y", "DRIVER")}
        actual = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                actual.add((s, d, e.kind.name))
        self.assertEqual(actual, expected, "with_concat 边集偏离")

    def test_no_cross_edges(self):
        """总边数 = 2 — 无跨目标/跨 kind 多余边."""
        n = sum(1 for _ in self.g.edges())
        self.assertEqual(n, 2, f"拼接应产生恰好 2 条边, got {n}")


class TestLhsConcatTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_36_lhs_concat: LHS 拼接位置映射 (缺陷 C)"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_36_lhs_concat.sv")
        cls.m = "lhs_concat"

    def test_node_set_exact(self):
        """节点集精确: a, b, y_hi, y_lo."""
        expected = {f"{self.m}.a", f"{self.m}.b", f"{self.m}.y_hi", f"{self.m}.y_lo"}
        self.assertEqual(set(self.g.nodes()), expected, "lhs_concat 节点集偏离")

    def test_positional_mapping(self):
        """位置映射精确: {y_hi,y_lo} = {a,b} → a→y_hi, b→y_lo (非笛卡尔积)."""
        m = self.m
        expected = {(f"{m}.a", f"{m}.y_hi", "DRIVER"), (f"{m}.b", f"{m}.y_lo", "DRIVER")}
        actual = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                actual.add((s, d, e.kind.name))
        self.assertEqual(actual, expected, "LHS 拼接位置映射偏离 (缺陷 C)")

    def test_no_cross_product(self):
        """无笛卡尔积: a→y_lo / b→y_hi 不应存在, 总边数 = 2."""
        m = self.m
        actual = set(self.g.edges())
        self.assertNotIn((f"{m}.a", f"{m}.y_lo"), actual, "a→y_lo 不应存在 (跨边)")
        self.assertNotIn((f"{m}.b", f"{m}.y_hi"), actual, "b→y_hi 不应存在 (跨边)")
        self.assertEqual(len(actual), 2, f"LHS 拼接应恰好 2 条边, got {len(actual)}")


if __name__ == "__main__":
    unittest.main()
