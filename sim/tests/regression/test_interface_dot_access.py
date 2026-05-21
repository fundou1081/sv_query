"""
Interface Dot Access Test
[P0-1] 支持 interface 点号访问 (ifc.data)
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestInterfaceDotAccess(unittest.TestCase):
    
    def _make_tracer(self, source, module_name='top'):
        tracer = UnifiedTracer(sources={module_name: source})
        tracer.build_graph()
        return tracer
    
    def test_simple_interface_dot_access(self):
        """[P0-1] 简单 interface 点号访问"""
        source = '''
interface simple_if;
    logic [7:0] data;
endinterface

module top(simple_if ifc, input [7:0] din);
    assign ifc.data = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        nodes = list(tracer.get_graph().nodes())
        
        self.assertTrue(
            any('ifc.data' in n for n in nodes),
            f"ifc.data should exist, got: {nodes}"
        )
    
    def test_interface_signal_assignment(self):
        """[P0-1] Interface 信号赋值"""
        source = '''
interface simple_if;
    logic [7:0] data;
endinterface

module top(simple_if ifc, input [7:0] din);
    assign ifc.data = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        edges = list(tracer.get_graph().edges())
        edge_ids = [f"{s}->{d}" for s, d in edges]
        
        self.assertTrue(
            any('din' in e and 'ifc.data' in e for e in edge_ids),
            f"Should have din -> ifc.data edge, got: {edge_ids}"
        )
    
    def test_interface_with_multiple_signals(self):
        """[P0-1] 多信号 interface"""
        source = '''
interface complex_if;
    logic [7:0] data;
    logic valid;
    logic [1:0] err;
endinterface

module top(complex_if bus, input [7:0] din, input vld, input [1:0] err_in);
    assign bus.data = din;
    assign bus.valid = vld;
    assign bus.err = err_in;
endmodule'''
        
        tracer = self._make_tracer(source)
        nodes = list(tracer.get_graph().nodes())
        
        self.assertTrue(any('bus.data' in n for n in nodes), f"bus.data should exist: {nodes}")
        self.assertTrue(any('bus.valid' in n for n in nodes), f"bus.valid should exist: {nodes}")
        self.assertTrue(any('bus.err' in n for n in nodes), f"bus.err should exist: {nodes}")


if __name__ == '__main__':
    unittest.main()
