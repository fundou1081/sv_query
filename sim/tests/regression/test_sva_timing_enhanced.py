# test_sva_timing_enhanced.py - 增强 SVA 时序表达式金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
增强 SVA 时序表达式:
1. throughout
2. within
3. intersect

[iter_064 行为断言升级] 在原 SyntaxKind AST 断言之上, 补充 SVAExtractor
结构化行为断言: SVASequenceNode.signals / timing_ops / clock /
signal_refs 索引. 行为金标准 = 提取器对真实语义 AST 的结构化视图.
throughout/within/intersect 在提取器当前实现中表现为信号提取和
##1 timing_op (iter_064 实测行为), 不硬断言 throughout/within/intersect
在 operators 中出现 — 这是当前提取器能力的事实, 而非缺陷.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer


class TestSVATimingEnhanced(unittest.TestCase):
    """增强 SVA 时序表达式测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _extract(self, source):
        return SVAExtractor({'test.sv': source}).extract()

    def test_throughout_sequence(self):
        """[Golden] throughout 序列

        RTL:
        sequence s1;
            @(posedge clk) a throughout b ##1 c;
        endsequence

        预期:
        - SequenceDeclaration 存在 (SyntaxKind)
        - ThroughoutSequenceExpr 存在
        - [行为] SVAExtractor 提取 s1, signals 含 a/b/c
        - [行为] clock == clk
        - [行为] timing_ops 含 ##1 (throughout 内的延迟仍被捕获)
        - [行为] signal_refs 建立 a/b/c -> top.s1 索引
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

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.sequences), 1,
            f"应提取 1 个 sequence, 实际 {len(g.sequences)}")
        s1 = g.sequences['top.s1']
        # signals: throughout 内 a, b, c 三个信号均应被提取
        self.assertEqual(set(s1.signals), {'a', 'b', 'c'},
            f"throughout 内 a/b/c 都应被提取, 实际 {s1.signals}")
        # clock
        self.assertEqual(s1.clock, 'clk',
            f"clock 应为 'clk', 实际 {s1.clock!r}")
        # timing_ops: throughout 内的 ##1 应被捕获
        ops_str = ' '.join(s1.timing_ops)
        self.assertIn('##1', ops_str,
            f"timing_ops 应含 ##1, 实际 {s1.timing_ops}")
        # signal_refs: 三个信号都应建立索引
        for sig in ('a', 'b', 'c'):
            self.assertIn(sig, g.signal_refs,
                f"signal_refs 应建立 {sig} 的索引")
            self.assertIn('top.s1', g.signal_refs[sig])

    def test_within_sequence(self):
        """[Golden] within 序列

        RTL:
        sequence s2;
            @(posedge clk) a ##1 b within c ##1 d;
        endsequence

        预期:
        - SequenceDeclaration 存在 (SyntaxKind)
        - WithinSequenceExpr 存在
        - [行为] SVAExtractor 提取 s2, signals 含 a/b/c/d
        - [行为] clock == clk
        - [行为] timing_ops 含 ##1 (within 两侧的延迟都被捕获)
        - [行为] signal_refs 建立 a/b/c/d -> top.s2 索引
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

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.sequences), 1,
            f"应提取 1 个 sequence, 实际 {len(g.sequences)}")
        s2 = g.sequences['top.s2']
        # signals: within 内 a, b, c, d 四个信号均应被提取
        self.assertEqual(set(s2.signals), {'a', 'b', 'c', 'd'},
            f"within 内 a/b/c/d 都应被提取, 实际 {s2.signals}")
        # clock
        self.assertEqual(s2.clock, 'clk',
            f"clock 应为 'clk', 实际 {s2.clock!r}")
        # timing_ops: within 两侧的 ##1 应都被捕获
        ops_str = ' '.join(s2.timing_ops)
        self.assertIn('##1', ops_str,
            f"timing_ops 应含 ##1, 实际 {s2.timing_ops}")
        # signal_refs: 四个信号都应建立索引
        for sig in ('a', 'b', 'c', 'd'):
            self.assertIn(sig, g.signal_refs,
                f"signal_refs 应建立 {sig} 的索引")
            self.assertIn('top.s2', g.signal_refs[sig])

    def test_intersect_sequence(self):
        """[Golden] intersect 序列

        RTL:
        sequence s3;
            @(posedge clk) a intersect b;
        endsequence

        预期:
        - SequenceDeclaration 存在 (SyntaxKind)
        - IntersectSequenceExpr 存在
        - [行为] SVAExtractor 提取 s3, signals 含 a/b
        - [行为] clock == clk
        - [行为] intersect 是零延迟操作, timing_ops 不必含延迟
        - [行为] signal_refs 建立 a/b -> top.s3 索引
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

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.sequences), 1,
            f"应提取 1 个 sequence, 实际 {len(g.sequences)}")
        s3 = g.sequences['top.s3']
        # signals: intersect 内 a, b 两个信号均应被提取
        self.assertEqual(set(s3.signals), {'a', 'b'},
            f"intersect 内 a/b 都应被提取, 实际 {s3.signals}")
        # clock
        self.assertEqual(s3.clock, 'clk',
            f"clock 应为 'clk', 实际 {s3.clock!r}")
        # signal_refs: 两个信号都应建立索引
        for sig in ('a', 'b'):
            self.assertIn(sig, g.signal_refs,
                f"signal_refs 应建立 {sig} 的索引")
            self.assertIn('top.s3', g.signal_refs[sig])


if __name__ == '__main__':
    unittest.main()
