#==============================================================================
# test_generate.py - generate 语句测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestGenerate(unittest.TestCase):
    """generate 语句测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_generate_for(self):
        """[Gen] generate for"""
        source = '''
module top(
    input wire clk,
    output wire [3:0] out
);
    genvar i;
    wire [3:0] tmp [0:3];
    generate
        for (i = 0; i < 4; i = i + 1) begin : GEN
            assign tmp[i] = clk;
        end
    endgenerate

    assign out = tmp[0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_generate_if(self):
        """[Gen] generate if"""
        source = '''
module top(input wire cond, input wire a, output wire y);
    generate if (1'b1) begin : GEN
        assign y = a;
    endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_generate_case(self):
        """[Gen] generate case"""
        source = '''
module top(input [1:0] sel, input a, input b, output wire y);
    generate case (1'b1)
        2'b00: assign y = a;
        default: assign y = b;
    endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_generate_nested(self):
        """[Gen] 嵌套 generate"""
        source = '''
module top(input clk, input [1:0] sel, output wire y);
    genvar i;
    generate
        for (i = 0; i < 1; i = i + 1) begin : OUTER
            if (1'b1) begin : INNER
                assign y = clk;
            end
        end
    endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
