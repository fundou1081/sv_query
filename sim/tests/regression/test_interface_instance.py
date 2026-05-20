# test_interface_instance.py - Interface 实例化金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
Interface 实例化语法:
1. interface 实例化
2. 模块端口连接
3. 接口信号追踪
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestInterfaceInstance(unittest.TestCase):
    """Interface 实例化测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_interface_instantiation(self):
        """[Golden] interface 实例化
        
        RTL:
        interface bus_if;
            logic [7:0] data;
        endinterface
        
        module testbench;
            bus_if ifc();
            assign ifc.data = 8'hAA;
        endmodule
        
        预期:
        - bus_if 实例化成功
        - ifc.data 节点存在
        - 8'hAA -> ifc.data 驱动关系
        """
        source = '''interface bus_if;
    logic [7:0] data;
endinterface

module testbench;
    bus_if ifc();
    assign ifc.data = 8'hAA;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: ifc.data 节点存在
        has_ifc_data = any('ifc.data' in n for n in nodes)
        self.assertTrue(has_ifc_data, f"ifc.data not found in {nodes}")
        
        # 验证: 8'hAA -> ifc.data 驱动关系
        has_driver = any("8'hAA" in edge[0] and 'ifc.data' in edge[1] for edge in edges)
        self.assertTrue(has_driver, f"8'hAA -> ifc.data not found in {edges}")
    
    def test_interface_port_connection(self):
        """[Golden] interface 端口连接
        
        RTL:
        interface bus_if;
            logic [7:0] data;
        endinterface
        
        module top(bus_if.master ifc);
            assign ifc.data = 8'h0;
        endmodule
        
        module testbench;
            bus_if ifc();
            top u_top(.ifc(ifc));
        endmodule
        
        预期:
        - u_top.ifc 连接到 ifc
        - ifc.data 驱动关系正确
        """
        source = '''interface bus_if;
    logic [7:0] data;
endinterface

module top(bus_if.master ifc);
    assign ifc.data = 8'h0;
endmodule

module testbench;
    bus_if ifc();
    top u_top(.ifc(ifc));
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())
        
        nodes = list(tracer.get_graph().nodes())
        edges = list(tracer.get_graph().edges())
        
        # 验证: u_top.ifc 节点存在
        has_u_top_ifc = any('u_top.ifc' in n for n in nodes)
        self.assertTrue(has_u_top_ifc, f"u_top.ifc not found in {nodes}")
        
        # 验证: ifc.data 节点存在
        has_ifc_data = any('ifc.data' in n for n in nodes)
        self.assertTrue(has_ifc_data, f"ifc.data not found in {nodes}")

if __name__ == '__main__':
    unittest.main()
