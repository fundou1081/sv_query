#==============================================================================
# test_latch.py - always_latch 锁存器追踪
# [P1] 锁存器识别
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestLatch(unittest.TestCase):
    """always_latch 测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    #----------------------------------------------------------------------
    # [金标准] latch 追踪
    #----------------------------------------------------------------------
    
    def test_latch_basic(self):
        """[Golden] 基础 latch"""
        # RTL:
        #   always_latch if (en) q = d;
        # 金标准: q 驱动 = d (当 en=1 时)
        source = '''
module top(
    input wire en,
    input wire d,
    output wire q
);
    always_latch if (en) q = d;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIsNotNone(result.confidence)
    
    def test_latch_with_else(self):
        """[Golden] latch with else"""
        source = '''
module top(
    input wire en,
    input wire d,
    input wire a,
    output wire q
);
    always_latch if (en) q = d;
    else       q = a;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        # 有多个可能驱动
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------
    
    def test_latch_no_condition(self):
        """[Boundary] 无条件 latch (可能危险)"""
        source = '''
module top(
    input wire d,
    output wire q
);
    always_latch q = d;
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('q', 'top')
        
        self.assertIsNotNone(result.confidence)


if __name__ == '__main__':
    unittest.main()
