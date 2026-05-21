# test_interface_basic.py - 基础 Interface 测试
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

class TestInterfaceBasic(unittest.TestCase):
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_simple_interface(self):
        source = '''
interface my_if;
    logic [7:0] data;
endinterface

module top(my_if tb, input [7:0] din);
    assign tb.data = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        self.assertIsNotNone(tracer.get_graph())
        nodes = list(tracer.get_graph().nodes())
        self.assertTrue(any('tb.data' in n for n in nodes), f'tb.data not in {nodes}')

if __name__ == '__main__':
    unittest.main()
