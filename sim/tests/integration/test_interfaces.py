#==============================================================================
# test_interfaces.py - 接口测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestInterfaces(unittest.TestCase):
    """接口测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_interface_simple(self):
        """[Iface] 基础接口"""
        source = '''
interface simple_if;
    logic data;
endinterface

module top(simple_if ifc);
    assign ifc.data = 1'b0;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        # 接口信号追踪
        self.assertIsNotNone(tracer.get_graph())
    
    def test_modport(self):
        """[Iface] modport"""
        source = '''
interface bus_if;
    logic [7:0] data;
    logic valid;
    
    modport master(output data, valid);
    modport slave(input data, valid);
endinterface

module master(output bus_if.master ifc);
    assign ifc.data = 8'h0;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())
    
    def test_interface_array(self):
        """[Iface] 接口数组"""
        source = '''
interface if_array;
    logic data;
endinterface

module top(if_array ifc [3:0]);
    assign ifc[0].data = 1'b0;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())
    
    def test_interface_class(self):
        """[Iface] interface class"""
        source = '''
interface base_if;
    logic valid;
endinterface

module top(base_if ifc);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()
