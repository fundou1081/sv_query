#==============================================================================
# test_replication_fix.py - Replication LHS 修复测试
# Bug: {2{a}} 格式返回 0 drivers
# 项目纪律: 金标准测试优先
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestReplicationFix(unittest.TestCase):
    """Replication 修复测试"""
    
    def test_replication_lhs(self):
        """[Golden] Replication LHS: {2{a}}"""
        src = 'module top(input a, output [3:0] y); assign y = {2{a}}; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('y', 'top')
        
        # 期望: 1 driver
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')
    
    def test_replication_triple(self):
        """[Golden] 三次复制: {3{a}}"""
        src = 'module top(input a, output [5:0] y); assign y = {3{a}}; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_replication_mixed(self):
        """[Golden] 混合复制: {2{a},b}"""
        src = 'module top(input a,b, output [4:0] y); assign y = {2{a},b}; endmodule'
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
