"""
[iter_091] T5: concat RHS 1:1 truth

1:1 truth 金标准: RHS 拼接 `y = {a, b}` 的精确图结构 — 拼接的每个操作数都必须
驱动目标 (a→y, b→y), 且**不产生跨边** (a→y 只一条, 无 a→其他目标)。

Fixture: golden_dataflow_4_concat.sv (with_concat)
    assign y = {a, b};

1:1 预期 (实测于 iter_091):
- 3 节点: a, b (PORT_IN), y (PORT_OUT)
- 2 条 DRIVER 边: a→y, b→y (总边数 2)

⚠️ 已知缺陷 (iter_091 发现, 不纳入 golden): **LHS 拼接位置映射丢失** —
`assign {y_hi, y_lo} = {a, b}` 实测产生笛卡尔积 4 条边 (a→y_hi, a→y_lo,
b→y_hi, b→y_lo), 位置对应关系 (a→y_hi, b→y_lo) 未保留。EXTRACTION_COVERAGE
标 #11 LHS concat "完整支持" 与实际不符, 待方豆定夺修复。
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


if __name__ == "__main__":
    unittest.main()
