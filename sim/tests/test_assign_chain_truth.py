"""
[iter_088] T1: assign 链基础数据流 1:1 truth

1:1 truth 金标准: 固定 fixture 的**精确图结构** (节点集 + 边集 + kind) — 任何提取
逻辑变化 (pyslang API / assign 处理 / 位选 / 网表声明) 导致偏离时此测试失败。
与 generate_for_chain / cross_module truth 同风格, 但用**集合相等**断言
(多一个节点/边 = 偏离), 而非仅存在性断言。

Fixtures:
- golden_dataflow_1_op.sv (simple_op): 纯 assign 二元运算
    assign sum = a + b;  assign prod = a * b;
- golden_dataflow_5_combined.sv (combined): wire 网表声明链 + assign 位选
    wire [15:0] sum = a + b;  wire [15:0] prod = sum * c;
    assign y = prod[15:8] + 8'd128;

1:1 预期 (实测于 iter_088):
- simple_op: 节点 {a, b, sum, prod}, 边 4 条 DRIVER (a/b → sum, a/b → prod)
- combined: 节点 {a, b, c, y, sum, prod, prod[15:8]}, 边 6 条
    (a,b→sum DRIVER; c,sum→prod DRIVER; prod[15:8]→prod BIT_SELECT;
     prod[15:8]→y DRIVER slice='[15:8]')
  net-decl 路径的 expression 干净 ('a + b' / 'sum * c'), 可一并锁定.

⚠️ 已知缺陷 (iter_088 发现, 已记录, 不纳入本 golden 断言 — 修好后再补断言):
- assign 边的 edge.expression 提取为整份源文件+空字节 (下游 handshake/dataflow
  消费受影响) — 本文件只锁定 net-decl 路径的干净 expression.
- net-decl wire 显式位宽被忽略 (wire [15:0] x → width=(1,0)) — 宽度断言不纳入
  truth 层范围 (unit 层 test_width_extraction 覆盖), 待修.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"


def _build_graph(fixture_name: str):
    """构建 fixture 的 1:1 图 (独立编译, 无缓存污染)."""
    path = FIXTURE_DIR / fixture_name
    tracer = UnifiedTracer(sources={str(path): path.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


def _edge_triples(graph):
    """(src, dst, kind.name) 精确三元组集合."""
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            out.add((s, d, e.kind.name))
    return out


class TestSimpleOpAssignTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_1_op: 纯 assign 二元运算"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_1_op.sv")
        cls.mod = "simple_op"

    def test_node_set_exact(self):
        """节点集必须精确等于 {a, b, sum, prod} — 无多余节点."""
        expected = {"a", "b", "sum", "prod"}
        actual = {n.split(".", 1)[1] for n in self.g.nodes()}
        self.assertEqual(actual, expected, f"simple_op 节点集偏离: {actual}")

    def test_port_kinds(self):
        """a/b 是 PORT_IN, sum/prod 是 PORT_OUT."""
        g = self.g
        for p in ("a", "b"):
            self.assertEqual(g.get_node(f"{self.mod}.{p}").kind.name, "PORT_IN", p)
        for p in ("sum", "prod"):
            self.assertEqual(g.get_node(f"{self.mod}.{p}").kind.name, "PORT_OUT", p)

    def test_edge_set_exact(self):
        """边集必须精确等于 4 条 DRIVER: a/b → sum, a/b → prod."""
        expected = {
            (f"{self.mod}.a", f"{self.mod}.sum", "DRIVER"),
            (f"{self.mod}.b", f"{self.mod}.sum", "DRIVER"),
            (f"{self.mod}.a", f"{self.mod}.prod", "DRIVER"),
            (f"{self.mod}.b", f"{self.mod}.prod", "DRIVER"),
        }
        self.assertEqual(_edge_triples(self.g), expected,
                         "simple_op 边集偏离 (assign 二元运算)")

    def test_no_extra_edges(self):
        """总边数 = 4 (assign 边无重复/无 CLOCK/RESET 误判)."""
        self.assertEqual(len(list(self.g.edges())), 4)


class TestCombinedWireAssignTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_5_combined: wire 声明链 + assign 位选"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_5_combined.sv")
        cls.mod = "combined"

    def test_node_set_exact(self):
        """节点集必须精确等于 {a,b,c,y,sum,prod,prod[15:8]} — 位选节点存在, 无多余."""
        expected = {"a", "b", "c", "y", "sum", "prod", "prod[15:8]"}
        actual = {n.split(".", 1)[1] for n in self.g.nodes()}
        self.assertEqual(actual, expected, f"combined 节点集偏离: {actual}")

    def test_edge_set_exact(self):
        """边集必须精确等于 6 条 (4 net-decl DRIVER + 1 BIT_SELECT + 1 slice DRIVER)."""
        m = self.mod
        expected = {
            (f"{m}.a", f"{m}.sum", "DRIVER"),           # wire sum = a + b
            (f"{m}.b", f"{m}.sum", "DRIVER"),
            (f"{m}.c", f"{m}.prod", "DRIVER"),          # wire prod = sum * c
            (f"{m}.sum", f"{m}.prod", "DRIVER"),
            (f"{m}.prod[15:8]", f"{m}.prod", "BIT_SELECT"),  # 位选回边
            (f"{m}.prod[15:8]", f"{m}.y", "DRIVER"),    # assign y = prod[15:8] + ...
        }
        self.assertEqual(_edge_triples(self.g), expected,
                         "combined 边集偏离 (wire 链 + assign 位选)")

    def test_net_decl_expressions(self):
        """net-decl 路径 expression 干净: 'a + b' / 'sum * c' (assign 路径有 bug, 不断言)."""
        g = self.g
        e1 = g.get_edge(f"{self.mod}.a", f"{self.mod}.sum")
        self.assertEqual(e1.expression, "a + b", "wire sum = a + b 的 expression")
        e2 = g.get_edge(f"{self.mod}.sum", f"{self.mod}.prod")
        self.assertEqual(e2.expression, "sum * c", "wire prod = sum * c 的 expression")

    def test_slice_edge_bit_range(self):
        """assign y = prod[15:8] + ... 的 DRIVER 边必须带 bit_slice='[15:8]'."""
        g = self.g
        e = g.get_edge(f"{self.mod}.prod[15:8]", f"{self.mod}.y")
        self.assertEqual(e.bit_slice, "[15:8]", "slice 边必须保留 [15:8]")

    def test_bit_select_node(self):
        """位选节点 prod[15:8] 必须存在且 bit_range 正确."""
        n = self.g.get_node(f"{self.mod}.prod[15:8]")
        self.assertIsNotNone(n, "prod[15:8] 位选节点应存在")
        self.assertEqual(n.bit_range, "[15:8]")


if __name__ == "__main__":
    unittest.main()
