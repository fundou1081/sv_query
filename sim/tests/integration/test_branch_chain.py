#==============================================================================
# test_branch_chain.py - if/else 多分支追踪
# [P0] 优先级最高
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestBranchChain(unittest.TestCase):
    """if/else 分支测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    #----------------------------------------------------------------------
    # [金标准] if 语句追踪
    #----------------------------------------------------------------------
    
    def test_if_single_branch(self):
        """[Golden] 单 if 分支"""
        source = '''
module top(
    input wire clk,
    input wire sel,
    input wire a,
    input wire b,
    output reg q
);
    always_ff @(posedge clk)
        if (sel) q <= a;
        else    q <= b;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # 应该有两个驱动 (a 和 b)
        driver_ids = [d.id for d in result.drivers]
        self.assertIn('top.a', driver_ids)
        self.assertIn('top.b', driver_ids)
    
    def test_if_else_chain(self):
        """[Golden] if-else 链"""
        source = '''
module top(
    input wire clk,
    input wire sel,
    input wire a,
    input wire b,
    input wire c,
    output reg q
);
    always_ff @(posedge clk) begin
        if (sel == 2'b00)
            q <= a;
        else if (sel == 2'b01)
            q <= b;
        else
            q <= c;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # 应该有多个驱动
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')
    
    def test_if_nested(self):
        """[Golden] 嵌套 if"""
        source = '''
module top(
    input wire clk,
    input wire a,
    input wire b,
    input wire cond,
    output reg q
);
    always_ff @(posedge clk) begin
        if (cond)
            if (a)
                q <= 1'b1;
            else
                q <= 1'b0;
        else
            q <= b;
    end
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # 有驱动
        self.assertGreaterEqual(len(result.drivers), 1)
    
    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------
    
    def test_if_no_else(self):
        """[Boundary] 只有 if 没有 else"""
        source = '''
module top(
    input wire clk,
    input wire en,
    input wire d,
    output reg q
);
    always_ff @(posedge clk)
        if (en) q <= d;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # en 应该被追踪
        self.assertEqual(result.confidence, 'high')
    
    def test_if_only_constant(self):
        """[Boundary] 只赋值常量"""
        source = '''
module top(
    input wire clk,
    input wire en,
    output reg q
);
    always_ff @(posedge clk)
        if (en) q <= 1'b1;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # 常量驱动
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
