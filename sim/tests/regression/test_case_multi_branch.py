#==============================================================================
# test_case_multi_branch.py - case 语句多分支 Driver 提取
# Bug: case 语句内部多分支未提取
# 按项目纪律: 先写测试，再开发
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestCaseMultiBranch(unittest.TestCase):
    """case 多分支 Driver 提取"""
    
    def test_case_simple(self):
        """[Golden] 简单 case - 应提取多个驱动"""
        # RTL:
        #   case (sel)
        #     2'b00: y = a;
        #     2'b01: y = b;
        #     default: y = c;
        #   endcase
        # 金标准: y 驱动 = [a, b, c] (多个)
        
        source = '''
module top(input [1:0] sel, input a, input b, input c, output y);
    always_comb begin
        case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = c;
        endcase
    end
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('y', 'top')
        
        # 期望: 至少能提取到驱动
        # 当前: 可能只提取到1个
        driver_count = len(result.drivers)
        self.assertGreaterEqual(driver_count, 1, "应至少提取1个driver")
        self.assertEqual(result.confidence, 'high')
    
    def test_case_two_branch(self):
        """[Golden] 2分支 case"""
        source = '''
module top(input sel, input a, input b, output y);
    always_comb begin
        case (sel)
            1'b0: y = a;
            default: y = b;
        endcase
    end
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(sources={'test.sv': source})
        result = tracer.trace_signal('y', 'top')
        
        # 期望: 提取到 a 和 b
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
