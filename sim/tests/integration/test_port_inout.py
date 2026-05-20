#==============================================================================
# test_port_inout.py - PORT_INOUT 测试
#==============================================================================
"""
[铁律13] 金标准测试
测试 inout 端口的支持

金标准 (Golden Standard):
RTL:
  module tri_device(inout wire data, input sel);
    assign data = sel ? data : 1'bz;
  endmodule
  
  module top(inout wire data_bus, input sel);
    tri_device td(.data(data_bus), .sel(sel));
  endmodule

期望:
  - data_bus 节点 kind = NodeKind.PORT_INOUT
  - sel 节点 kind = NodeKind.PORT_IN
  - inout 端口被正确识别，不崩溃
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind


class TestPortInout(unittest.TestCase):
    """PORT_INOUT 测试"""
    
    def _build_graph(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        return tracer.get_graph()
    
    def test_inout_port_is_recognized(self):
        """[金标准] inout 端口应被识别为 PORT_INOUT
        
        期望:
        - top.data_bus.kind = NodeKind.PORT_INOUT
        - top.sel.kind = NodeKind.PORT_IN
        """
        source = '''
module tri_device(inout wire data, input sel);
    assign data = sel ? data : 1'bz;
endmodule

module top(inout wire data_bus, input sel);
    tri_device td(.data(data_bus), .sel(sel));
endmodule'''
        
        graph = self._build_graph(source)
        
        # 检查 data_bus
        data_bus = graph.get_node('top.data_bus')
        self.assertIsNotNone(data_bus, "data_bus 节点应该存在")
        self.assertEqual(data_bus.kind, NodeKind.PORT_INOUT,
            f"data_bus.kind 应该是 PORT_INOUT，实际是 {data_bus.kind}")
        
        # 检查 sel (应该是 PORT_IN)
        sel = graph.get_node('top.sel')
        self.assertIsNotNone(sel, "sel 节点应该存在")
        self.assertEqual(sel.kind, NodeKind.PORT_IN,
            f"sel.kind 应该是 PORT_IN，实际是 {sel.kind}")
    
    def test_inout_port_has_is_port_marker(self):
        """[金标准] inout 端口应该有 is_port=True
        
        期望: ModuleTracer 能找到 inout 端口
        """
        source = '''
module tri_device(inout wire data, input sel);
endmodule

module top(inout wire data_bus, input sel);
    tri_device td(.data(data_bus), .sel(sel));
endmodule'''
        
        graph = self._build_graph(source)
        
        data_bus = graph.get_node('top.data_bus')
        self.assertTrue(hasattr(data_bus, 'is_port'), 
            "PORT_INOUT 应该有 is_port 属性")
        self.assertTrue(data_bus.is_port,
            f"data_bus.is_port 应该是 True，实际是 {data_bus.is_port}")
    
    def test_inout_and_other_ports_coexist(self):
        """[边界] inout 与普通 input/output 端口共存
        
        期望:
        - data_bus: PORT_INOUT
        - input_only: PORT_IN
        - output_only: PORT_OUT
        """
        source = '''
module top(inout wire data_bus, input input_only, output output_only);
endmodule'''
        
        graph = self._build_graph(source)
        
        data_bus = graph.get_node('top.data_bus')
        input_only = graph.get_node('top.input_only')
        output_only = graph.get_node('top.output_only')
        
        self.assertEqual(data_bus.kind, NodeKind.PORT_INOUT)
        self.assertEqual(input_only.kind, NodeKind.PORT_IN)
        self.assertEqual(output_only.kind, NodeKind.PORT_OUT)


if __name__ == '__main__':
    unittest.main()
