#==============================================================================
# test_advanced_grammar.py - 高级语法 Driver 提取测试
# 按项目纪律: 先有测试，再开发
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestForLoopExtraction(unittest.TestCase):
    """for 循环语法"""
    
    def test_generate_for(self):
        """generate for 块"""
        source = '''
module top(input clk, output [3:0] out);
    genvar i;
    generate
        for (i=0; i<4; i=i+1) begin : g
            assign out[i] = clk;
        end
    endgenerate
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_for_loop_in_always(self):
        """always 中的 for"""
        source = '''
module top(input clk, input [7:0] data, output logic [7:0] q);
    integer i;
    always_ff @(posedge clk) begin
        for (i = 0; i < 8; i = i + 1) begin
            q[i] <= data[i];
        end
    end
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('q', 'top')
        
        # for 循环可以提取到第一个驱动
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


class TestProceduralTimingExtraction(unittest.TestCase):
    """过程时序"""
    
    def test_wait(self):
        """wait 语句"""
        source = '''
module top(input req);
    always wait(req);
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        # 能解析即可
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())
    
    def test_always_begin_end(self):
        """always begin end"""
        source = '''
module top(input clk, input d, output logic q);
    always @(posedge clk) begin
        q <= d;
    end
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('q', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium'])


class TestClockingBlockExtraction(unittest.TestCase):
    """clocking block"""
    
    def test_clocking_block(self):
        """clocking block"""
        source = '''
module top(input clk);
    clocking cb @(posedge clk);
        input data;
        output enable;
    endclocking
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        # 能解析不崩溃
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())


class TestSequencePropertyExtraction(unittest.TestCase):
    """sequence/property (assertion)"""
    
    def test_sequence(self):
        """sequence 定义"""
        source = '''
module top();
    sequence s1;
        req |-> ##1 ack;
    endsequence
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        # 能解析不崩溃
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())
    
    def test_property(self):
        """property 定义"""
        source = '''
module top();
    property p1;
        req |-> ##1 ack;
    endproperty
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        tracer.build_graph()
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()
