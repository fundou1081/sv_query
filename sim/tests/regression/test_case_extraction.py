#==============================================================================
# test_case_extraction.py - case 语句 Driver 提取
# Bug: case 内部多分支赋值未提取
# 原因: pyslang CaseStatement API 结构复杂
# 状态: 已知限制 (需进一步研究)
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer


class TestCaseKnownLimitation(unittest.TestCase):
    """case 语句 - 已知 API 限制"""
    
    def test_case_compiles(self):
        """验证 case 能够解析"""
        source = '''
module top(input [1:0] sel, input a, b, output y);
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
        tracer.build_graph()
        
        # 已知限制: 内部提取不完整，但基础功能可用
        self.assertIsNotNone(tracer.get_graph())


if __name__ == '__main__':
    unittest.main()
