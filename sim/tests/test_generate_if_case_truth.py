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
- spec_golden/probe_generate_if_wire.sv (probe_gen_if_wire): USE=1 → g_use1
  激活 (wire prod1 = a*b), g_use0 未实例化 (iter_107 #23 修复)

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
SPEC_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "spec_golden"


def _build_graph(fn: str):
    path = FIXTURE_DIR / fn
    tracer = UnifiedTracer(sources={str(path): path.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


def _build_graph_path(path: Path):
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


class TestGenerateIfAluTruth(unittest.TestCase):
    """[1:1 truth] generate_if_alu: generate-if/else 内 always (缺陷 F 修复)

    TWO_CYCLE_ALU=0 → else 分支 (always @*) 激活; if 分支 (always @(posedge clk))
    未实例化 (isUninstantiated) — 只提取激活分支, 无 CLOCK 边.
    """

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("generate_if_alu.sv")
        cls.m = "generate_if_alu"

    def test_node_set_exact(self):
        """节点集精确: 9 节点 (参数 TWO_CYCLE_ALU 不在图)."""
        expected = {f"{self.m}.alu_shl", f"{self.m}.alu_shr", f"{self.m}.clk",
                    f"{self.m}.instr_sra", f"{self.m}.instr_srai",
                    f"{self.m}.reg_op1", f"{self.m}.reg_op1[31]",
                    f"{self.m}.reg_op2", f"{self.m}.reg_op2[4:0]"}
        self.assertEqual(set(self.g.nodes()), expected, "generate_if_alu 节点集偏离")
        self.assertNotIn("TWO_CYCLE_ALU", set(self.g.nodes()), "参数不应在图中")

    def test_else_branch_driver_edges(self):
        """else 分支 (激活) 的 shift 赋值产生 DRIVER 边 (缺陷 F 修复)."""
        m = self.m
        drv = {t for t in _edge_triples(self.g) if t[2] == "DRIVER"}
        self.assertIn((f"{m}.reg_op1", f"{m}.alu_shl", "DRIVER"), drv,
                      "reg_op1→alu_shl 应在 (else 分支 shift)")
        self.assertIn((f"{m}.reg_op2[4:0]", f"{m}.alu_shl", "DRIVER"), drv,
                      "reg_op2[4:0]→alu_shl 应在")
        self.assertIn((f"{m}.instr_sra", f"{m}.alu_shr", "DRIVER"), drv,
                      "instr_sra→alu_shr 应在 ($signed concat)")

    def test_no_clock_edges(self):
        """激活分支是 always @* — 不应有 CLOCK 边 (if 分支未实例化)."""
        n_clock = sum(1 for s, d in self.g.edges()
                      for e in self.g._edge_data.get((s, d), [])
                      if e.kind.name == "CLOCK")
        self.assertEqual(n_clock, 0, "else 分支 (组合) 不应有 CLOCK 边")

    def test_bit_select_back_edges(self):
        """位选回边保留: reg_op1[31]→reg_op1, reg_op2[4:0]→reg_op2."""
        m = self.m
        bs = {t for t in _edge_triples(self.g) if t[2] == "BIT_SELECT"}
        self.assertEqual(bs, {(f"{m}.reg_op1[31]", f"{m}.reg_op1", "BIT_SELECT"),
                              (f"{m}.reg_op2[4:0]", f"{m}.reg_op2", "BIT_SELECT")},
                         "BIT_SELECT 回边偏离")


class TestGenerateIfWireTruth(unittest.TestCase):
    """[1:1 truth] probe_generate_if_wire: generate-if 单块内 wire 声明 (iter_107 #23)"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph_path(SPEC_DIR / "probe_generate_if_wire.sv")
        cls.m = "probe_gen_if_wire"

    def test_active_branch_wire_node(self):
        """激活分支 (USE=1 → g_use1) 的 wire prod1 节点存在 (hierarchical path)."""
        self.assertIsNotNone(self.g.get_node(f"{self.m}.g_use1.prod1"),
                             "g_use1.prod1 节点应存在 (#23 修复)")

    def test_active_branch_wire_edges(self):
        """wire prod1 = a * b → a→prod1, b→prod1 DRIVER 边."""
        m = self.m
        drv = {t for t in _edge_triples(self.g) if t[2] == "DRIVER"}
        self.assertEqual(drv, {
            (f"{m}.a", f"{m}.g_use1.prod1", "DRIVER"),
            (f"{m}.b", f"{m}.g_use1.prod1", "DRIVER"),
        }, "激活分支 wire 驱动边偏离")

    def test_inactive_branch_absent(self):
        """未实例化分支 (g_use0) 的 prod0 绝不出现在图中."""
        node_ids = set(self.g.nodes())
        self.assertNotIn(f"{self.m}.g_use0.prod0", node_ids,
                         "未实例化分支 wire 不应出现")


class TestGenerateCaseWireTruth(unittest.TestCase):
    """[1:1 truth] probe_generate_case_wire: generate-case 单块 wire (iter_107 #24)"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph_path(SPEC_DIR / "probe_generate_case_wire.sv")
        cls.m = "probe_gen_case_wire"

    def test_active_branch_wire(self):
        """激活分支 (SEL=2 → g_use2) 的 wire prod2 = a - b 提取."""
        m = self.m
        drv = {t for t in _edge_triples(self.g) if t[2] == "DRIVER"}
        # prod2×2 (wire 声明) + a→y (assign y 假分支) = 3
        self.assertEqual(drv, {
            (f"{m}.a", f"{m}.g_use2.prod2", "DRIVER"),
            (f"{m}.b", f"{m}.g_use2.prod2", "DRIVER"),
            (f"{m}.a", f"{m}.y", "DRIVER"),
        }, "激活分支 (g_use2) wire 驱动边偏离")

    def test_inactive_branches_absent(self):
        """未实例化分支 (g_use1/g_def) 的 prod1/prod_d 不在图中."""
        node_ids = set(self.g.nodes())
        for absent in ("g_use1.prod1", "g_def.prod_d"):
            self.assertNotIn(f"{self.m}.{absent}", node_ids,
                             f"未实例化分支 {absent} 不应出现")

    def test_ternary_references_activate_wire(self):
        """ternary 引用解析: prod2 → BRANCH_TRUE (y = SEL==2 ? prod2 : a)."""
        m = self.m
        tri = {t for t in _edge_triples(self.g) if t[2].startswith("BRANCH")}
        self.assertIn((f"{m}.g_use2.prod2", f"{m}.y.ternary_SEL", "BRANCH_TRUE"), tri)
        self.assertIn((f"{m}.a", f"{m}.y.ternary_SEL", "BRANCH_FALSE"), tri)


if __name__ == "__main__":
    unittest.main()
