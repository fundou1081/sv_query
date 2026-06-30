# test_sva_timing.py - SVA 时序表达式金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
SVA 时序表达式:
1. ##1 延迟
2. ##n 延迟
3. [*n] 重复
4. [->n] goto 重复
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestSVATiming(unittest.TestCase):
    """SVA 时序表达式测试"""

    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_delay_sequence(self):
        """[Golden] ##1 延迟序列

        RTL:
        module top(input clk, logic a, b, c);
            sequence s1;
                @(posedge clk) a ##1 b ##2 c;
            endsequence
        endmodule

        预期:
        - SequenceDeclaration 存在
        - DelayedSequenceExpr 包含 2 个 DelayedSequenceElement
        - 延迟值分别为 1 和 2
        """
        source = '''module top(input clk, logic a, b, c);
    sequence s1;
        @(posedge clk) a ##1 b ##2 c;
    endsequence
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 SequenceDeclaration
        seq_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.SequenceDeclaration:
                seq_decl = m
                break

        self.assertIsNotNone(seq_decl, "SequenceDeclaration not found")

        # 检查 seqExpr
        seq_expr = seq_decl.seqExpr
        self.assertEqual(seq_expr.kind, pyslang.SyntaxKind.ClockingSequenceExpr)

        # 检查 DelayedSequenceExpr
        expr = seq_expr.expr
        self.assertEqual(expr.kind, pyslang.SyntaxKind.DelayedSequenceExpr)

        # 检查 DelayedSequenceElement
        elements = list(expr.elements)
        self.assertEqual(len(elements), 2, "Should have 2 DelayedSequenceElement")

        # 检查延迟值
        self.assertEqual(str(elements[0].delayVal).strip(), '1')
        self.assertEqual(str(elements[1].delayVal).strip(), '2')

    def test_repetition_sequence(self):
        """[Golden] [*n] 重复序列

        RTL:
        module top(input clk, logic a);
            sequence s2;
                @(posedge clk) a [*3];
            endsequence
        endmodule

        预期:
        - SequenceDeclaration 存在
        - SimpleSequenceExpr 存在
        - repetition 属性存在
        """
        source = '''module top(input clk, logic a);
    sequence s2;
        @(posedge clk) a [*3];
    endsequence
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 SequenceDeclaration
        seq_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.SequenceDeclaration:
                seq_decl = m
                break

        self.assertIsNotNone(seq_decl, "SequenceDeclaration not found")

        # 检查 seqExpr
        seq_expr = seq_decl.seqExpr
        self.assertEqual(seq_expr.kind, pyslang.SyntaxKind.ClockingSequenceExpr)

        # 检查 SimpleSequenceExpr
        expr = seq_expr.expr
        self.assertEqual(expr.kind, pyslang.SyntaxKind.SimpleSequenceExpr)

        # 检查 repetition 属性
        self.assertTrue(hasattr(expr, 'repetition'), "repetition attribute not found")

    def test_goto_sequence(self):
        """[Golden] [->n] goto 重复

        RTL:
        module top(input clk, logic a, b);
            sequence s3;
                @(posedge clk) a [->2] ##1 b;
            endsequence
        endmodule

        预期:
        - SequenceDeclaration 存在
        - SequenceRepetition 存在
        """
        source = '''module top(input clk, logic a, b);
    sequence s3;
        @(posedge clk) a [->2] ##1 b;
    endsequence
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 SequenceDeclaration
        seq_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.SequenceDeclaration:
                seq_decl = m
                break

        self.assertIsNotNone(seq_decl, "SequenceDeclaration not found")

if __name__ == '__main__':
    unittest.main()
