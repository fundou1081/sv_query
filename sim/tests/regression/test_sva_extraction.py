# test_sva_extraction.py - SVA 结构化提取金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
#
# 使用 Semantic AST 提取 SVA 结构
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.sva_extractor import SVAExtractor
from trace.core.graph.sva_models import (
    SVASequenceNode, SVAPropertyNode, SVAAssertionNode, SVAGraph
)


def _extract(source):
    extractor = SVAExtractor({'test.sv': source})
    return extractor.extract()


class TestSequenceExtraction(unittest.TestCase):
    """Sequence 提取"""

    def test_simple_sequence(self):
        """[金标准] 简单 sequence

        sequence s1;
            @(posedge clk) a ##1 b;
        endsequence

        期望:
        - id: "top.s1"
        - signals: ["a", "b"]
        - timing_ops: ["##1"]
        - clock: "clk"
        """
        source = '''module top(input clk, logic a, b);
    sequence s1;
        @(posedge clk) a ##1 b;
    endsequence
endmodule'''
        sva = _extract(source)

        self.assertIn('top.s1', sva.sequences)
        seq = sva.sequences['top.s1']
        self.assertEqual(seq.name, 's1')
        self.assertIn('a', seq.signals)
        self.assertIn('b', seq.signals)
        self.assertIn('##1', seq.timing_ops)
        self.assertIn('clk', seq.clock)

    def test_sequence_with_range_delay(self):
        """[金标准] 带范围延迟的 sequence

        sequence s2;
            @(posedge clk) a ##[1:3] b;
        endsequence

        期望: timing_ops 包含 "##[1:3]"
        """
        source = '''module top(input clk, logic a, b);
    sequence s2;
        @(posedge clk) a ##[1:3] b;
    endsequence
endmodule'''
        sva = _extract(source)

        seq = sva.sequences.get('top.s2')
        self.assertIsNotNone(seq)
        self.assertTrue(any('##' in op for op in seq.timing_ops))


class TestPropertyExtraction(unittest.TestCase):
    """Property 提取"""

    def test_simple_implication(self):
        """[金标准] 简单蕴含

        property p1;
            @(posedge clk) a |-> b;
        endproperty

        期望:
        - id: "top.p1"
        - signals: ["a", "b"]
        - operators: ["|->"]
        - clock: "clk"
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
endmodule'''
        sva = _extract(source)

        self.assertIn('top.p1', sva.properties)
        prop = sva.properties['top.p1']
        self.assertEqual(prop.name, 'p1')
        self.assertIn('a', prop.signals)
        self.assertIn('b', prop.signals)
        self.assertIn('|->', prop.operators)

    def test_property_with_disable_iff(self):
        """[金标准] 带 disable iff 的 property

        property p2;
            @(posedge clk) disable iff (!rst_n) a |-> b;
        endproperty

        期望: disable_iff = "!rst_n"
        """
        source = '''module top(input clk, rst_n, logic a, b);
    property p2;
        @(posedge clk) disable iff (!rst_n) a |-> b;
    endproperty
endmodule'''
        sva = _extract(source)

        prop = sva.properties.get('top.p2')
        self.assertIsNotNone(prop)
        self.assertIn('rst_n', prop.disable_iff)

    def test_property_with_next_cycle(self):
        """[金标准] 下一周期蕴含

        property p3;
            @(posedge clk) a |=> b;
        endproperty

        期望: operators 包含 "|=>"
        """
        source = '''module top(input clk, logic a, b);
    property p3;
        @(posedge clk) a |=> b;
    endproperty
endmodule'''
        sva = _extract(source)

        prop = sva.properties.get('top.p3')
        self.assertIsNotNone(prop)
        self.assertIn('|=>', prop.operators)


class TestAssertionExtraction(unittest.TestCase):
    """Assertion 提取"""

    def test_assert_property(self):
        """[金标准] assert property

        assert property (p1) else $error("fail");

        期望:
        - kind: "assert"
        - property_ref: "top.p1"
        - message: 包含 "fail"
        """
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1) else $error("fail");
endmodule'''
        sva = _extract(source)

        asserts = [a for a in sva.assertions if a.kind == 'assert']
        self.assertGreaterEqual(len(asserts), 1)
        self.assertIn('p1', asserts[0].property_ref)

    def test_assume_property(self):
        """[金标准] assume property"""
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assume property (p1);
endmodule'''
        sva = _extract(source)

        assumes = [a for a in sva.assertions if a.kind == 'assume']
        self.assertGreaterEqual(len(assumes), 1)

    def test_cover_property(self):
        """[金标准] cover property"""
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    cover property (p1);
endmodule'''
        sva = _extract(source)

        covers = [a for a in sva.assertions if a.kind == 'cover']
        self.assertGreaterEqual(len(covers), 1)


class TestSignalRefIndex(unittest.TestCase):
    """信号关联索引"""

    def test_signal_ref_index(self):
        """[金标准] 信号关联索引

        sequence s1: a ##1 b
        property p1: a |-> b
        assert property (p1)

        期望:
        - signal_refs["a"] 包含 s1 和 p1
        - signal_refs["b"] 包含 s1 和 p1
        """
        source = '''module top(input clk, logic a, b);
    sequence s1;
        @(posedge clk) a ##1 b;
    endsequence
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1);
endmodule'''
        sva = _extract(source)

        self.assertIn('a', sva.signal_refs)
        self.assertIn('b', sva.signal_refs)
        # a 和 b 都应关联到 s1 和 p1
        a_refs = sva.signal_refs['a']
        self.assertTrue(any('s1' in r for r in a_refs),
            f"a 应关联到 s1, 实际: {a_refs}")

    def test_get_assertions_for_signal(self):
        """[金标准] 查询信号相关的 assertion"""
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1) else $error("fail");
endmodule'''
        sva = _extract(source)

        assertions = sva.get_assertions_for_signal('a')
        self.assertGreaterEqual(len(assertions), 1)


class TestClassSVA(unittest.TestCase):
    """Class 内的 SVA"""

    def test_sva_in_class(self):
        """[金标准] Class 内的 SVA

        pyslang 限制: ClassDeclaration 不暴露 PropertyDeclaration
        作为 class members。需要从 syntax 树手动提取。

        当前实现: 暂不支持 class 内的 SVA 提取。
        """
        source = '''class my_checker;
    logic clk;
    logic a, b;

    property p1;
        @(posedge clk) a |-> b;
    endproperty
endclass
module top; endmodule'''
        sva = _extract(source)

        # pyslang 限制: class 内的 property 不被识别
        # 记录为已知限制
        self.assertEqual(len(sva.properties), 0,
            "pyslang 限制: class 内 property 暂不支持")


class TestNoSVA(unittest.TestCase):
    """无 SVA 时返回空"""

    def test_no_sva(self):
        """[负面] 无 SVA 时返回空"""
        source = '''module top(input clk, logic [7:0] data);
    always_ff @(posedge clk) data <= data + 1;
endmodule'''
        sva = _extract(source)

        self.assertEqual(len(sva.sequences), 0)
        self.assertEqual(len(sva.properties), 0)
        self.assertEqual(len(sva.assertions), 0)


class TestOutputFormat(unittest.TestCase):
    """输出格式"""

    def test_dot_output(self):
        """[金标准] DOT 输出"""
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1);
endmodule'''
        sva = _extract(source)
        dot = sva.to_dot()
        self.assertIn('digraph', dot)
        self.assertIn('p1', dot)

    def test_mermaid_output(self):
        """[金标准] Mermaid 输出"""
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1);
endmodule'''
        sva = _extract(source)
        mermaid = sva.to_mermaid()
        self.assertIn('graph TD', mermaid)
        self.assertIn('p1', mermaid)


if __name__ == '__main__':
    unittest.main()
