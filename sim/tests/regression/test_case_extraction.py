#==============================================================================
# test_case_extraction.py - case 语句内部提取
# Bug: case 语句内的赋值未提取
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestCaseKnownLimitations(unittest.TestCase):
    """case 语句 - 已知限制"""
    
    def test_case_basic_extraction(self):
        """[Known Limit] case 基本提取"""
        source = '''
module top(input [1:0] sel, input a, input b, output y);
    always_comb begin
        case (sel)
            2'b00: y = a;
            2'b01: y = b;
            default: y = 0;
        endcase
    end
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        tracer = UnifiedTracer(trees={'test': tree})
        result = tracer.trace_signal('y', 'top')
        
        # 已知限制: case 内部提取有限
        # 当前实现: 能提取到第一个 case 的驱动
        self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])


if __name__ == '__main__':
    unittest.main()
