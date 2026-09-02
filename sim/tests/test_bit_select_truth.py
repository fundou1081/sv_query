"""
[iter_090] T4: 位选 RHS/LHS 1:1 truth

1:1 truth 金标准: 位选/切片的精确图结构 — BIT_SELECT 回边 + slice DRIVER 边的
bit_slice 保留 + 位选节点 bit_range, 任何位选处理逻辑变化导致偏离时此测试失败。

Fixtures:
- golden_dataflow_3_slice.sv (with_trunc): 截断 sum[7:0] + 切片 a[15:8]
- golden_dataflow_25_array_index.sv (array_index): 4 byte-slice + indexed
  part-select `bus[{sel,3'b000} +: 8]` + 嵌套 ternary mux

1:1 预期 (实测于 iter_090):
- with_trunc: 7 节点 / 6 边 (2 BIT_SELECT 回边 + 2 slice DRIVER + 2 sum DRIVER)
- array_index: 24 节点 / 25 边 — 字节切片 BIT_SELECT 回边 + byte 驱动边 +
  `bus[?:?]` (indexed part-select 未解析的当前行为) + ternary mux

⚠️ 已知缺陷 (iter_088, 不纳入 golden): net-decl wire 宽度 (defect B) 不断言。
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


def _edge_triples(graph, with_slice=False):
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            out.add((s, d, e.kind.name, e.bit_slice) if with_slice else (s, d, e.kind.name))
    return out


class TestWithTruncSliceTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_3_slice: 截断 + 切片"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_3_slice.sv")
        cls.m = "with_trunc"

    def test_node_set_exact(self):
        """节点集精确: 7 节点 (含 a[15:8] / sum[7:0] 位选节点)."""
        expected = {f"{self.m}.a", f"{self.m}.a[15:8]", f"{self.m}.b",
                    f"{self.m}.sum", f"{self.m}.sum[7:0]",
                    f"{self.m}.y_slice", f"{self.m}.y_trunc"}
        self.assertEqual(set(self.g.nodes()), expected, "with_trunc 节点集偏离")

    def test_bit_select_back_edges(self):
        """BIT_SELECT 回边: a[15:8]→a, sum[7:0]→sum."""
        m = self.m
        bs = {t for t in _edge_triples(self.g) if t[2] == "BIT_SELECT"}
        self.assertEqual(bs, {(f"{m}.a[15:8]", f"{m}.a", "BIT_SELECT"),
                              (f"{m}.sum[7:0]", f"{m}.sum", "BIT_SELECT")},
                         "BIT_SELECT 回边偏离")

    def test_slice_driver_edges(self):
        """slice DRIVER 边必须带 bit_slice: y_trunc←sum[7:0], y_slice←a[15:8]."""
        m = self.m
        sliced = {t for t in _edge_triples(self.g, with_slice=True) if t[3]}
        self.assertEqual(sliced,
                         {(f"{m}.sum[7:0]", f"{m}.y_trunc", "DRIVER", "[7:0]"),
                          (f"{m}.a[15:8]", f"{m}.y_slice", "DRIVER", "[15:8]")},
                         "slice DRIVER 边 bit_slice 偏离")

    def test_bit_range_on_nodes(self):
        """位选节点 bit_range 精确."""
        g = self.g
        self.assertEqual(g.get_node(f"{self.m}.a[15:8]").bit_range, "[15:8]")
        self.assertEqual(g.get_node(f"{self.m}.sum[7:0]").bit_range, "[7:0]")


class TestArrayIndexSliceTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_25_array_index: 字节切片 + part-select + ternary mux"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_25_array_index.sv")
        cls.m = "array_index"

    def test_node_set_exact(self):
        """节点集精确: 24 节点 — 4 字节切片 + part + [?:?] + ternary + 各 wire."""
        expected = {
            f"{self.m}.a", f"{self.m}.b", f"{self.m}.bus", f"{self.m}.clk",
            f"{self.m}.rst_n", f"{self.m}.sel",
            f"{self.m}.bus[7:0]", f"{self.m}.bus[15:8]",
            f"{self.m}.bus[23:16]", f"{self.m}.bus[31:24]",
            f"{self.m}.bus[?:?]",          # indexed part-select 未解析 (当前行为)
            f"{self.m}.byte0", f"{self.m}.byte1", f"{self.m}.byte2", f"{self.m}.byte3",
            f"{self.m}.part", f"{self.m}.sum_lo", f"{self.m}.sum_lo[7:0]",
            f"{self.m}.mix_mid", f"{self.m}.mux_hi",
            f"{self.m}.mux_hi.ternary_sel",
            f"{self.m}.y_lo", f"{self.m}.y_mid", f"{self.m}.y_hi",
        }
        self.assertEqual(set(self.g.nodes()), expected, "array_index 节点集偏离")

    def test_byte_slice_back_edges(self):
        """4 个字节切片 BIT_SELECT 回边精确."""
        m = self.m
        bs = {t for t in _edge_triples(self.g) if t[2] == "BIT_SELECT"}
        self.assertEqual(bs, {
            (f"{m}.bus[7:0]", f"{m}.bus", "BIT_SELECT"),
            (f"{m}.bus[15:8]", f"{m}.bus", "BIT_SELECT"),
            (f"{m}.bus[23:16]", f"{m}.bus", "BIT_SELECT"),
            (f"{m}.bus[31:24]", f"{m}.bus", "BIT_SELECT"),
            (f"{m}.sum_lo[7:0]", f"{m}.sum_lo", "BIT_SELECT"),
        }, "字节切片 BIT_SELECT 回边偏离")

    def test_byte_driver_edges(self):
        """bus[N:M] → byteN 驱动边精确."""
        m = self.m
        drv = {t for t in _edge_triples(self.g) if t[2] == "DRIVER"}
        for seg, byte in (("[7:0]", "byte0"), ("[15:8]", "byte1"),
                          ("[23:16]", "byte2"), ("[31:24]", "byte3")):
            self.assertIn((f"{m}.bus{seg}", f"{m}.{byte}", "DRIVER"), drv,
                          f"bus{seg}→{byte} 应存在")

    def test_indexed_part_select_unresolved(self):
        """indexed part-select `bus[{sel,3'b000} +: 8]` → bus[?:?] 节点 (当前行为)."""
        m = self.m
        drv = {t for t in _edge_triples(self.g) if t[2] == "DRIVER"}
        self.assertIn((f"{m}.bus[?:?]", f"{m}.part", "DRIVER"), drv,
                      "bus[?:?]→part 应存在 (indexed part-select 未解析)")
        n = self.g.get_node(f"{m}.bus[?:?]")
        self.assertIsNotNone(n, "bus[?:?] 节点应存在")
        # [iter_103] 缺陷 E: 动态 part-select 宽度未知 — 不得伪造 (1,0)
        self.assertIsNone(n.width, "bus[?:?] 宽度应为 None (动态 base 无法静态解析)")

    def test_mux_ternary_structure(self):
        """嵌套 ternary mux: byte3→BRANCH_TRUE, sel→BRANCH_CONDITION, →BRANCH_RESULT."""
        m = self.m
        tri = {t for t in _edge_triples(self.g) if t[2].startswith("BRANCH")}
        self.assertIn((f"{m}.byte3", f"{m}.mux_hi.ternary_sel", "BRANCH_TRUE"), tri)
        self.assertIn((f"{m}.sel", f"{m}.mux_hi.ternary_sel", "BRANCH_CONDITION"), tri)
        self.assertIn((f"{m}.mux_hi.ternary_sel", f"{m}.mux_hi", "BRANCH_RESULT"), tri)

    def test_slice_driver_edge(self):
        """sum_lo[7:0]→y_lo DRIVER 带 bit_slice='[7:0]'."""
        m = self.m
        e = self.g.get_edge(f"{m}.sum_lo[7:0]", f"{m}.y_lo")
        self.assertIsNotNone(e, "sum_lo[7:0]→y_lo 应存在")
        self.assertEqual(e.bit_slice, "[7:0]")


if __name__ == "__main__":
    unittest.main()
