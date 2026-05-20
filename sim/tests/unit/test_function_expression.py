#==============================================================================
# test_function_expression.py - 函数内部表达式解析测试
#==============================================================================
# Req-6: 函数内部逻辑提取
#
# 金标准测试：验证函数体内部表达式能够完整展开
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind


class TestFunctionExpression(unittest.TestCase):
    """函数内部表达式解析测试"""
    
    def _make_tracer(self, source):
        return UnifiedTracer(sources={'test.sv': source})
    
    def test_function_call_drivers(self):
        """[金标准] 函数调用的驱动应包含函数参数
        
        assign out = gray_conv(in);
        
        期望:
        - in -> out (通过 gray_conv(in))
        """
        source = '''
module top(input wire [7:0] in, output wire [7:0] out);
    function [7:0] gray_conv(input [7:0] a);
        gray_conv = a;
    endfunction
    
    assign out = gray_conv(in);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        result = tracer.trace_signal('out', 'top')
        driver_ids = [d.id for d in result.drivers]
        
        # 应该追踪到 in
        self.assertTrue(
            any('in' in d for d in driver_ids),
            f"Expected 'in' in drivers, got {driver_ids}"
        )

    def test_binary_expression_in_function(self):
        """[金标准] 函数内二元表达式应完整展开
        
        gray_conv = {a[7], a[6:0] ^ a[7:1]}
        
        期望驱动链:
        - a[7] -> gray_conv (已实现)
        - a[6:0] -> gray_conv (待实现)
        - a[7:1] -> gray_conv (待实现)
        
        当前状态: ❌ 失败 (a[6:0] 未被追踪)
        """
        source = '''
module top(input wire [7:0] in, output wire [7:0] out);
    function [7:0] gray_conv(input [7:0] a);
        begin
            gray_conv = {a[7], a[6:0] ^ a[7:1]};
        end
    endfunction
    
    assign out = gray_conv(in);
endmodule'''
        
        tracer = self._make_tracer(source)
        tracer.build_graph()
        graph = tracer.get_graph()
        
        result = tracer.trace_signal('out', 'top')
        driver_ids = [d.id for d in result.drivers]
        
        # 金标准: a[7], a[6:0], a[7:1] 都应该在驱动链中
        has_a_7 = any('a[7]' in d for d in driver_ids)
        has_a_6_0 = any('a[6:0]' in d for d in driver_ids)
        has_a_7_1 = any('a[7:1]' in d for d in driver_ids)
        
        print(f"Drivers: {driver_ids}")
        print(f"a[7]: {has_a_7}, a[6:0]: {has_a_6_0}, a[7:1]: {has_a_7_1}")
        
        # 验证 a[7] 被追踪 (已实现)
        self.assertTrue(has_a_7, f"a[7] should be tracked, got {driver_ids}")
        
        # 验证 a[7:1] 被追踪 (已实现)
        self.assertTrue(has_a_7_1, f"a[7:1] should be tracked, got {driver_ids}")
        
        # 验证 a[6:0] 被追踪 (待实现 - 当前失败)
        # 按照铁律17，需要强断言
        self.assertTrue(
            has_a_6_0,
            f"❌ 金标准失败: a[6:0] 未被追踪. Drivers: {driver_ids}"
        )


if __name__ == '__main__':
    unittest.main()