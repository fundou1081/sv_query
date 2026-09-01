"""
[iter_093] T7: parameter/localparam 过滤 1:1 truth (反例式)

1:1 truth 金标准: **parameter/localparam 必须从信号图中过滤** — 参数名绝不出现在
节点集 (过滤错 = 污染整个图), 条件字符串保留参数名 (不解析为字面量)。

Fixtures:
- golden_dataflow_33_parameter_filter.sv (param_filter): parameter WIDTH/SAT_VAL
  用于端口位宽 + ternary 条件; localparam ZERO 用于 ternary 真分支

1:1 预期 (实测于 iter_093):
- 节点: a, b, y, y.ternary_SAT_VAL_a — WIDTH/SAT_VAL/ZERO 均不在图中
- DRIVER 条件: '!(a > SAT_VAL)' (参数名保留在条件串)
- ternary 结构: a→ternary BRANCH_CONDITION, ternary→y BRANCH_RESULT

⚠️ 已知 quirk (iter_093 发现, 记录待定): ternary 真分支 ZERO (localparam 常量)
不产生常量边 — 局部常量在 ternary 分支中的驱动边缺失, 待方豆定夺。
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


class TestParameterFilterTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_33_parameter_filter: parameter 过滤"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_33_parameter_filter.sv")
        cls.m = "param_filter"

    def test_parameter_names_absent(self):
        """反例式: parameter WIDTH/SAT_VAL 和 localparam ZERO 绝不在节点集."""
        node_ids = set(self.g.nodes())
        for p in ("WIDTH", "SAT_VAL", "ZERO"):
            self.assertNotIn(p, node_ids, f"parameter {p} 不应是信号节点")
            self.assertNotIn(f"{self.m}.{p}", node_ids, f"{p} 不应出现在图中")

    def test_node_set_exact(self):
        """节点集精确: a, b, y, y.ternary_SAT_VAL_a."""
        expected = {f"{self.m}.a", f"{self.m}.b", f"{self.m}.y",
                    f"{self.m}.y.ternary_SAT_VAL_a"}
        self.assertEqual(set(self.g.nodes()), expected, "param_filter 节点集偏离")

    def test_condition_keeps_param_name(self):
        """条件字符串保留参数名: '!(a > SAT_VAL)' (不解析为 8'd255)."""
        m = self.m
        conds = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                conds.add((s, d, e.kind.name, e.condition))
        self.assertIn((f"{m}.a", f"{m}.y", "DRIVER", "!(a > SAT_VAL)"), conds)
        self.assertIn((f"{m}.b", f"{m}.y", "DRIVER", "!(a > SAT_VAL)"), conds)

    def test_ternary_structure(self):
        """ternary: a→BRANCH_CONDITION, ternary→y BRANCH_RESULT."""
        m = self.m
        tri = {t for t in
               ((s, d, e.kind.name) for s, d in self.g.edges()
                for e in self.g._edge_data.get((s, d), []))
               if t[2].startswith("BRANCH")}
        self.assertEqual(tri, {
            (f"{m}.a", f"{m}.y.ternary_SAT_VAL_a", "BRANCH_CONDITION"),
            (f"{m}.y.ternary_SAT_VAL_a", f"{m}.y", "BRANCH_RESULT"),
        }, "ternary 结构偏离")

    def test_no_param_value_nodes(self):
        """参数值 8'd255 不产生常量节点 (参数解析不泄漏)."""
        node_ids = set(self.g.nodes())
        self.assertNotIn("8'd255", node_ids, "参数值不应作为常量节点")


if __name__ == "__main__":
    unittest.main()
