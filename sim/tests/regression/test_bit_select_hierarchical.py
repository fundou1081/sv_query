#==============================================================================
# test_bit_select_hierarchical.py - 金标准测试: 方案C 分层位选择
# 铁律13: 先推导金标准，再验证
#==============================================================================
# 方案C 图模型:
#   父节点: top.data (完整信号)
#   子节点: top.data[3] (位选择，parent=top.data)
#   聚合边: top.data[3] → top.data (BIT_SELECT)
#   驱动边: top.data[3] → top.y (DRIVER)
#   查询 data 时: 通过父节点聚合所有位驱动
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind


class TestBitSelectHierarchical(unittest.TestCase):
    """方案C: 分层位选择节点"""

    def test_bit_select_creates_parent_and_child(self):
        """[Golden] 位选择创建父子节点
        RTL: always_comb y = data[3];
        金标准:
        | 节点            | 类型   | parent     |
        |-----------------|--------|------------|
        | top.data        | PORT_IN| None       |
        | top.data[3]     | SIGNAL | top.data   |
        | top.y           | PORT_IN| None       |
        | 边: top.data[3] → top.data (BIT_SELECT) |
        | 边: top.data[3] → top.y (DRIVER)        |
        """
        src = '''
module top(input [7:0] data, output reg y);
    always_comb y = data[3];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        # 父节点存在
        self.assertIn('top.data', graph.nodes(),
            "父节点 top.data 应存在")
        # 子节点存在
        self.assertIn('top.data[3]', graph.nodes(),
            "子节点 top.data[3] 应存在")
        # 子节点有 parent
        child = graph.get_node('top.data[3]')
        self.assertIsNotNone(child)
        self.assertEqual(child.parent, 'top.data',
            "top.data[3] 的 parent 应为 top.data")
        # 聚合边存在
        agg_edge = graph.get_edge('top.data[3]', 'top.data')
        self.assertIsNotNone(agg_edge,
            "应有聚合边 data[3] → data")
        self.assertEqual(agg_edge.kind, EdgeKind.BIT_SELECT)
        # 驱动边存在
        drv_edge = graph.get_edge('top.data[3]', 'top.y')
        self.assertIsNotNone(drv_edge,
            "应有驱动边 data[3] → y")
        self.assertEqual(drv_edge.kind, EdgeKind.DRIVER)

    def test_query_parent_aggregates_bit_drivers(self):
        """[Golden] 查询父节点聚合位驱动
        RTL: always_comb y = data[3];
        查询 data 的驱动时，应通过聚合边找到 data[3] 的驱动关系
        金标准:
        | 查询      | 结果                                    |
        |-----------|-----------------------------------------|
        | trace(y)  | drivers=[data[3]] (通过聚合→data)       |
        | trace(data)| drivers=[] (data 本身无直接驱动)        |
        """
        src = '''
module top(input [7:0] data, output reg y);
    always_comb y = data[3];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1,
            "y 应有至少1个驱动")
        self.assertEqual(result.confidence, 'high')

    def test_multiple_bit_select_same_signal(self):
        """[Golden] 同一信号多个位选择
        RTL: if(sel) y=data[7]; else y=data[0];
        金标准:
        | 节点            | parent     |
        |-----------------|------------|
        | top.data        | None       |
        | top.data[7]     | top.data   |
        | top.data[0]     | top.data   |
        | 边: data[7] → data (BIT_SELECT) |
        | 边: data[0] → data (BIT_SELECT) |
        | 边: data[7] → y (DRIVER)        |
        | 边: data[0] → y (DRIVER)        |
        """
        src = '''
module top(input [7:0] data, input sel, output reg y);
    always_comb begin
        if (sel) y = data[7];
        else y = data[0];
    end
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        self.assertIn('top.data[7]', graph.nodes())
        self.assertIn('top.data[0]', graph.nodes())
        # 两个位选择都有聚合边到父节点
        self.assertIsNotNone(graph.get_edge('top.data[7]', 'top.data'))
        self.assertIsNotNone(graph.get_edge('top.data[0]', 'top.data'))
        # 两个位选择都有驱动边到 y
        self.assertIsNotNone(graph.get_edge('top.data[7]', 'top.y'))
        self.assertIsNotNone(graph.get_edge('top.data[0]', 'top.y'))
        # 查询 y 应有2个驱动
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 2,
            "y 应有2个驱动 (data[7] 和 data[0])")

    def test_assign_bit_select(self):
        """[Golden] assign 中位选择
        RTL: assign y = data[3];
        与 always_comb 同样处理
        """
        src = '''
module top(input [7:0] data, output y);
    assign y = data[3];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        self.assertIn('top.data[3]', graph.nodes())
        child = graph.get_node('top.data[3]')
        self.assertEqual(child.parent, 'top.data')
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)

    def test_range_select(self):
        """[Golden] 范围选择
        RTL: always_comb y = data[7:4];
        金标准: 子节点 data[7:4]，parent=data
        """
        src = '''
module top(input [7:0] data, output reg [3:0] y);
    always_comb y = data[7:4];
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        self.assertIn('top.data[7:4]', graph.nodes())
        child = graph.get_node('top.data[7:4]')
        self.assertEqual(child.parent, 'top.data')
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)

    def test_no_bit_select_unchanged(self):
        """[Golden] 无位选择时行为不变
        RTL: assign y = data;
        不应创建子节点
        """
        src = '''
module top(input [7:0] data, output [7:0] y);
    assign y = data;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        tracer.build_graph()
        graph = tracer.get_graph()

        self.assertIn('top.data', graph.nodes())
        # 不应有 data[...] 子节点
        for n in graph.nodes():
            if '[' in n:
                self.fail(f"不应有位选择子节点: {n}")
        result = tracer.trace_signal('y', 'top')
        self.assertGreaterEqual(len(result.drivers), 1)

    def test_backward_compat_basic(self):
        """[Golden] 向后兼容: 基本 assign
        RTL: assign y = a;
        原有测试不应破坏
        """
        src = '''
module top(input a, output y);
    assign y = a;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('y', 'top')

        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()
