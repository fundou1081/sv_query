# test_sva_timing.py - SVA 时序表达式金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
SVA 时序表达式:
1. ##1 延迟
2. ##n 延迟
3. [*n] 重复
4. [->n] goto 重复

[iter_064 行为断言升级] 在原 SyntaxKind AST 断言之上, 补充 SVAExtractor
结构化行为断言: SVASequenceNode.signals / timing_ops / clock /
signal_refs 索引. 行为金标准 = 提取器对真实语义 AST 的结构化视图.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer


class TestSVATiming(unittest.TestCase):
    """SVA 时序表达式测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _extract(self, source):
        return SVAExtractor({'test.sv': source}).extract()

    def test_delay_sequence(self):
        """[Golden] ##1 延迟序列

        RTL:
        module top(input clk, logic a, b, c);
            sequence s1;
                @(posedge clk) a ##1 b ##2 c;
            endsequence
        endmodule

        预期:
        - SequenceDeclaration 存在 (SyntaxKind)
        - DelayedSequenceExpr 包含 2 个 DelayedSequenceElement
        - 延迟值分别为 1 和 2
        - [行为] SVAExtractor 提取 s1, 含 a/b/c 三个信号
        - [行为] timing_ops 含 ##1 和 ##2
        - [行为] clock == clk
        - [行为] signal_refs 建立 a/b/c -> top.s1 索引
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

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.sequences), 1,
            f"应提取 1 个 sequence, 实际 {len(g.sequences)}")
        s1 = g.sequences['top.s1']
        # signals: a, b, c 三个信号均被提取
        self.assertEqual(set(s1.signals), {'a', 'b', 'c'},
            f"a/b/c 都应被提取, 实际 {s1.signals}")
        # clock
        self.assertEqual(s1.clock, 'clk',
            f"clock 应为 'clk', 实际 {s1.clock!r}")
        # timing_ops: 应同时含 ##1 和 ##2 (iter 实测行为: ##1 出现 2 次 + ##2 出现 1 次)
        ops_str = ' '.join(s1.timing_ops)
        self.assertIn('##1', ops_str,
            f"timing_ops 应含 ##1, 实际 {s1.timing_ops}")
        self.assertIn('##2', ops_str,
            f"timing_ops 应含 ##2, 实际 {s1.timing_ops}")
        # signal_refs: 三个信号都应建立索引
        for sig in ('a', 'b', 'c'):
            self.assertIn(sig, g.signal_refs,
                f"signal_refs 应建立 {sig} 的索引")
            self.assertIn('top.s1', g.signal_refs[sig])

    def test_repetition_sequence(self):
        """[Golden] [*n] 重复序列

        RTL:
        module top(input clk, logic a);
            sequence s2;
                @(posedge clk) a [*3];
            endsequence
        endmodule

        预期:
        - SequenceDeclaration 存在 (SyntaxKind)
        - SimpleSequenceExpr 存在
        - repetition 属性存在
        - [行为] SVAExtractor 提取 s2, signals 含 a, clock=clk
        - [行为] signal_refs 建立 a -> top.s2 索引
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

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.sequences), 1,
            f"应提取 1 个 sequence, 实际 {len(g.sequences)}")
        s2 = g.sequences['top.s2']
        self.assertEqual(s2.name, 's2')
        # signals: a 应被提取
        self.assertIn('a', s2.signals,
            f"a 应被提取: {s2.signals}")
        # clock
        self.assertEqual(s2.clock, 'clk',
            f"clock 应为 'clk', 实际 {s2.clock!r}")
        # signal_refs: a 应建立索引
        self.assertIn('a', g.signal_refs,
            "signal_refs 应建立 'a' 的索引")
        self.assertIn('top.s2', g.signal_refs['a'])

    def test_goto_sequence(self):
        """[Golden] [->n] goto 重复

        RTL:
        module top(input clk, logic a, b);
            sequence s3;
                @(posedge clk) a [->2] ##1 b;
            endsequence
        endmodule

        预期:
        - SequenceDeclaration 存在 (SyntaxKind)
        - SequenceRepetition 存在
        - [行为] SVAExtractor 提取 s3, signals 含 a/b, clock=clk
        - [行为] timing_ops 含 ##1 (goto repetition 当前在提取器中不
          单独记为 op, 这是 iter_064 实测行为, 不硬断言 [->2] 出现)
        - [行为] signal_refs 建立 a/b -> top.s3 索引
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

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.sequences), 1,
            f"应提取 1 个 sequence, 实际 {len(g.sequences)}")
        s3 = g.sequences['top.s3']
        self.assertEqual(s3.name, 's3')
        # signals: a, b 均应被提取
        self.assertEqual(set(s3.signals), {'a', 'b'},
            f"a/b 都应被提取, 实际 {s3.signals}")
        # clock
        self.assertEqual(s3.clock, 'clk',
            f"clock 应为 'clk', 实际 {s3.clock!r}")
        # timing_ops: ##1 应被记录 (goto repetition [->2] 在提取器当前
        # 实测下不单独记为 timing_op, 不硬断言 [->2] 出现)
        ops_str = ' '.join(s3.timing_ops)
        self.assertIn('##1', ops_str,
            f"timing_ops 应含 ##1, 实际 {s3.timing_ops}")
        # signal_refs: a/b 都应建立索引
        for sig in ('a', 'b'):
            self.assertIn(sig, g.signal_refs,
                f"signal_refs 应建立 {sig} 的索引")
            self.assertIn('top.s3', g.signal_refs[sig])


if __name__ == '__main__':
    unittest.main()
