"""
test_bit_select.py - Bit Select 追踪金标准测试

[铁律13] 金标准测试
[铁律17] 强断言原则

场景设计:
  1. Port 位宽提取: input [7:0] d → width=(7,0)
  2. Internal signal 位宽: logic [7:0] data → width=(7,0)
  3. Bit select 节点: data[3:0] → width=(3,0), bit_range="[3:0]", parent_bit_start=0, parent_bit_end=3
  4. BIT_SELECT 边: data[3:0] --BIT_SELECT--> data
  5. Multiple bit ranges: data[7:4] → parent_bit_start=4, parent_bit_end=7

预期结果:
  节点属性:
    - top.d: width=(7, 0), bit_range=None
    - top.data: width=(7, 0), bit_range=None
    - top.data[3:0]: width=(3, 0), bit_range="[3:0]", parent_bit_start=0, parent_bit_end=3
    - top.data[7:4]: width=(3, 0), bit_range="[7:4]", parent_bit_start=4, parent_bit_end=7
    - top.slice: width=(3, 0)
  
  边:
    - top.data[3:0] --BIT_SELECT--> top.data
    - top.data[7:4] --BIT_SELECT--> top.data
    - top.data[3:0] --DRIVER--> top.slice
"""

import unittest
import sys
sys.path.insert(0, 'src')

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind, NodeKind
import pyslang


class TestBitSelectWidth(unittest.TestCase):
    """位选宽度追踪测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_port_width_extraction(self):
        """[金标准] Port 位宽提取"""
        source = '''module top(input [7:0] d, input clk);
endmodule'''
        
        graph = self._build_graph(source)
        
        d_node = graph.get_node('top.d')
        self.assertIsNotNone(d_node, "应有 top.d 节点")
        self.assertEqual(d_node.width, (7, 0),
            f"Port [7:0] 应为 width=(7, 0)，实际是 {d_node.width}")
    
    def test_internal_signal_width(self):
        """[金标准] Internal signal 位宽提取"""
        source = '''module top;
    logic [7:0] data;
    logic [3:0] slice;
endmodule'''
        
        graph = self._build_graph(source)
        
        data_node = graph.get_node('top.data')
        self.assertIsNotNone(data_node, "应有 top.data 节点")
        self.assertEqual(data_node.width, (7, 0),
            f"logic [7:0] 应为 width=(7, 0)，实际是 {data_node.width}")
        
        slice_node = graph.get_node('top.slice')
        self.assertIsNotNone(slice_node, "应有 top.slice 节点")
        self.assertEqual(slice_node.width, (3, 0),
            f"logic [3:0] 应为 width=(3, 0)，实际是 {slice_node.width}")
    
    def test_bit_select_node_attributes(self):
        """[金标准] Bit select 节点属性"""
        source = '''module top;
    logic [7:0] data;
    logic [3:0] slice;
    assign slice = data[3:0];
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查 data[3:0] 节点
        data_slice_node = graph.get_node('top.data[3:0]')
        self.assertIsNotNone(data_slice_node, "应有 top.data[3:0] 节点")
        
        # 宽度应该是子选择范围，不是父节点宽度
        self.assertEqual(data_slice_node.width, (3, 0),
            f"data[3:0] 应为 width=(3, 0)，实际是 {data_slice_node.width}")
        
        # 检查 bit_range 属性
        self.assertEqual(data_slice_node.bit_range, "[3:0]",
            f"bit_range 应为 '[3:0]'，实际是 {data_slice_node.bit_range}")
    
    def test_bit_select_parent_info(self):
        """[金标准] Bit select 父节点信息"""
        source = '''module top;
    logic [7:0] data;
    logic [3:0] slice;
    assign slice = data[3:0];
endmodule'''
        
        graph = self._build_graph(source)
        
        data_slice_node = graph.get_node('top.data[3:0]')
        
        # 检查父节点信息
        self.assertEqual(data_slice_node.parent_bit_start, 0,
            f"parent_bit_start 应为 0，实际是 {data_slice_node.parent_bit_start}")
        self.assertEqual(data_slice_node.parent_bit_end, 3,
            f"parent_bit_end 应为 3，实际是 {data_slice_node.parent_bit_end}")
    
    def test_bit_select_multiple_ranges(self):
        """[金标准] 多个位选范围"""
        source = '''module top;
    logic [7:0] data;
    logic [3:0] low;
    logic [3:0] high;
    assign low = data[3:0];
    assign high = data[7:4];
endmodule'''
        
        graph = self._build_graph(source)
        
        # data[3:0] → 低4位
        low_node = graph.get_node('top.data[3:0]')
        self.assertIsNotNone(low_node)
        self.assertEqual(low_node.bit_range, "[3:0]")
        self.assertEqual(low_node.parent_bit_start, 0)
        self.assertEqual(low_node.parent_bit_end, 3)
        
        # data[7:4] → 高4位
        high_node = graph.get_node('top.data[7:4]')
        self.assertIsNotNone(high_node)
        self.assertEqual(high_node.bit_range, "[7:4]")
        self.assertEqual(high_node.parent_bit_start, 4)
        self.assertEqual(high_node.parent_bit_end, 7)
    
    def test_bit_select_parent_node(self):
        """[金标准] Bit select 父节点关系"""
        source = '''module top;
    logic [7:0] data;
    assign data[3:0] = 4'b0;
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查父节点
        parent_node = graph.get_node('top.data')
        self.assertIsNotNone(parent_node)
        
        # 检查 data[3:0] 的父节点引用
        data_slice_node = graph.get_node('top.data[3:0]')
        self.assertIsNotNone(data_slice_node)
        self.assertEqual(data_slice_node.parent, 'top.data',
            f"parent 应为 'top.data'，实际是 {data_slice_node.parent}")
    
    def test_bit_select_edge_kind(self):
        """[金标准] BIT_SELECT 边"""
        source = '''module top;
    logic [7:0] data;
    logic [3:0] slice;
    assign slice = data[3:0];
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查 BIT_SELECT 边
        edge = graph.get_edge('top.data[3:0]', 'top.data')
        self.assertIsNotNone(edge, "应有 data[3:0] → data 的边")
        self.assertEqual(edge.kind, EdgeKind.BIT_SELECT,
            f"边类型应为 BIT_SELECT，实际是 {edge.kind}")
    
    def test_bit_select_driver_tracking(self):
        """[金标准] Bit select 的 Driver 追踪"""
        source = '''module top;
    logic [7:0] data;
    logic [3:0] slice;
    assign slice = data[3:0];
endmodule'''
        
        graph = self._build_graph(source)
        
        # DRIVER 边应该从 bit-select 节点指向目标
        edge = graph.get_edge('top.data[3:0]', 'top.slice')
        self.assertIsNotNone(edge, "应有 data[3:0] → slice 的 DRIVER 边")
        self.assertEqual(edge.kind, EdgeKind.DRIVER)


class TestBitSelectNegative(unittest.TestCase):
    """负面测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_no_parent_for_scalar(self):
        """标量信号无 parent"""
        source = '''module top;
    logic clk;
endmodule'''
        
        graph = self._build_graph(source)
        
        clk_node = graph.get_node('top.clk')
        self.assertIsNotNone(clk_node)
        self.assertIsNone(clk_node.parent,
            f"标量信号 parent 应为 None，实际是 {clk_node.parent}")
    
    def test_no_bit_range_for_parent(self):
        """父节点无 bit_range"""
        source = '''module top;
    logic [7:0] data;
    logic [3:0] slice;
    assign slice = data[3:0];
endmodule'''
        
        graph = self._build_graph(source)
        
        data_node = graph.get_node('top.data')
        self.assertIsNotNone(data_node)
        self.assertIsNone(data_node.bit_range,
            f"父节点 bit_range 应为 None，实际是 {data_node.bit_range}")


if __name__ == '__main__':
    unittest.main()