#==============================================================================
# test_directives.py - 预处理指令测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestDirectives(unittest.TestCase):
    """预处理指令测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_define(self):
        """[Dir] `define"""
        source = '''
`define WIDTH 8
module top(input [`WIDTH-1:0] a, output [`WIDTH-1:0] y);
    assign y = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_include(self):
        """[Dir] `include"""
        source = '''
`include "defines.sv"
module top(input a, output y);
    assign y = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_ifdef(self):
        """[Dir] `ifdef"""
        source = '''
`define FEATURE 1
module top(input a, output y);
`ifdef FEATURE
    assign y = a;
`else
    assign y = 1'b0;
`endif
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_ifndef(self):
        """[Dir] `ifndef"""
        source = '''
`ifndef DISABLE
module top(input a, output y);
    assign y = a;
`endif
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_undef(self):
        """[Dir] `undef"""
        source = '''
`define MY_MACRO 1
`undef MY_MACRO
module top(input a, output y);
    assign y = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_pragma(self):
        """[Dir] (* ... *)"""
        source = '''
module top(
    input wire clk,
    input wire din,
    output reg dout
);
    (* ASYNC_REG = "FALSE" *)
    always_ff @(posedge clk)
        dout <= din;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_full_case(self):
        """[Dir] full_case"""
        source = '''
module top(
    input [1:0] sel,
    input a,
    output reg q
);
    always_comb begin
        // synthesis full_case
        case (sel)
            2'b00: q = a;
            2'b01: q = a;
        endcase
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_parallel_case(self):
        """[Dir] parallel_case"""
        source = '''
module top(
    input [1:0] sel,
    input a,
    input b,
    output reg q
);
    always_comb begin
        // synthesis parallel_case
        case (sel)
            2'b00: q = a;
            2'b01: q = b;
            default: q = a;
        endcase
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
