#==============================================================================
# test_initial_fix.py - initial 块 Driver 提取
# Bug: initial 块未提取
# 项目纪律: 金标准测试优先
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestInitialBlock(unittest.TestCase):
    """initial 块 Driver 提取"""
    
    def test_initial_simple(self):
        """[Golden] 简单 initial"""
        src = '''module top(output y);
    initial y = 1b0;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()
