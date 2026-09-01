"""
[iter_088] T2: always_ff + clock/reset 1:1 truth

1:1 truth 金标准: 固定 fixture 的精确图结构 (节点集 + 边集 + kind + condition),
任何 always_ff / clock / reset / 条件提取逻辑变化导致偏离时此测试失败。

Fixtures:
- orphan_regression/orphan_01_ternary_in_always_ff.sv (orphan_01):
  always @(posedge clk or negedge rst_n), if (!rst_n) y<=0 else y<=sel?a:b
  — 异步复位 + 时序 ternary, 锁定 CLOCK/RESET 边 + 条件 DRIVER + ternary 分解
- golden_mini/fsm_demo.sv (fsm_demo):
  always @(posedge clk) 状态机: state_q<=next_state + 4 输出 case 分支
  — 锁定 case-in-sequential 条件边 + parameter 过滤 + 状态机结构

1:1 预期 (实测于 iter_088):
- orphan_01: 8 节点 / 11 边 (2 CLOCK + 2 RESET + 3 条件 DRIVER + 4 ternary 分解边)
- fsm_demo: 12 节点 / 40 边 (CLOCK 17 + DRIVER 21 + BRANCH 2), parameter IDLE..ERR
  不在图中 (过滤生效)

⚠️ 已知缺陷 (iter_088, 不纳入 golden): assign/always 路径 DRIVER 边 expression
字段为整份源文件 — 本文件只锁定 condition (干净), 不断言 expression。
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"


def _build_graph(rel_path: str):
    path = FIXTURE_DIR / rel_path
    tracer = UnifiedTracer(sources={str(path): path.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


def _edge_triples(graph, with_cond=False):
    """(src, dst, kind[, condition]) 精确元组集合."""
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            if with_cond:
                out.add((s, d, e.kind.name, e.condition))
            else:
                out.add((s, d, e.kind.name))
    return out


class TestOrphan01AsyncResetTruth(unittest.TestCase):
    """[1:1 truth] orphan_01: always_ff 异步复位 + 时序 ternary"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("orphan_regression/orphan_01_ternary_in_always_ff.sv")
        cls.m = "orphan_01"

    def test_node_set_exact(self):
        """节点集精确: y(REG) + 5 端口 + 8'd0(CONST) + y.ternary_sel(OP_TERNARY)."""
        expected = {"8'd0", "orphan_01.a", "orphan_01.b", "orphan_01.clk",
                    "orphan_01.rst_n", "orphan_01.sel", "orphan_01.y",
                    "orphan_01.y.ternary_sel"}
        self.assertEqual(set(self.g.nodes()), expected, "orphan_01 节点集偏离")

    def test_reg_kind(self):
        """y 是 REG (时序赋值); 端口 clk/rst_n/sel/a/b 是 PORT_IN."""
        self.assertEqual(self.g.get_node(f"{self.m}.y").kind.name, "REG")
        for p in ("clk", "rst_n", "sel", "a", "b"):
            self.assertEqual(self.g.get_node(f"{self.m}.{p}").kind.name, "PORT_IN", p)

    def test_edge_set_exact(self):
        """边集精确: 2 CLOCK + 2 RESET + 3 条件 DRIVER + 4 ternary 分解边 = 11."""
        m = self.m
        expected = {
            (f"{m}.clk", f"{m}.y", "CLOCK", "!rst_n"),
            (f"{m}.clk", f"{m}.y", "CLOCK", "!(!rst_n)"),
            (f"{m}.rst_n", f"{m}.y", "RESET", "!rst_n"),
            (f"{m}.rst_n", f"{m}.y", "RESET", "!(!rst_n)"),
            ("8'd0", f"{m}.y", "DRIVER", "!rst_n"),
            (f"{m}.a", f"{m}.y", "DRIVER", "!(!rst_n)"),
            (f"{m}.b", f"{m}.y", "DRIVER", "!(!rst_n)"),
            (f"{m}.a", f"{m}.y.ternary_sel", "BRANCH_TRUE", ""),
            (f"{m}.b", f"{m}.y.ternary_sel", "BRANCH_FALSE", ""),
            (f"{m}.sel", f"{m}.y.ternary_sel", "BRANCH_CONDITION", ""),
            (f"{m}.y.ternary_sel", f"{m}.y", "BRANCH_RESULT", ""),
        }
        self.assertEqual(_edge_triples(self.g, with_cond=True), expected,
                         "orphan_01 边集偏离 (CLOCK/RESET/条件/ternary)")

    def test_clk_reset_edge_counts(self):
        """CLOCK=2, RESET=2, DRIVER=3, BRANCH_*=4 分类计数."""
        kinds = {}
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                kinds[e.kind.name] = kinds.get(e.kind.name, 0) + 1
        self.assertEqual(kinds, {"CLOCK": 2, "RESET": 2, "DRIVER": 3,
                                 "BRANCH_TRUE": 1, "BRANCH_FALSE": 1,
                                 "BRANCH_CONDITION": 1, "BRANCH_RESULT": 1})


class TestFsmDemoCaseInAlwaysFfTruth(unittest.TestCase):
    """[1:1 truth] fsm_demo: case-in-sequential + parameter 过滤"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("fsm_demo.sv")
        cls.m = "fsm_demo"

    def test_node_set_exact(self):
        """节点集精确: 端口 + 寄存器 + next_state + 常量; parameter IDLE..ERR 不在图."""
        expected = {"2'b0", "2'b1", "fsm_demo.busy", "fsm_demo.clk",
                    "fsm_demo.next_state", "fsm_demo.next_state.ternary_start",
                    "fsm_demo.start", "fsm_demo.state_q", "fsm_demo.y_done",
                    "fsm_demo.y_err", "fsm_demo.y_idle", "fsm_demo.y_run"}
        self.assertEqual(set(self.g.nodes()), expected, "fsm_demo 节点集偏离")
        # parameter 过滤: IDLE/RUN/DONE/ERR 常量不应作为节点存在
        for p in ("IDLE", "RUN", "DONE", "ERR"):
            self.assertNotIn(p, {n.split(".", 1)[-1] for n in self.g.nodes()},
                             f"parameter {p} 不应是信号节点")

    def test_registers_are_reg(self):
        """state_q 和 4 个输出都是 REG."""
        for sig in ("state_q", "y_idle", "y_run", "y_done", "y_err"):
            self.assertEqual(self.g.get_node(f"{self.m}.{sig}").kind.name, "REG", sig)

    def test_clock_edge_conditions_per_branch(self):
        """每个 case 分支的 CLOCK 边带对应 state 条件 (4 分支 × 4 输出 = 16 + state_q)."""
        clk_conds = set()
        for s, d in self.g.edges():
            if s == f"{self.m}.clk":
                for e in self.g._edge_data.get((s, d), []):
                    clk_conds.add(e.condition)
        self.assertEqual(clk_conds,
                         {"", "state_q == IDLE", "state_q == RUN",
                          "state_q == DONE", "state_q == ERR"},
                         "CLOCK 边条件集偏离")
        # CLOCK 总数 = 4 输出 × 4 分支 + state_q 无分支 = 17
        n_clk = sum(1 for s, d in self.g.edges() if s == f"{self.m}.clk"
                    for _ in self.g._edge_data.get((s, d), []))
        self.assertEqual(n_clk, 17, "CLOCK 边总数偏离")

    def test_case_branch_drivers(self):
        """y_idle 的 4 个 case 分支: IDLE→2'b1, 其余→2'b0 (条件精确, 仅 DRIVER 边)."""
        g = self.g
        y_idle_drivers = set()
        for s, d in g.edges():
            if d == f"{self.m}.y_idle":
                for e in g._edge_data.get((s, d), []):
                    if e.kind.name == "DRIVER":  # CLOCK 边也指向 y_idle, 排除
                        y_idle_drivers.add((s, e.condition))
        self.assertEqual(y_idle_drivers,
                         {("2'b1", "state_q == IDLE"), ("2'b0", "state_q == RUN"),
                          ("2'b0", "state_q == DONE"), ("2'b0", "state_q == ERR")},
                         "y_idle case 分支驱动偏离")

    def test_state_transition(self):
        """状态转移: next_state→state_q DRIVER + start 触发 ternary."""
        g = self.g
        self.assertIsNotNone(g.get_edge(f"{self.m}.next_state", f"{self.m}.state_q"),
                             "next_state→state_q 应存在")
        self.assertIsNotNone(
            g.get_edge(f"{self.m}.start", f"{self.m}.next_state.ternary_start", ),
            "start→ternary 应存在")
        self.assertIsNotNone(
            g.get_edge(f"{self.m}.next_state.ternary_start", f"{self.m}.next_state"),
            "ternary→next_state 应存在")


if __name__ == "__main__":
    unittest.main()
