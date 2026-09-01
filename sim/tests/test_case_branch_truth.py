"""
[iter_089] T3: case 多分支条件边 1:1 truth

1:1 truth 金标准: case/if-case 的**分支条件边精确结构** (src → dst + kind + condition),
任何 case 展平 / 条件合成 / 字面量归一化逻辑变化导致偏离时此测试失败。

Fixtures:
- golden_dataflow_9_case.sv (with_case): 普通 4 分支 case (2'b00/01/10/default)
- golden_dataflow_16_nested_case.sv (nested_case): 嵌套 case (复合条件 &&)
- golden_dataflow_17_if_case_mixed.sv (if_case_mixed): if-else + case 混合,
  时钟复位 + 复合条件 (always_ff)

1:1 预期 (实测于 iter_089):
- with_case: 6 节点 / 5 DRIVER 边, 条件含字面量归一化 (2'b00→'2'b0', 2'b01→'2'b1')
- nested_case: 9 节点 / 11 DRIVER 边, 复合条件 'sel == X && sub_sel == Y'
- if_case_mixed: 9 节点 / 17 边 (5 DRIVER + 6 CLOCK + 6 RESET), 条件
  '!(!rst_n) && en && mode == ...' / '!(!rst_n) && !en'

⚠️ 已知缺陷 (iter_088, 不纳入 golden): DRIVER 边 expression 字段损坏 — 只锁定 condition。
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


def _edge_triples(graph, with_cond=True):
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            out.add((s, d, e.kind.name, e.condition) if with_cond else (s, d, e.kind.name))
    return out


class TestWithCaseTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_9_case: 普通 4 分支 case"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_9_case.sv")
        cls.m = "with_case"

    def test_node_set_exact(self):
        """节点集精确: sel + a/b/c/d + y (无常量节点)."""
        expected = {f"{self.m}.sel", f"{self.m}.a", f"{self.m}.b",
                    f"{self.m}.c", f"{self.m}.d", f"{self.m}.y"}
        self.assertEqual(set(self.g.nodes()), expected, "with_case 节点集偏离")

    def test_branch_conditions_exact(self):
        """5 条 DRIVER 边条件精确 (含字面量归一化: 2'b00→'2'b0')."""
        m = self.m
        expected = {
            (f"{m}.a", f"{m}.y", "DRIVER", "sel == 2'b0"),      # 2'b00 归一化
            (f"{m}.a", f"{m}.y", "DRIVER", "sel == 2'b1"),      # 2'b01 归一化
            (f"{m}.b", f"{m}.y", "DRIVER", "sel == 2'b1"),
            (f"{m}.c", f"{m}.y", "DRIVER", "sel == 2'b10"),
            (f"{m}.d", f"{m}.y", "DRIVER", "sel == default"),
        }
        self.assertEqual(_edge_triples(self.g), expected,
                         "with_case 分支条件边偏离")

    def test_y_kind(self):
        """always @(*) 中 y 声明为 output reg, 分类为 PORT_OUT (输出端口优先)."""
        self.assertEqual(self.g.get_node(f"{self.m}.y").kind.name, "PORT_OUT")


class TestNestedCaseTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_16_nested_case: 嵌套 case 复合条件"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_16_nested_case.sv")
        cls.m = "nested_case"

    def test_node_set_exact(self):
        """节点集精确: 9 节点含 8'd0/8'd255 常量."""
        expected = {"8'd0", "8'd255", f"{self.m}.a", f"{self.m}.b",
                    f"{self.m}.c", f"{self.m}.d", f"{self.m}.sel",
                    f"{self.m}.sub_sel", f"{self.m}.y"}
        self.assertEqual(set(self.g.nodes()), expected, "nested_case 节点集偏离")

    def test_compound_conditions_exact(self):
        """11 条 DRIVER 边, 复合条件 'sel == X && sub_sel == Y' 精确."""
        m = self.m
        expected = {
            ("8'd0", f"{m}.y", "DRIVER", "sel == 2'b0"),
            ("8'd255", f"{m}.y", "DRIVER", "sel == default"),
            (f"{m}.a", f"{m}.y", "DRIVER", "sel == 2'b1 && sub_sel == 2'b0"),
            (f"{m}.a", f"{m}.y", "DRIVER", "sel == 2'b1 && sub_sel == 2'b1"),
            (f"{m}.a", f"{m}.y", "DRIVER", "sel == 2'b1 && sub_sel == default"),
            (f"{m}.b", f"{m}.y", "DRIVER", "sel == 2'b1 && sub_sel == 2'b0"),
            (f"{m}.b", f"{m}.y", "DRIVER", "sel == 2'b1 && sub_sel == 2'b1"),
            (f"{m}.c", f"{m}.y", "DRIVER", "sel == 2'b10 && sub_sel == 2'b0"),
            (f"{m}.c", f"{m}.y", "DRIVER", "sel == 2'b10 && sub_sel == 2'b1"),
            (f"{m}.c", f"{m}.y", "DRIVER", "sel == 2'b10 && sub_sel == default"),
            (f"{m}.d", f"{m}.y", "DRIVER", "sel == 2'b10 && sub_sel == 2'b0"),
            (f"{m}.d", f"{m}.y", "DRIVER", "sel == 2'b10 && sub_sel == 2'b1"),
        }
        self.assertEqual(_edge_triples(self.g), expected,
                         "nested_case 复合条件边偏离")


class TestIfCaseMixedTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_17_if_case_mixed: if-else + case 混合"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_17_if_case_mixed.sv")
        cls.m = "if_case_mixed"

    def test_node_set_exact(self):
        """节点集精确: 9 节点 (无中间信号)."""
        expected = {"8'd0", f"{self.m}.a", f"{self.m}.b", f"{self.m}.c",
                    f"{self.m}.clk", f"{self.m}.en", f"{self.m}.mode",
                    f"{self.m}.rst_n", f"{self.m}.y"}
        self.assertEqual(set(self.g.nodes()), expected, "if_case_mixed 节点集偏离")

    def test_driver_conditions_exact(self):
        """5 条 DRIVER 边: 复位 + en 分支 + case 分支 (复合条件精确)."""
        m = self.m
        expected = {
            ("8'd0", f"{m}.y", "DRIVER", "!rst_n"),
            (f"{m}.a", f"{m}.y", "DRIVER", "!(!rst_n) && en && mode == 2'b0"),
            (f"{m}.a", f"{m}.y", "DRIVER", "!(!rst_n) && en && mode == 2'b1"),
            (f"{m}.a", f"{m}.y", "DRIVER", "!(!rst_n) && en && mode == 2'b10"),
            (f"{m}.a", f"{m}.y", "DRIVER", "!(!rst_n) && en && mode == default"),
            (f"{m}.b", f"{m}.y", "DRIVER", "!(!rst_n) && en && mode == 2'b0"),
            (f"{m}.b", f"{m}.y", "DRIVER", "!(!rst_n) && !en"),
            (f"{m}.c", f"{m}.y", "DRIVER", "!(!rst_n) && en && mode == 2'b1"),
        }
        self.assertEqual(
            {t for t in _edge_triples(self.g) if t[2] == "DRIVER"}, expected,
            "if_case_mixed DRIVER 条件边偏离")

    def test_clock_reset_conditions_exact(self):
        """CLOCK/RESET 各 6 条, 条件与 DRIVER 分支一致 (每分支一条)."""
        g = self.g
        m = self.m
        conds = {
            "!rst_n",
            "!(!rst_n) && en && mode == 2'b0",
            "!(!rst_n) && en && mode == 2'b1",
            "!(!rst_n) && en && mode == 2'b10",
            "!(!rst_n) && en && mode == default",
            "!(!rst_n) && !en",
        }
        clk_conds = set()
        rst_conds = set()
        for s, d in g.edges():
            for e in g._edge_data.get((s, d), []):
                if e.kind.name == "CLOCK":
                    clk_conds.add(e.condition)
                elif e.kind.name == "RESET":
                    rst_conds.add(e.condition)
        self.assertEqual(clk_conds, conds, "CLOCK 条件集偏离")
        self.assertEqual(rst_conds, conds, "RESET 条件集偏离")
        n_clk = sum(1 for s, d in g.edges() if s == f"{m}.clk"
                    for _ in g._edge_data.get((s, d), []))
        n_rst = sum(1 for s, d in g.edges() if s == f"{m}.rst_n"
                    for _ in g._edge_data.get((s, d), []))
        self.assertEqual((n_clk, n_rst), (6, 6), "CLOCK/RESET 边数偏离")


if __name__ == "__main__":
    unittest.main()
