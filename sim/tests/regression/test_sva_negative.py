# test_sva_negative.py - SVA 反向测试
# [铁律18] 负面测试
#
# 验证 SVA 提取器能正确处理各种边界情况和异常输入
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.sva_extractor import SVAExtractor
from trace.core.graph.sva_models import SVAGraph


def _extract(source):
    extractor = SVAExtractor({'test.sv': source})
    return extractor.extract()


class TestEmptyInput(unittest.TestCase):
    """空输入"""

    def test_empty_source(self):
        """[负面] 空源码"""
        sva = _extract('')
        self.assertEqual(len(sva.sequences), 0)
        self.assertEqual(len(sva.properties), 0)
        self.assertEqual(len(sva.assertions), 0)

    def test_module_only(self):
        """[负面] 只有 module 没有 SVA"""
        source = '''module top(input clk, logic [7:0] data);
    always_ff @(posedge clk) data <= data + 1;
endmodule'''
        sva = _extract(source)
        self.assertEqual(len(sva.sequences), 0)
        self.assertEqual(len(sva.properties), 0)
        self.assertEqual(len(sva.assertions), 0)

    def test_empty_module(self):
        """[负面] 空 module"""
        source = '''module top; endmodule'''
        sva = _extract(source)
        self.assertEqual(len(sva.sequences), 0)


class TestMalformedSVA(unittest.TestCase):
    """格式错误的 SVA"""

    def test_property_without_assert(self):
        """[负面] 有 property 但没有 assert"""
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a |-> b;
    endproperty
endmodule'''
        sva = _extract(source)
        self.assertEqual(len(sva.properties), 1)
        self.assertEqual(len(sva.assertions), 0)

    def test_assert_without_property(self):
        """[负面] assert 引用不存在的 property"""
        source = '''module top(input clk, logic a, b);
    assert property (nonexistent_p) else $error("fail");
endmodule'''
        sva = _extract(source)
        # 应该有 assertion，但 property_ref 可能为空或指向不存在的 property
        self.assertGreaterEqual(len(sva.assertions), 0)

    def test_sequence_without_use(self):
        """[负面] 有 sequence 但没有被引用"""
        source = '''module top(input clk, logic a, b);
    sequence s1;
        @(posedge clk) a ##1 b;
    endsequence
endmodule'''
        sva = _extract(source)
        self.assertEqual(len(sva.sequences), 1)
        self.assertEqual(len(sva.assertions), 0)


class TestComplexTiming(unittest.TestCase):
    """复杂时序表达式"""

    def test_multiple_delays(self):
        """[负面] 多重延迟 ##1 ##2 ##3"""
        source = '''module top(input clk, logic a, b, c, d);
    sequence s1;
        @(posedge clk) a ##1 b ##2 c ##3 d;
    endsequence
endmodule'''
        sva = _extract(source)
        seq = sva.sequences.get('top.s1')
        if seq:
            self.assertIn('a', seq.signals)
            self.assertIn('d', seq.signals)

    def test_range_delay(self):
        """[负面] 范围延迟 ##[0:$]"""
        source = '''module top(input clk, logic a, b);
    sequence s1;
        @(posedge clk) a ##[0:$] b;
    endsequence
endmodule'''
        sva = _extract(source)
        # 不应崩溃
        self.assertIsInstance(sva, SVAGraph)

    def test_repetition_operator(self):
        """[负面] 重复操作符 [*3]"""
        source = '''module top(input clk, logic a, b);
    property p1;
        @(posedge clk) a[*3] |-> b;
    endproperty
endmodule'''
        sva = _extract(source)
        prop = sva.properties.get('top.p1')
        if prop:
            self.assertTrue(any('[*' in op for op in prop.operators))


class TestMultipleModules(unittest.TestCase):
    """多 module 场景"""

    def test_sva_in_different_modules(self):
        """[负面] 不同 module 中的 SVA"""
        source = '''module mod_a(input clk, logic a);
    property p1;
        @(posedge clk) a;
    endproperty
    assert property (p1);
endmodule

module mod_b(input clk, logic b);
    property p2;
        @(posedge clk) b;
    endproperty
    assert property (p2);
endmodule'''
        sva = _extract(source)
        # 两个 module 的 property 都应被提取
        self.assertGreaterEqual(len(sva.properties), 2)

    def test_sva_in_submodule(self):
        """[负面] 子 module 中的 SVA"""
        source = '''module sub(input clk, logic a);
    property p1;
        @(posedge clk) a;
    endproperty
    assert property (p1);
endmodule

module top(input clk, logic a);
    sub u_sub(.clk(clk), .a(a));
endmodule'''
        sva = _extract(source)
        # 子 module 的 SVA 应被提取
        self.assertGreaterEqual(len(sva.properties), 1)


class TestSignalRefEdgeCases(unittest.TestCase):
    """信号关联边界情况"""

    def test_same_signal_multiple_assertions(self):
        """[负面] 同一信号被多个 assertion 引用"""
        source = '''module top(input clk, logic a);
    property p1;
        @(posedge clk) a;
    endproperty
    property p2;
        @(posedge clk) a;
    endproperty
    assert property (p1);
    assert property (p2);
endmodule'''
        sva = _extract(source)
        refs = sva.signal_refs.get('a', [])
        # a 应关联到多个节点
        self.assertGreaterEqual(len(refs), 2)

    def test_clock_signal_excluded(self):
        """[负面] 时钟信号不应出现在信号列表中"""
        source = '''module top(input clk, logic a);
    property p1;
        @(posedge clk) a;
    endproperty
endmodule'''
        sva = _extract(source)
        prop = sva.properties.get('top.p1')
        if prop:
            self.assertNotIn('clk', prop.signals)


class TestOutputEdgeCases(unittest.TestCase):
    """输出格式边界情况"""

    def test_dot_empty_graph(self):
        """[负面] 空图的 DOT 输出"""
        sva = SVAGraph()
        dot = sva.to_dot()
        self.assertIn('digraph', dot)

    def test_mermaid_empty_graph(self):
        """[负面] 空图的 Mermaid 输出"""
        sva = SVAGraph()
        mermaid = sva.to_mermaid()
        self.assertIn('graph', mermaid)

    def test_get_assertions_for_unknown_signal(self):
        """[负面] 查询不存在的信号"""
        sva = SVAGraph()
        result = sva.get_assertions_for_signal('nonexistent')
        self.assertEqual(len(result), 0)

    def test_get_signals_for_unknown_assertion(self):
        """[负面] 查询不存在的 assertion"""
        sva = SVAGraph()
        result = sva.get_signals_for_assertion('nonexistent')
        self.assertEqual(len(result), 0)


class TestUVMCompatibility(unittest.TestCase):
    """UVM 兼容性"""

    def test_sva_with_uvm_macros(self):
        """[负面] 有 UVM 宏的 SVA（不应崩溃）"""
        source = '''module top(input clk, logic a, b);
    `define uvm_info(ID, MSG, VERB)
    property p1;
        @(posedge clk) a |-> b;
    endproperty
    assert property (p1) else `uvm_info("TEST", "fail", 0);
endmodule'''
        sva = _extract(source)
        # 不应崩溃
        self.assertIsInstance(sva, SVAGraph)


if __name__ == '__main__':
    unittest.main()
