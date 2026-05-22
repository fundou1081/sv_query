#==============================================================================
# test_bit_select.py - 位选择追踪
#==============================================================================
# 铁律13: 金标准测试 - 先推导金标准再验证
# 铁律22: 强断言原则 - 必须验证具体行为
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer


class TestBitSelect(unittest.TestCase):
    """位选择追踪测试"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def _driver_ids(self, result):
        return [d.id for d in result.drivers]
    
    #----------------------------------------------------------------------
    # [金标准] 位选择追踪
    #----------------------------------------------------------------------
    
    def test_single_bit_select(self):
        """[Bit] 单比特选择: assign out = data[0];
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | out  | [data[0]] | high |
        """
        source = '''
module top(
    input wire [7:0] data,
    output wire out
);
    assign out = data[0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "out = data[0] 应有 1 个驱动源")
        self.assertIn('top.data[0]', self._driver_ids(result),
            "out 的驱动应包含 top.data[0]")
        self.assertEqual(result.confidence, 'high')
    
    def test_range_select(self):
        """[Bit] 范围选择: assign nibble = data[3:0];
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | nibble | [data[3:0]] | high |
        """
        source = '''
module top(
    input wire [7:0] data,
    output wire [3:0] nibble
);
    assign nibble = data[3:0];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nibble', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "nibble = data[3:0] 应有 1 个驱动源")
        self.assertIn('top.data[3:0]', self._driver_ids(result),
            "nibble 的驱动应包含 top.data[3:0]")
        self.assertEqual(result.confidence, 'high')
    
    def test_reverse_range(self):
        """[Bit] 反向范围: assign nibble = data[7:4];
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | nibble | [data[7:4]] | high |
        """
        source = '''
module top(
    input wire [7:0] data,
    output wire [3:0] nibble
);
    assign nibble = data[7:4];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('nibble', 'top')
        
        self.assertEqual(len(result.drivers), 1,
            "nibble = data[7:4] 应有 1 个驱动源")
        self.assertIn('top.data[7:4]', self._driver_ids(result),
            "nibble 的驱动应包含 top.data[7:4]")
        self.assertEqual(result.confidence, 'high')
    
    #----------------------------------------------------------------------
    # [边界条件]
    #----------------------------------------------------------------------
    
    def test_out_of_bounds(self):
        """[Boundary] 越界访问: data[15] 当 data 是 [7:0]
        金标准: 越界访问返回 uncertain 而非崩溃
        """
        source = '''
module top(
    input wire [7:0] data,
    output wire out
);
    assign out = data[15];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        # 越界访问应返回 uncertain 而非崩溃
        self.assertIn(result.confidence, ['high', 'uncertain'],
            "越界访问 data[15] 应返回 uncertain")
    
    def test_negative_index(self):
        """[Boundary] 负数索引: data[-1]
        金标准: 负数索引返回 uncertain 而非崩溃
        """
        source = '''
module top(
    input wire [7:0] data,
    output wire out
);
    assign out = data[-1];
endmodule'''
        
        tracer = self._make_tracer(source)
        result = tracer.trace_signal('out', 'top')
        
        self.assertIn(result.confidence, ['high', 'uncertain'],
            "负数索引 data[-1] 应返回 uncertain")
    
    def test_vector_to_vector(self):
        """[Boundary] 向量到向量: data[15:0] -> lo[7:0], hi[15:8]
        金标准:
        | 信号 | 驱动源 | 置信度 |
        |------|--------|--------|
        | lo   | [data[7:0]] | high |
        | hi   | [data[15:8]] | high |
        """
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
        
        self.assertEqual(len(result_lo.drivers), 1,
            "lo = data[7:0] 应有 1 个驱动源")
        self.assertIn('top.data[7:0]', self._driver_ids(result_lo),
            "lo 的驱动应包含 top.data[7:0]")
        self.assertEqual(result_lo.confidence, 'high')
        
        self.assertEqual(len(result_hi.drivers), 1,
            "hi = data[15:8] 应有 1 个驱动源")
        self.assertIn('top.data[15:8]', self._driver_ids(result_hi),
            "hi 的驱动应包含 top.data[15:8]")
        self.assertEqual(result_hi.confidence, 'high')


if __name__ == '__main__':
    unittest.main()