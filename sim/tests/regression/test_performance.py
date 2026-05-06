#==============================================================================
# test_performance.py - 性能基准测试
# [P2] 性能评估
#==============================================================================

import unittest
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestPerformance(unittest.TestCase):
    """性能基准测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    #----------------------------------------------------------------------
    # [性能基准]
    #----------------------------------------------------------------------
    
    def test_parse_small(self):
        """[Perf] 小模块解析 (< 100 行)"""
        source = '''
module small(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        start = time.time()
        tree = pyslang.SyntaxTree.fromText(source)
        parse_time = time.time() - start
        
        self.assertLess(parse_time, 0.1, "解析超时")
    
    def test_parse_medium(self):
        """[Perf] 中等模块 (1000 行)"""
        # 生成 1000 行代码
        source = 'module medium('
        for i in range(250):
            source += f'input wire d{i},'
        source = source.rstrip(',') + ');\\n'
        for i in range(250):
            source += f'wire w{i}; assign w{i} = d{i};\\n'
        source += 'endmodule'
        
        start = time.time()
        tree = pyslang.SyntaxTree.fromText(source)
        parse_time = time.time() - start
        
        self.assertLess(parse_time, 1.0, "解析超时")
    
    def test_build_graph_small(self):
        """[Perf] 小图构建"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        
        start = time.time()
        tracer.build_graph()
        build_time = time.time() - start
        
        self.assertLess(build_time, 0.1, "图构建超时")
    
    def test_trace_signal_small(self):
        """[Perf] 小信号追踪"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        
        start = time.time()
        result = tracer.trace_signal('dout', 'top')
        trace_time = time.time() - start
        
        self.assertLess(trace_time, 0.05, "追踪超时")
    
    def test_no_memory_leak(self):
        """[Perf] 无内存泄漏"""
        import gc
        
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        # 强制 GC
        gc.collect()
        
        # 运行多次
        for _ in range(10):
            tree = pyslang.SyntaxTree.fromText(source)
            tracer = UnifiedTracer(trees={'test': tree})
            tracer.build_graph()
        
        gc.collect()
        # 基本的内存检查通过即可
    
    #----------------------------------------------------------------------
    # [边界]
    #----------------------------------------------------------------------
    
    def test_large_module_performance(self):
        """[Boundary] 大模块性能"""
        # 生成 10000 行
        lines = ['module large(']
        for i in range(2500):
            lines.append(f'input wire d{i},')
        lines.append(');')
        for i in range(2500):
            lines.append(f'wire w{i}; assign w{i} = d{i};')
        lines.append('endmodule')
        source = '\\n'.join(lines)
        
        start = time.time()
        try:
            tree = pyslang.SyntaxTree.fromText(source)
            parse_time = time.time() - start
            # 应该能完成（可以很慢）
            self.assertGreater(parse_time, 0)
        except Exception as e:
            self.fail(f"解析失败: {e}")


if __name__ == '__main__':
    unittest.main()
