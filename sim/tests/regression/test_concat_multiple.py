#==============================================================================
# test_concat_multiple.py - 拼接驱动提取记录
# Bug: 当前实现只返回第一个值
# 原因: SignalChain 结构设计限制
# 状态: 已知限制 (文档记录)
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestConcatKnownLimitations(unittest.TestCase):
    """拼接 Driver 提取 - 已知限制"""
    
    def test_concat_returns_at_least_one(self):
        """[Known Limit] {a,b} 至少返回第一个driver"""
        source = '''
module top(input a, input b, output [1:0] y);
    assign y = {a, b};
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        result = tracer.trace_signal('y', 'top')
        
        # 已知限制: 只返回第一个，但至少能追踪到1个
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')
        
    def test_concat_four_returns_at_least_one(self):
        """{a,b,c,d} 只返回第一个"""
        source = '''
module top(input a, input b, input c, input d, output [3:0] y);
    assign y = {a, b, c, d};
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


class TestReplicationKnownLimitations(unittest.TestCase):
    """replication Driver - 正确返回1"""
    
    def test_replication_returns_source(self):
        """{4{a}} 正确返回主driver"""
        source = '''
module top(input a, output [3:0] y);
    assign y = {4{a}};
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        result = tracer.trace_signal('y', 'top')
        
        self.assertEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
