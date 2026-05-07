# test_sva_timing_enhanced.py - 增强 SVA 时序表达式金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
增强 SVA 时序表达式:
1. throughout
2. within
3. intersect
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.base import PyslangAdapter

class TestSVATimingEnhanced(unittest.TestCase):
    """增强 SVA 时序表达式测试"""
    
    def _make_tracer(self, source):
        tree = pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(trees={'test': tree})
    
    def _get_adapter(self, tree):
        class FP:
            def __init__(self, t): self.trees = t
        return PyslangAdapter(FP({'test': tree}))
    
    def test_throughout_sequence(self):
        """[Golden] throughout 序列
        
        RTL:
        sequence s1;
            @(posedge clk) a throughout b ##1 c;
        endsequence
        
        预期:
        - SequenceDeclaration 存在
        - ThroughoutSequenceExpr 存在
        """
        source = '''module top(input clk, logic a, b, c);
    sequence s1;
        @(posedge clk) a throughout b ##1 c;
    endsequence
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        members = list(root.members)
        seq = members[0]
        
        # 检查 seqExpr
        seq_expr = seq.seqExpr
        self.assertEqual(seq_expr.kind, pyslang.SyntaxKind.ClockingSequenceExpr)
        
        # 检查 ThroughoutSequenceExpr
        expr = seq_expr.expr
        self.assertEqual(expr.kind, pyslang.SyntaxKind.ThroughoutSequenceExpr)
    
    def test_within_sequence(self):
        """[Golden] within 序列
        
        RTL:
        sequence s2;
            @(posedge clk) a ##1 b within c ##1 d;
        endsequence
        
        预期:
        - SequenceDeclaration 存在
        - WithinSequenceExpr 存在
        """
        source = '''module top(input clk, logic a, b, c, d);
    sequence s2;
        @(posedge clk) a ##1 b within c ##1 d;
    endsequence
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        members = list(root.members)
        seq = members[0]
        
        # 检查 seqExpr
        seq_expr = seq.seqExpr
        self.assertEqual(seq_expr.kind, pyslang.SyntaxKind.ClockingSequenceExpr)
        
        # 检查 WithinSequenceExpr
        expr = seq_expr.expr
        self.assertEqual(expr.kind, pyslang.SyntaxKind.WithinSequenceExpr)
    
    def test_intersect_sequence(self):
        """[Golden] intersect 序列
        
        RTL:
        sequence s3;
            @(posedge clk) a intersect b;
        endsequence
        
        预期:
        - SequenceDeclaration 存在
        - IntersectSequenceExpr 存在
        """
        source = '''module top(input clk, logic a, b);
    sequence s3;
        @(posedge clk) a intersect b;
    endsequence
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root
        
        members = list(root.members)
        seq = members[0]
        
        # 检查 seqExpr
        seq_expr = seq.seqExpr
        self.assertEqual(seq_expr.kind, pyslang.SyntaxKind.ClockingSequenceExpr)
        
        # 检查 IntersectSequenceExpr
        expr = seq_expr.expr
        self.assertEqual(expr.kind, pyslang.SyntaxKind.IntersectSequenceExpr)

if __name__ == '__main__':
    unittest.main()
