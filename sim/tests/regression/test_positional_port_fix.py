#==============================================================================
# test_positional_port_fix.py - 位置端口连接 Driver 提取
# Bug: 位置端口连接未提取
# 项目纪律: 金标准测试优先
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestPositionalPort(unittest.TestCase):
    """位置端口连接 Driver 提取"""
    
    def test_positional_port(self):
        """[Golden] 位置端口连接"""
        src = '''module child(input a, output y);
    assign y = a;
endmodule
module top(input a, output b);
    child u1(a, b);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('b', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')


if __name__ == '__main__':
    unittest.main()
