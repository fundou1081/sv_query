"""
[iter_096] T10: generate-if/case 内 wire 1:1 truth

1:1 truth 金标准: generate 编译期分支选择的精确图结构 — 激活分支的 assign 被
提取, **未激活分支的 assign 绝不出现在图中**; parameter 驱动分支选择且不出现在
节点集。任何 generate 分支选择逻辑变化导致偏离时此测试失败。

Fixtures:
- golden_dataflow_30_generate_if.sv (generate_if_demo): MODE=1 → gen_adder 激活,
  gen_subtractor 未实例化
- golden_dataflow_31_generate_case.sv (generate_case_demo): SEL=2 →
  gen_subtractor 激活, gen_adder/gen_default 未实例化

1:1 预期 (实测于 iter_096):
- generate_if_demo: 5 节点 / 6 边; op1→result 在 (gen_adder), op2→result 不在
- generate_case_demo: 5 节点 / 6 边; op2→result 在 (gen_subtractor), op1→result 不在
- 两者 parameter (MODE/SEL/W) 都不在节点集
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


def _edge_triples(graph):
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            out.add((s, d, e.kind.name))
    return out


class TestGenerateIfTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_30_generate_if: MODE=1 → gen_adder 激活"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_30_generate_if.sv")
        cls.m = "generate_if_demo"

    def test_node_set_exact(self):
        """节点集精确: data/weights/result + op1/op2 wire; MODE/W 参数不在."""
        expected = {f"{self.m}.data", f"{self.m}.weights", f"{self.m}.result",
                    f"{self.m}.op1", f"{self.m}.op2"}
        self.assertEqual(set(self.g.nodes()), expected, "generate_if_demo 节点集偏离")
        for p in ("MODE", "W"):
            self.assertNotIn(p, set(self.g.nodes()), f"parameter {p} 不应在图中")

    def test_active_branch_edges(self):
        """gen_adder 激活: op1→result 在; gen_subtractor 未实例化: op2→result 不在."""
        m = self.m
        edges = _edge_triples(self.g)
        self.assertIn((f"{m}.op1", f"{m}.result", "DRIVER"),
                      edges, "gen_adder 的 op1→result 应在 (MODE=1)")
        self.assertNotIn((f"{m}.op2", f"{m}.result", "DRIVER"),
                         edges, "gen_subtractor 未实例化, op2→result 不应在")

    def test_edge_set_exact(self):
        """边集精确: 6 条 (data/weights→op1/op2 + gen_adder 的 op1,data→result)."""
        m = self.m
        expected = {
            (f"{m}.data", f"{m}.op1", "DRIVER"),
            (f"{m}.data", f"{m}.op2", "DRIVER"),
            (f"{m}.data", f"{m}.result", "DRIVER"),   # gen_adder: result = op1 + data
            (f"{m}.op1", f"{m}.result", "DRIVER"),
            (f"{m}.weights", f"{m}.op1", "DRIVER"),
            (f"{m}.weights", f"{m}.op2", "DRIVER"),
        }
        self.assertEqual(_edge_triples(self.g), expected,
                         "generate_if_demo 边集偏离")


class TestGenerateCaseTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_31_generate_case: SEL=2 → gen_subtractor 激活"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_31_generate_case.sv")
        cls.m = "generate_case_demo"

    def test_node_set_exact(self):
        """节点集精确: data/weights/result + op1/op2 wire; SEL/W 参数不在."""
        expected = {f"{self.m}.data", f"{self.m}.weights", f"{self.m}.result",
                    f"{self.m}.op1", f"{self.m}.op2"}
        self.assertEqual(set(self.g.nodes()), expected, "generate_case_demo 节点集偏离")
        for p in ("SEL", "W"):
            self.assertNotIn(p, set(self.g.nodes()), f"parameter {p} 不应在图中")

    def test_active_branch_edges(self):
        """gen_subtractor 激活: op2→result 在; gen_adder/gen_default 不在: op1→result 不在."""
        m = self.m
        edges = _edge_triples(self.g)
        self.assertIn((f"{m}.op2", f"{m}.result", "DRIVER"),
                      edges, "gen_subtractor 的 op2→result 应在 (SEL=2)")
        self.assertNotIn((f"{m}.op1", f"{m}.result", "DRIVER"),
                         edges, "gen_adder 未实例化, op1→result 不应在")

    def test_edge_set_exact(self):
        """边集精确: 6 条 (data/weights→op1/op2 + gen_subtractor 的 op2,data→result)."""
        m = self.m
        expected = {
            (f"{m}.data", f"{m}.op1", "DRIVER"),
            (f"{m}.data", f"{m}.op2", "DRIVER"),
            (f"{m}.data", f"{m}.result", "DRIVER"),   # gen_subtractor: result = op2 - data
            (f"{m}.op2", f"{m}.result", "DRIVER"),
            (f"{m}.weights", f"{m}.op1", "DRIVER"),
            (f"{m}.weights", f"{m}.op2", "DRIVER"),
        }
        self.assertEqual(_edge_triples(self.g), expected,
                         "generate_case_demo 边集偏离")


if __name__ == "__main__":
    unittest.main()
