#==============================================================================
# test_case_multi_branch_v2.py - case 多分支 Driver 提取
# Bug: case 内部多分支未正确提取
# 项目纪律: 金标准测试优先
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
        """[Golden] 简单 case - 2分支"""
        src = '''module top(input sel, a, b, output y);
            always_comb begin
                case (sel)
                    1'b0: y = a;
                    default: y = b;
                endcase
            end
        endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')
        
        # 期望: 2 drivers (a, b)
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')
    
    def test_case_3branch(self):
        """[Golden] 3分支 case"""
        src = '''module top(input [1:0] sel, a, b, c, output y);
            always_comb begin
                case (sel)
                    2'b00: y = a;
                    2'b01: y = b;
                    default: y = c;
                endcase
            end
        endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
        self.assertEqual(result.confidence, 'high')
    
    def test_casez(self):
        """[Golden] casez - 支持 don't care"""
        src = '''module top(input [2:0] sel, a, b, c, output y);
            always_comb begin
                casez (sel)
                    3'b00?: y = a;
                    3'b01?: y = b;
                    default: y = c;
                endcasez
            end
        endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)
    
    def test_casex(self):
        """[Golden] casex - 支持 x"""
        src = '''module top(input [2:0] sel, a, b, c, output y);
            always_comb begin
                casex (sel)
                    3'b00x: y = a;
                    3'b01x: y = b;
                    default: y = c;
                endcasex
            end
        endmodule'''
        tree = pyslang.SyntaxTree.fromText(src)
        tracer = UnifiedTracer(sources={'t.sv': source})
        result = tracer.trace_signal('y', 'top')
        
        self.assertGreaterEqual(len(result.drivers), 1)


if __name__ == '__main__':
    unittest.main()
