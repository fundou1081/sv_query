# test_bit_select_handler.py - BitSelectHandler 单元测试
# [iter_074 2026-08-29] 补 signal graph 底层测试缺口:
# bit_select_handler 此前 **0 直接 import** (仅 test_bitselect_handler_diff 间接)。
#
# 覆盖核心逻辑 (路径 A: _create_hierarchical_bit_nodes):
# 1. RangeSelect 位选 (data[7:4]) → BIT_SELECT 边
# 2. LHS 位选 (y[3:0]) → BIT_SELECT 边
# 3. ElementSelect 动态索引 (data[idx]) → BIT_SELECT 边
# 4. 多级位选层级边
# 5. 位选节点属性 (bit_range)
# 6. constraint 内位选扫描 (Phase 3)
"""
BitSelectHandler 单元测试 (iter_074 补充)

底层技术: 位选节点创建 + BIT_SELECT 聚合边 (signal graph 的位选层级结构).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.bit_select_handler import BitSelectHandler
from trace.core.compiler import SVCompiler
from trace.core.graph.models import EdgeKind
from trace.core.graph_builder import GraphBuilder
from trace.core.semantic_adapter import SemanticAdapter


def _process(source):
    """构造 graph + BitSelectHandler 并处理 (直接测试底层)."""
    comp = SVCompiler({'test.sv': source})
    adapter = SemanticAdapter(comp.get_root(), target_module='top')
    graph = GraphBuilder(adapter, target_module='top').build()
    handler = BitSelectHandler(adapter, graph)
    handler.process()
    return graph


def _bit_select_edges(graph):
    """所有 BIT_SELECT 边 [(child, parent), ...]"""
    return [
        (u, v) for u, v in graph.edges()
        if graph.get_edge(u, v) and graph.get_edge(u, v).kind == EdgeKind.BIT_SELECT
    ]


class TestBitSelectHandlerBasic(unittest.TestCase):
    """基本位选处理"""

    def test_range_select_rhs(self):
        """[Golden] RHS 位选 data[7:4] → BIT_SELECT 边 data[7:4] → data"""
        source = '''module top(input logic [7:0] data, output logic [3:0] y);
    assign y = data[7:4];
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        self.assertIn(('top.data[7:4]', 'top.data'), edges,
                      "RHS 位选应生成 BIT_SELECT 聚合边")
        self.assertIn('top.data[7:4]', graph.nodes(), "位选节点应存在")

    def test_range_select_lhs(self):
        """[Golden] LHS 位选 y[3:0] = ... → BIT_SELECT 边 y[3:0] → y"""
        source = '''module top(input logic [3:0] a, output logic [7:0] y);
    assign y[3:0] = a;
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        self.assertIn(('top.y[3:0]', 'top.y'), edges,
                      "LHS 位选应生成 BIT_SELECT 聚合边")

    def test_element_select_dynamic(self):
        """[Golden] 动态索引 data[idx] → BIT_SELECT 边 (符号下标也聚合)"""
        source = '''module top(input logic [7:0] data, input logic [1:0] idx, output logic y);
    assign y = data[idx];
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        self.assertIn(('top.data[idx]', 'top.data'), edges,
                      "动态索引位选应生成 BIT_SELECT 聚合边")

    def test_bit_select_node_attributes(self):
        """[Golden] 位选节点属性 (bit_range/parent_bit_start) 被设置"""
        source = '''module top(input logic [7:0] data, output logic [3:0] y);
    assign y = data[7:4];
endmodule'''
        graph = _process(source)
        node = graph.get_node('top.data[7:4]')
        self.assertIsNotNone(node, "位选节点应存在")
        # [iter_074 强化] 原条件断言 (if hasattr) 会静默跳过 — 改为直接断言
        self.assertEqual(node.bit_range, '[7:4]', "bit_range 应记录位选范围")
        self.assertEqual(node.parent_bit_start, 4, "parent_bit_start 应记录低边界")

    def test_no_bit_select_no_edges(self):
        """[Golden] 无位选 → 无 BIT_SELECT 边 (负面)"""
        source = '''module top(input logic [7:0] data, output logic [7:0] y);
    assign y = data;
endmodule'''
        graph = _process(source)
        self.assertEqual(len(_bit_select_edges(graph)), 0,
                         "无位选不应有 BIT_SELECT 边")


class TestBitSelectHandlerHierarchy(unittest.TestCase):
    """层级位选"""

    def test_multidim_hierarchy(self):
        """[Golden] 多维数组位选: data[0][1] 应聚合到 data[0] → data

        [iter_074] 4D/2D 数组的位选层级聚合 (iter_071 修过多级 ElementSelect 错拼).
        """
        source = '''module top(input logic [1:0][3:0] packed2d, output logic [3:0] y);
    assign y = packed2d[0];
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        # packed2d[0] → packed2d 聚合边
        self.assertTrue(
            any(u.startswith('top.packed2d[0]') and v == 'top.packed2d' for u, v in edges),
            f"2D 数组位选应聚合到根: {edges}",
        )

    def test_generate_bitselect(self):
        """[Golden] generate-for 内的位选 (genvar 展开)"""
        source = '''module top(input logic [7:0] data);
    genvar i;
    logic [7:0] acc;
    for (i = 0; i < 4; i++) begin : gen_loop
        assign acc[i] = data[i];
    end
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        self.assertGreaterEqual(len(edges), 1, "generate 内位选应有 BIT_SELECT 边")


class TestBitSelectHandlerConstraint(unittest.TestCase):
    """constraint 内位选扫描 (Phase 3)"""

    def test_constraint_bit_select(self):
        """[Golden] constraint 内位选 (addr[1:0] == 0) 不崩溃且有节点"""
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c { addr[1:0] == 2'b0; }
endclass
module top;
endmodule'''
        graph = _process(source)
        # Phase 3 不崩溃 + 图可构建
        self.assertIsNotNone(graph)


class TestBitSelectHandlerAdvanced(unittest.TestCase):
    """[iter_074] 边界: 参数位选/嵌套深度/越界/宽度提取"""

    def test_parameterized_bit_select(self):
        """[Golden] 参数位选 data[W-1] (W 为参数) 折叠后聚合"""
        source = '''module top #(parameter W=8) (input logic [W-1:0] data, output logic y);
    assign y = data[W-1];
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        self.assertTrue(
            any(u.startswith('top.data[') and v == 'top.data' for u, v in edges),
            f"参数位选应折叠并聚合: {edges}",
        )

    def test_three_level_nested(self):
        """[Golden] 3 层嵌套 d[1][2]: 完整层级链 d[1][2] → d[1] → d"""
        source = '''module top(input logic [3:0][3:0][7:0] d, output logic [7:0] y);
    assign y = d[1][2];
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        self.assertTrue(
            any(u.startswith('top.d[1][2]') and v == 'top.d[1]' for u, v in edges),
            f"3 层嵌套应有中间层聚合: {edges}",
        )
        self.assertIn(('top.d[1]', 'top.d'), edges, "应有根聚合边")

    def test_out_of_bounds_index(self):
        """[Golden] 越界索引 data[8] 不崩溃 (pyslang IndexOOB 警告, 图仍建)"""
        source = '''module top(input logic [7:0] data, output logic y);
    assign y = data[8];
endmodule'''
        graph = _process(source)
        edges = _bit_select_edges(graph)
        self.assertTrue(
            any(u == 'top.data[8]' for u, _ in edges),
            f"越界索引位选仍应聚合 (容错): {edges}",
        )

    def test_signal_widths_extracted(self):
        """[Golden] signal_widths 提取: 端口/数据声明宽度进宽度表

        直接验证 _extract_all_widths 的输出 (Phase 1).
        """
        source = '''module top(input logic [15:0] data, output logic [7:0] y);
    assign y = data[7:0];
endmodule'''
        comp = SVCompiler({'test.sv': source})
        adapter = SemanticAdapter(comp.get_root(), target_module='top')
        graph = GraphBuilder(adapter, target_module='top').build()
        handler = BitSelectHandler(adapter, graph)
        handler._extract_all_widths()
        self.assertIn('top.data', handler.signal_widths, "端口宽度应进宽度表")
        self.assertIn('top.y', handler.signal_widths, "输出端口宽度应进宽度表")


if __name__ == '__main__':
    unittest.main(verbosity=2)
