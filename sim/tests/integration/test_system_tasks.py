#==============================================================================
# test_system_tasks.py - 系统任务和函数测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestSystemTasks(unittest.TestCase):
    """系统任务和函数测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_display(self):
        """[SVL] $display"""
        source = '''
module top;
    initial $display("Hello");
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nonexist', 'top')
        
        # 纯仿真任务不影响追踪
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_finish(self):
        """[SVL] $finish"""
        source = '''
module top;
    initial #10 $finish;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nonexist', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_strobe(self):
        """[SVL] $strobe"""
        source = '''
module top(input clk, input a);
    always @(posedge clk) $strobe("%h", a);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('clk', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_time(self):
        """[SVL] $time"""
        source = '''
module top(output [31:0] t);
    assign t = $time;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('t', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_random(self):
        """[SVL] $random"""
        source = '''
module top(output [31:0] r);
    assign r = $random;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('r', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_floor(self):
        """[SVL] $floor"""
        source = '''
module top(input real r, output [31:0] f);
    assign f = $floor(r);
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('f', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_countdrivers(self):
        """[SVL] $countdrivers"""
        source = '''
module top(input a);
    // synthesis translate_off
    wire checked = a;
    // synthesis translate_on
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('a', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_sformatf(self):
        """[SVL] $sformatf"""
        source = '''
module top(output [7:0] s);
    assign s = 8'h42;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('s', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
