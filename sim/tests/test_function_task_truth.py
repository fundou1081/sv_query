"""
[iter_092] T6: function/task 调用 1:1 truth

1:1 truth 金标准: 函数/任务调用的精确图结构 — 调用结果作为 function 节点驱动
输出, 调用实参驱动 function 节点, task 形参映射真边。任何调用提取逻辑变化
(flattener / 形参映射 / 函数内联) 导致偏离时此测试失败。

Fixtures:
- golden_dataflow_19_function_multi.sv (function_multi): 3 function
  (sat_add/abs_val/clamp) 组合 + 三目 + 溢出
- golden_dataflow_32_task_call.sv (top): task 调用站点形参映射 (iter_076 修复)

1:1 预期 (实测于 iter_092):
- function_multi: 12 节点 / 10 边 — function 调用节点 (sat_add/clamp) 驱动输出,
  实参 (a/b/c) 驱动 function 节点, sat_add 驱动 overflow
- task_call: 2 节点 / 1 边 — din→dout DRIVER (task output 参数驱动, 无占位边)
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


class TestFunctionMultiTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_19_function_multi: function 组合"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_19_function_multi.sv")
        cls.m = "function_multi"

    def test_node_set_exact(self):
        """节点集精确: 12 节点 (含 function 节点 sat_add/clamp + 内部 x/x[7])."""
        expected = {f"{self.m}.a", f"{self.m}.b", f"{self.m}.c", f"{self.m}.sel",
                    f"{self.m}.y", f"{self.m}.z", f"{self.m}.overflow",
                    f"{self.m}.sat_add", f"{self.m}.clamp",
                    f"{self.m}.x", f"{self.m}.x[7]",
                    f"{self.m}.y.ternary_sel"}
        self.assertEqual(set(self.g.nodes()), expected, "function_multi 节点集偏离")

    def test_function_call_edges(self):
        """function 调用: 实参驱动 function 节点, function 节点驱动输出."""
        m = self.m
        expected = {
            (f"{m}.a", f"{m}.sat_add", "DRIVER"),    # sat_add(a, b/c)
            (f"{m}.b", f"{m}.sat_add", "DRIVER"),
            (f"{m}.c", f"{m}.sat_add", "DRIVER"),
            (f"{m}.sat_add", f"{m}.overflow", "DRIVER"),  # sat_add(a,b) > 200
            (f"{m}.clamp", f"{m}.z", "DRIVER"),      # clamp(...) → z
            (f"{m}.a", f"{m}.y", "DRIVER"),          # abs_val(a) 分支
            (f"{m}.b", f"{m}.y", "DRIVER"),
            (f"{m}.x[7]", f"{m}.x", "BIT_SELECT"),   # abs_val 内部 x[7]
            (f"{m}.sel", f"{m}.y.ternary_sel", "BRANCH_CONDITION"),
            (f"{m}.y.ternary_sel", f"{m}.y", "BRANCH_RESULT"),
        }
        self.assertEqual(_edge_triples(self.g), expected,
                         "function_multi 调用边偏离")

    def test_function_result_drives_y(self):
        """y 的 4 个驱动源精确 (a/b 实参 + ternary)."""
        m = self.m
        drv_y = {s for s, d in self.g.edges() if d == f"{m}.y"
                 for e in self.g._edge_data.get((s, d), []) if e.kind.name == "DRIVER"}
        self.assertEqual(drv_y, {f"{m}.a", f"{m}.b"},
                         "y 的 DRIVER 源偏离")


class TestTaskCallTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_32_task_call: task 调用形参映射 (iter_076)"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_32_task_call.sv")

    def test_node_set_exact(self):
        """节点集精确: din, dout (task formal 不泄漏)."""
        self.assertEqual(set(self.g.nodes()), {"top.din", "top.dout"},
                         "task_call 节点集偏离")

    def test_param_mapping_edge(self):
        """真边: din→dout DRIVER (input 实参 → output 实参, 无占位边)."""
        expected = {("top.din", "top.dout", "DRIVER")}
        self.assertEqual(_edge_triples(self.g), expected,
                         "task 形参映射边偏离")

    def test_no_placeholder_edges(self):
        """总边数 = 1 — 无 EmptyArgument 占位边/多余边."""
        n = sum(1 for _ in self.g.edges())
        self.assertEqual(n, 1, f"task 调用应恰好 1 条边, got {n}")


if __name__ == "__main__":
    unittest.main()
