#==============================================================================
# test_bit_select.py - 位选择追踪
# [P0] 优先级最高
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestBitSelect(unittest.TestCase):
    """位选择追踪测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    #----------------------------------------------------------------------
    # [金标准] 位选择追踪
    #----------------------------------------------------------------------
    
    def test_single_bit_select(self):
        """[Golden] 单比特选择 [0]"""
        # RTL: assign out = data[0];
        # 金标准: out 驱动 = data[0]
        source = '''
module top(
    input wire [7:0] data,
    output wire out
);
    assign out = data[0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        driver_ids = [d.id for d in result.drivers]
        # 方案C: 位选择信息保留，驱动为 data[...] 而非 data
        self.assertTrue(
            any('data' in d for d in driver_ids),
            f"驱动应包含 data 信号，实际: {driver_ids}"
        )
    
    def test_range_select(self):
        """[Golden] 范围选择 [3:0]"""
        source = '''
module top(
    input wire [7:0] data,
    output wire [3:0] nibble
);
    assign nibble = data[3:0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nibble', 'top')
        
        driver_ids = [d.id for d in result.drivers]
        # 方案C: 位选择信息保留，驱动为 data[...] 而非 data
        self.assertTrue(
            any('data' in d for d in driver_ids),
            f"驱动应包含 data 信号，实际: {driver_ids}"
        )
    
    def test_reverse_range(self):
        """[Golden] 反向范围 [7:4]"""
        source = '''
module top(
    input wire [7:0] data,
    output wire [3:0] nibble
);
    assign nibble = data[7:4];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nibble', 'top')
        
        driver_ids = [d.id for d in result.drivers]
        # 方案C: 位选择信息保留，驱动为 data[...] 而非 data
        self.assertTrue(
            any('data' in d for d in driver_ids),
            f"驱动应包含 data 信号，实际: {driver_ids}"
        )
    
    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------
    
    def test_out_of_bounds(self):
        """[Boundary] 越界访问"""
        source = '''
module top(
    input wire [7:0] data,
    output wire out
);
    assign out = data[15];  // 越界
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        # 应该处理但不崩溃
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_negative_index(self):
        """[Boundary] 负数索引"""
        source = '''
module top(
    input wire [7:0] data,
    output wire out
);
    assign out = data[-1];  // 无效
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
    
    def test_vector_to_vector(self):
        """[Boundary] 向量到向量"""
        source = '''
module top(
    input wire [15:0] data,
    output wire [7:0] lo,
    output wire [7:0] hi
);
    assign lo = data[7:0];
    assign hi = data[15:8];
endmodule'''
        
        tracer = self._make_tracer(source)
        
        result_lo = tracer.trace_signal('lo', 'top')
        result_hi = tracer.trace_signal('hi', 'top')
        
        # 方案C: 位选择信息保留
        self.assertTrue(any('data' in d.id for d in result_lo.drivers))
        self.assertTrue(any('data' in d.id for d in result_hi.drivers))


if __name__ == '__main__':
    unittest.main()
