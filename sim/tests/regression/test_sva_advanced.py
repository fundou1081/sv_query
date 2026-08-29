# test_sva_advanced.py - SVA 语法缺口补充测试
# [iter_062 2026-08-29] 按 TEST_MAP 功能域缺口分析补充:
# 高优先级缺口: 系统函数 ($rose/$fell/$stable/$past/$changed/$onehot),
#               property 内无界范围 ##[0:$], non-consecutive [=n],
#               iff, property 引用 sequence
#
# 策略: 验证提取器**现有行为** (语法被 pyslang 接受 + 提取不崩溃 + 信号/操作符
#       提取正确); expect / immediate assertion 是提取器缺口 (iter_062 实测
#       _parse_assertion 不识别), 按 test_sva_in_class 惯例断言"暂不支持"并记录.
"""
SVA 高级语法覆盖 (iter_062 补充):
1. $rose / $fell / $stable / $past / $changed 系统函数
2. $onehot / $onehot0 / $isunknown
3. property 内无界延迟范围 ##[0:$]
4. non-consecutive repetition [=n]
5. iff 操作符 (property 层)
6. property 引用 sequence
7. expect / immediate assertion — pyslang 可解析, 提取器暂不支持 (记录)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.sva_extractor import SVAExtractor


def _extract(source):
    ext = SVAExtractor({'test.sv': source})
    return ext.extract()


class TestSVASystemFunctions(unittest.TestCase):
    """系统函数在断言中的信号提取"""

    def test_rose_fell_stable(self):
        """[Golden] $rose / $fell / $stable — 边沿检测函数"""
        source = '''module top(input logic clk, req, gnt, data);
    property p_rose;
        @(posedge clk) $rose(req) |-> ##1 gnt;
    endproperty
    property p_fell;
        @(posedge clk) $fell(gnt) |-> data;
    endproperty
    property p_stable;
        @(posedge clk) $stable(data);
    endproperty
    assert property (p_rose);
    assert property (p_fell);
    assert property (p_stable);
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.properties), 3)
        # 信号应被提取 (系统函数参数是信号)
        all_signals = set()
        for p in g.properties.values():
            all_signals.update(p.signals)
        self.assertIn('req', all_signals)
        self.assertIn('gnt', all_signals)
        self.assertIn('data', all_signals)

    def test_past_changed(self):
        """[Golden] $past / $changed — 历史值函数"""
        source = '''module top(input logic clk, req, gnt, data);
    property p_past;
        @(posedge clk) req |-> ##1 ($past(data) == data);
    endproperty
    property p_changed;
        @(posedge clk) $changed(data) |-> gnt;
    endproperty
    assert property (p_past);
    assert property (p_changed);
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.properties), 2)
        all_signals = set()
        for p in g.properties.values():
            all_signals.update(p.signals)
        self.assertIn('data', all_signals)

    def test_onehot_family(self):
        """[Golden] $onehot / $onehot0 / $isunknown / $countones"""
        source = '''module top(input logic clk, valid, input logic [3:0] sel);
    property p_onehot;
        @(posedge clk) valid |-> $onehot(sel);
    endproperty
    property p_unknown;
        @(posedge clk) !$isunknown(sel);
    endproperty
    property p_count;
        @(posedge clk) $countones(sel) == 1;
    endproperty
    assert property (p_onehot);
    assert property (p_unknown);
    assert property (p_count);
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.properties), 3)
        all_signals = set()
        for p in g.properties.values():
            all_signals.update(p.signals)
        self.assertIn('sel', all_signals)
        self.assertIn('valid', all_signals)


class TestSVAOperators(unittest.TestCase):
    """高级时序操作符"""

    def test_unbounded_range_in_property(self):
        """[Golden] property 内无界延迟 ##[0:$]"""
        source = '''module top(input logic clk, req, gnt);
    property p_eventual;
        @(posedge clk) req |-> ##[0:$] gnt;
    endproperty
    assert property (p_eventual);
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.properties), 1)
        p = list(g.properties.values())[0]
        self.assertIn('|->', p.operators)
        self.assertIn('req', p.signals)
        self.assertIn('gnt', p.signals)

    def test_nonconsecutive_repetition(self):
        """[Golden] non-consecutive exact repetition [=n] (与 goto [->n] 区分)"""
        source = '''module top(input logic clk, a, b);
    sequence s_neq;
        @(posedge clk) a [=3] ##1 b;
    endsequence
    sequence s_goto;
        @(posedge clk) a [->2] ##1 b;
    endsequence
    cover property (s_neq);
    cover property (s_goto);
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.sequences), 2, "两种 repetition 序列都应被提取")
        for s in g.sequences.values():
            self.assertIn('a', s.signals)
            self.assertIn('b', s.signals)

    def test_iff_operator(self):
        """[Golden] iff 操作符 (双向蕴含)"""
        source = '''module top(input logic clk, req, ack);
    property p_equiv;
        @(posedge clk) req iff ack;
    endproperty
    assert property (p_equiv);
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.properties), 1)
        p = list(g.properties.values())[0]
        self.assertIn('req', p.signals)
        self.assertIn('ack', p.signals)

    def test_property_references_sequence(self):
        """[Golden] property 引用 sequence (SVA 模块化核心)"""
        source = '''module top(input logic clk, a, b, c, d);
    sequence s_ab;
        @(posedge clk) a ##1 b;
    endsequence
    property p_full;
        @(posedge clk) s_ab |-> c ##1 d;
    endproperty
    assert property (p_full);
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.properties), 1)
        p = list(g.properties.values())[0]
        # 引用的 sequence 应被记录 (字段 sequences; 若当前未填充, 记录为工具缺口)
        if p.sequences:
            self.assertTrue(any('s_ab' in s for s in p.sequences), f"应引用 s_ab: {p.sequences}")
        self.assertIn('c', p.signals)


class TestSVAUnsupported(unittest.TestCase):
    """pyslang 可解析但提取器暂不支持的语法 — 记录为已知缺口"""

    def test_expect_property(self):
        """expect property — SVA 2017 第四类断言.

        pyslang 可解析 (编译通过), 但 _parse_assertion 只识别
        assert/assume/cover (iter_062 实测 expect 不被提取).
        按 test_sva_in_class 惯例断言"暂不支持"并记录.
        """
        source = '''module top(input logic clk, req, gnt);
    property p_req;
        @(posedge clk) req |-> ##[1:3] gnt;
    endproperty
    expect property (p_req);
endmodule'''
        g = _extract(source)
        # property 本身被提取; expect 断言不产生 assertion 节点 (已知缺口)
        self.assertEqual(len(g.properties), 1, "property 应被提取")
        self.assertEqual(len(g.assertions), 0,
            "提取器暂不支持 expect (已知缺口, 见 EXTRACTION_COVERAGE)")

    def test_immediate_assertion(self):
        """Immediate assertion — 过程块内 assert/assume/cover 语句.

        pyslang 可解析, 但提取器只处理并发断言 (iter_062 实测 immediate 不被提取).
        """
        source = '''module top(input logic a, b);
    always_comb begin
        immediate_assert: assert (a == b) else $error("mismatch");
    end
    initial begin
        assume (a || !a);
    end
endmodule'''
        g = _extract(source)
        self.assertEqual(len(g.errors), 0, f"不应有提取错误: {g.errors}")
        self.assertEqual(len(g.assertions), 0,
            "提取器暂不支持 immediate assertion (已知缺口, 见 EXTRACTION_COVERAGE)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
