#==============================================================================
# test_case_stmt.py - case 语句测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestCaseStmt(unittest.TestCase):
    """case 语句测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_case_simple(self):
        """[Complex] 基础 case"""
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    input wire b,
    output reg q
);
    always_comb case (sel)
        2'b00:   q = a;
        2'b01:   q = b;
    endcase
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_casex(self):
        """[Complex] casex (X作为无关位)"""
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    output wire q
);
    casex (sel)
        2'b00:   q = a;
        2'bx1:   q = a;
    endcasex
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_casez(self):
        """[Complex] casez (Z作为无关位)"""
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    output wire q
);
    casez (sel)
        2'b00:   q = a;
        2'bz1:   q = a;
    endcasez
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_priority_case(self):
        """[Complex] priority case"""
        source = '''
module top(
    input wire [2:0] sel,
    input wire a,
    output reg q
);
    always_comb priority case (1'b1)
        sel[2]: q = a;
        sel[1]: q = a;
    endcase
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_unique_case(self):
        """[Complex] unique case"""
        source = '''
module top(
    input wire [1:0] sel,
    input wire a,
    input wire b,
    output reg q
);
    always_comb unique case (sel)
        2'b00:   q = a;
        2'b01:   q = b;
        default: q = 1'b0;
    endcase
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
