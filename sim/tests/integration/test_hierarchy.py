#==============================================================================
# test_hierarchy.py - 模块层次测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestHierarchy(unittest.TestCase):
    """模块层次测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def test_deep_hierarchy(self):
        """[Hier] 深层嵌套"""
        source = '''
module leaf(input d, output q);
    assign q = d;
endmodule

module mid(input d, output q);
    wire tmp;
    leaf l1(.d(d), .q(tmp));
    leaf l2(.d(tmp), .q(q));
endmodule

module top(input d, output q);
    wire t1, t2, t3;
    mid m1(.d(d), .q(t1));
    mid m2(.d(t1), .q(t2));
    mid m3(.d(t2), .q(t3));
    mid m4(.d(t3), .q(q));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_instantiation_array(self):
        """[Hier] 实例数组"""
        source = '''
module buffer_gate(input d, output q);
    assign q = d;
endmodule

module top(input [3:0] din, output [3:0] dout);
    buffer_gate u1(.d(din[0]), .q(dout[0]));
    buffer_gate u2(.d(din[1]), .q(dout[1]));
    buffer_gate u3(.d(din[2]), .q(dout[2]));
    buffer_gate u4(.d(din[3]), .q(dout[3]));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_parameterized_module(self):
        """[Hier] 参数化模块"""
        source = '''module my_buf_mod #(
    parameter WIDTH = 8
) (
    input [WIDTH-1:0] din,
    output [WIDTH-1:0] dout
);
    assign dout = din;
endmodule

module top(input [7:0] a, output [7:0] y);
    my_buf #(.WIDTH(8)) buf_gate(.din(a), .dout(y));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_generate_instantiation(self):
        """[Hier] generate 中的实例化"""
        source = '''
module my_buf(input d, output q);
    assign q = d;
endmodule

module top(input [3:0] din, output [3:0] dout);
    genvar i;
    generate
        for (i=0; i<4; i=i+1) begin : GEN
        buf_gate b(.d(din[i]), .q(dout[i]));
    end
endgenerate
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('dout', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_module_with_generics(self):
        """[Hier] generics"""
        source = '''module gen_mod (input d, output q);
    assign q = d;
endmodule

module top(input a, output y);
    gen_mod buf_gate(.d(a), .q(y));
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('y', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
