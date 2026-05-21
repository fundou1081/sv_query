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
        tracer = UnifiedTracer(sources={'t.sv': src})
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
        tracer = UnifiedTracer(sources={'t.sv': src})
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
        tracer = UnifiedTracer(sources={'t.sv': src})
        result = tracer.trace_signal('b', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()


class TestCrossModuleTracing(unittest.TestCase):
    """跨模块驱动追踪"""

    def test_simple_instance(self):
        """[Golden] 简单模块实例化
        RTL:
            module child(input d, output q);
                assign q = d;
            endmodule
            module top(input a, output b);
                child inst(.d(a), .q(b));
            endmodule
        金标准:
        | 信号 | 驱动源 | 来源 |
        |------|--------|------|
        | b    | [a]    | top |
        说明: b 的最终驱动源是 a，跨模块追踪应返回 a
        """
        src = '''
module child(input d, output q);
    assign q = d;
endmodule

module top(input a, output b);
    child inst(.d(a), .q(b));
endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'top.sv': src})
        result = tracer.trace_signal('b', 'top')
        
        # 跨模块追踪应返回最终驱动源 a
        driver_ids = [d.id for d in result.drivers]
        print(f"Drivers for 'b': {driver_ids}")
        self.assertIn('top.a', driver_ids,
            f"b 的驱动源应为 top.a，实际: {driver_ids}")
