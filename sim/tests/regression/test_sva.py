# test_sva.py - SVA 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
"""
SVA 语法覆盖:
1. sequence 声明
2. property 声明
3. assert property
4. assume property
5. cover property

[iter_064 行为断言升级] 在原 SyntaxKind AST 断言之上, 补充 SVAExtractor
结构化行为断言 (properties / sequences / assertions / signal_refs /
get_assertions_for_signal). 行为金标准 = 提取器对真实语义 AST 的结构化
视图 — 比 SyntaxKind 严格, 因为它验证"信号是否被提取、操作符是否被记录、
signal_refs 是否建立、property_ref 链路是否正确"。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer


class TestSVA(unittest.TestCase):
    """SVA 支持测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _extract(self, source):
        return SVAExtractor({'test.sv': source}).extract()

    def test_sequence_declaration(self):
        """[Golden] sequence 声明

        RTL:
        module top(input clk, logic a, b);
            sequence s1;
                @(posedge clk) a ##1 b;
            endsequence
        endmodule

        预期:
        - SequenceDeclaration 存在 (SyntaxKind)
        - 名称为 s1
        - [行为] SVAExtractor 提取 s1 到 graph.sequences
        - [行为] sequence 含信号 a, b
        - [行为] sequence timing_ops 含 ##1
        - [行为] sequence clock == clk
        - [行为] signal_refs 建立 a/b -> top.s1 索引
        """
        source = '''module top(input clk, logic a, b);
    sequence s1;
        @(posedge clk) a ##1 b;
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
        self.assertEqual(str(seq_decl.name).strip(), 's1')

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.sequences), 1,
            f"应提取 1 个 sequence, 实际 {len(g.sequences)}: {list(g.sequences)}")
        seq_id = 'top.s1'  # module.top → sequence id 格式
        self.assertIn(seq_id, g.sequences)
        s1 = g.sequences[seq_id]
        self.assertEqual(s1.name, 's1')
        self.assertEqual(s1.clock, 'clk', "clock 应被提取")
        # timing_ops: ##1 a → ##1 b 链路中 ##1 出现 2 次 (iter 实测行为)
        self.assertTrue(any('##1' in op for op in s1.timing_ops),
            f"timing_ops 应含 ##1, 实际 {s1.timing_ops}")
        # signals: a, b 均被提取
        self.assertIn('a', s1.signals, f"a 应被提取: {s1.signals}")
        self.assertIn('b', s1.signals, f"b 应被提取: {s1.signals}")
        # signal_refs 索引: a → [top.s1]
        self.assertIn('a', g.signal_refs, "signal_refs 应建立 a 的索引")
        self.assertIn('top.s1', g.signal_refs['a'])

    def test_property_declaration(self):
        """[Golden] property 声明

        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) disable iff (1'b0) a |-> b;
            endproperty
        endmodule

        预期:
        - PropertyDeclaration 存在 (SyntaxKind)
        - 名称为 p1
        - [行为] SVAExtractor 提取 p1 到 graph.properties
        - [行为] property 含 operators |->, signals a/b, clock clk, disable_iff
        - [行为] signal_refs 建立 a/b -> top.p1 索引
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) disable iff (1'b0) a |-> b;
    endproperty
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 PropertyDeclaration
        prop_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.PropertyDeclaration:
                prop_decl = m
                break

        self.assertIsNotNone(prop_decl, "PropertyDeclaration not found")
        self.assertEqual(str(prop_decl.name).strip(), 'p1')

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.properties), 1,
            f"应提取 1 个 property, 实际 {len(g.properties)}: {list(g.properties)}")
        p1 = g.properties['top.p1']
        self.assertEqual(p1.name, 'p1')
        self.assertEqual(p1.clock, 'clk')
        # operators: |-> 应被记录
        self.assertIn('|->', p1.operators,
            f"|-> 应在 operators 中, 实际 {p1.operators}")
        # disable_iff: 非空 (实际含完整 disable iff 文本)
        self.assertTrue(p1.disable_iff,
            f"disable_iff 应被提取, 实际空: {p1.disable_iff!r}")
        # signals
        self.assertIn('a', p1.signals)
        self.assertIn('b', p1.signals)
        # signal_refs
        self.assertIn('a', g.signal_refs)
        self.assertIn('top.p1', g.signal_refs['a'])

    def test_assert_property(self):
        """[Golden] assert property

        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) a |-> b;
            endproperty

            assert property (p1) else $error("fail");
        endmodule

        预期:
        - ConcurrentAssertionMember 存在 (SyntaxKind)
        - AssertPropertyStatement 存在
        - [行为] SVAExtractor 提取 1 个 property + 1 个 assertion
        - [行为] assertion.kind == 'assert', property_ref == 'top.p1'
        - [行为] assertion message == 'fail'
        - [行为] get_assertions_for_signal('a') 返回关联 assert
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty

    assert property (p1) else $error("fail");
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 ConcurrentAssertionMember
        assertion = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.ConcurrentAssertionMember:
                assertion = m
                break

        self.assertIsNotNone(assertion, "ConcurrentAssertionMember not found")

        # 检查 statement
        stmt = assertion.statement
        self.assertEqual(stmt.kind, pyslang.SyntaxKind.AssertPropertyStatement)

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.properties), 1)
        self.assertEqual(len(g.assertions), 1,
            f"应提取 1 个 assertion, 实际 {len(g.assertions)}: {g.assertions}")
        a = g.assertions[0]
        self.assertEqual(a.kind, 'assert',
            f"assertion.kind 应为 'assert', 实际 {a.kind!r}")
        self.assertEqual(a.property_ref, 'top.p1',
            f"property_ref 应为 'top.p1', 实际 {a.property_ref!r}")
        # else $error("fail") → message == 'fail'
        self.assertEqual(a.message, 'fail',
            f"else $error 消息应被提取, 实际 {a.message!r}")
        # signal_refs: a 应能反查到关联的 assert
        self.assertIn('a', g.signal_refs)
        a_assertions = g.get_assertions_for_signal('a')
        self.assertTrue(len(a_assertions) >= 1,
            f"信号 'a' 应能反查到至少 1 个 assertion, 实际 {a_assertions}")
        # 反查结果中应含 assert kind
        kinds = {x.kind for x in a_assertions}
        self.assertIn('assert', kinds,
            f"信号 'a' 应关联到 assert 类型 assertion: {kinds}")

    def test_assume_property(self):
        """[Golden] assume property

        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) a |-> b;
            endproperty

            assume property (p1);
        endmodule

        预期:
        - AssumePropertyStatement 存在 (SyntaxKind)
        - [行为] SVAExtractor 提取 1 个 property + 1 个 assertion (kind=assume)
        - [行为] assertion.property_ref == 'top.p1'
        - [行为] get_assertions_for_signal('b') 返回关联 assume
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty

    assume property (p1);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 ConcurrentAssertionMember
        assertion = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.ConcurrentAssertionMember:
                assertion = m
                break

        self.assertIsNotNone(assertion, "ConcurrentAssertionMember not found")

        # 检查 statement
        stmt = assertion.statement
        self.assertEqual(stmt.kind, pyslang.SyntaxKind.AssumePropertyStatement)

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.properties), 1)
        self.assertEqual(len(g.assertions), 1,
            f"应提取 1 个 assertion, 实际 {len(g.assertions)}: {g.assertions}")
        a = g.assertions[0]
        self.assertEqual(a.kind, 'assume',
            f"assertion.kind 应为 'assume', 实际 {a.kind!r}")
        self.assertEqual(a.property_ref, 'top.p1',
            f"property_ref 应为 'top.p1', 实际 {a.property_ref!r}")
        # 信号 'b' 在 property 中, 反查应能见到关联的 assume
        b_assertions = g.get_assertions_for_signal('b')
        kinds = {x.kind for x in b_assertions}
        self.assertIn('assume', kinds,
            f"信号 'b' 应关联到 assume: {kinds}")

    def test_cover_property(self):
        """[Golden] cover property

        RTL:
        module top(input clk, logic a, b);
            property p1;
                @(posedge clk) a |-> b;
            endproperty

            cover property (p1);
        endmodule

        预期:
        - CoverPropertyStatement 存在 (SyntaxKind)
        - [行为] SVAExtractor 提取 1 个 assertion (kind=cover)
        - [行为] assertion.property_ref == 'top.p1'
        - [行为] 提取器对 cover 不要求 else 分支 → message 为空
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty

    cover property (p1);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 ConcurrentAssertionMember
        assertion = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.ConcurrentAssertionMember:
                assertion = m
                break

        self.assertIsNotNone(assertion, "ConcurrentAssertionMember not found")

        # 检查 statement
        stmt = assertion.statement
        self.assertEqual(stmt.kind, pyslang.SyntaxKind.CoverPropertyStatement)

        # === [iter_064 行为断言] SVAExtractor 结构化视图 ===
        g = self._extract(source)
        self.assertEqual(g.errors, [], f"提取器不应有错误: {g.errors}")
        self.assertEqual(len(g.properties), 1)
        self.assertEqual(len(g.assertions), 1,
            f"应提取 1 个 assertion, 实际 {len(g.assertions)}: {g.assertions}")
        a = g.assertions[0]
        self.assertEqual(a.kind, 'cover',
            f"assertion.kind 应为 'cover', 实际 {a.kind!r}")
        self.assertEqual(a.property_ref, 'top.p1',
            f"property_ref 应为 'top.p1', 实际 {a.property_ref!r}")
        # cover 无 else 分支 → message 应为空
        self.assertEqual(a.message, '',
            f"cover 无 else 分支, message 应为空, 实际 {a.message!r}")


if __name__ == '__main__':
    unittest.main()
