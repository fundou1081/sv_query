#==============================================================================
# test_module_hierarchy_fix.py - 模块例化 Driver 提取
# Bug: 模块例化端口连接未提取
# 项目纪律: 金标准测试优先
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestModuleHierarchy(unittest.TestCase):
    """模块 hierarchy Driver 提取"""
    
    def test_module_instantiation(self):
        """[Golden] 模块例化"""
        src = '''
module child(input a, output y);
    assign y = a;
endmodule

module top(input a, output b);
    child u1(.a(a), .y(b));
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('b', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')
    
    def test_port_connection_named(self):
        """[Golden] 命名端口连接"""
        src = '''
module child(input a, input b, output y);
    assign y = a & b;
endmodule

module top(input a, b, output y);
    child u1(.a(a), .b(b), .y(y));
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_port_connection_positional(self):
        """[Golden] 位置端口连接"""
        src = '''
module child(input a, output y);
    assign y = a;
endmodule

module top(input a, output b);
    child u1(a, b);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(trees={'t': tree})
        result = tracer.trace_signal('b', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
