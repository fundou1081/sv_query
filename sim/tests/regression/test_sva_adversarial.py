# test_sva_adversarial.py - SVA 对抗场景修复回归 (iter_121)
#
# [iter_121] 方豆对抗验证发现的 6 个 SVA 提取缺口, 全部修复后的锁定测试:
# 1. formal 参数替换: assert property(p_arg(a,b)) → a,b 进 signals (非形式参 x/y)
# 2. sequence 引用展开: property 引 sequence → 序列内信号 (a,b) 进 signals
# 3. 局部变量剔除: (a, tmp = b) 的 tmp 不是信号
# 4. 函数剔除: $countones({b, f(data)}) 里自定义函数 f 不是信号
# 5. generate-for 内 assert property: per-entry 断言被提取 (0→4), 信号含 base
#    (y[i] → y, genvar i 不进)
# 6. covergroup option/type_option 不再被当 SVA property (跨域污染)
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.sva_extractor import SVAExtractor  # noqa: E402


def _extract(source):
    g = SVAExtractor({'test.sv': source}).extract()
    assert len(g.errors) == 0, f"不应有提取错误: {g.errors}"
    return g


class TestSVAFormalArgs(unittest.TestCase):
    """#1 formal 参数替换: 实例化实参进 property signals."""

    SRC = '''module top(input logic clk, a, b, c);
  sequence s_arg(logic x, logic y); x ##1 y; endsequence
  property p_arg(logic x, logic y);
    @(posedge clk) s_arg(x, y) |-> c;
  endproperty
  assert property (p_arg(a, b));
endmodule'''

    def test_actual_args_in_signals(self):
        g = _extract(self.SRC)
        sigs = g.properties['top.p_arg'].signals
        for s in ('a', 'b', 'c'):
            self.assertIn(s, sigs, f"实参 {s} 应进 signals")
        for f in ('x', 'y'):
            self.assertNotIn(f, sigs, f"形式参 {f} 不应是信号 (iter_121 前泄漏)")

    def test_property_ref_resolved(self):
        g = _extract(self.SRC)
        self.assertEqual(g.assertions[0].property_ref, 'top.p_arg')


class TestSVALocalVar(unittest.TestCase):
    """#3 局部变量剔除."""

    SRC = '''module top(input logic clk, a, b, output logic [7:0] out);
  property p_loc;
    int tmp;
    @(posedge clk) (a, tmp = b) ##1 (out == tmp);
  endproperty
  assert property (p_loc);
endmodule'''

    def test_local_not_signal(self):
        g = _extract(self.SRC)
        sigs = g.properties['top.p_loc'].signals
        self.assertNotIn('tmp', sigs, "local var tmp 不应是信号 (iter_121 前泄漏)")
        for s in ('a', 'b', 'out'):
            self.assertIn(s, sigs)


class TestSVAUserFunction(unittest.TestCase):
    """#4 用户函数不当信号."""

    SRC = '''module top(input logic clk, a, b, data);
  function automatic logic f(logic x); return ~x; endfunction
  property p_fn;
    @(posedge clk) a |-> $countones({b, f(data)}) > 0;
  endproperty
  cover property (p_fn);
endmodule'''

    def test_function_not_signal(self):
        g = _extract(self.SRC)
        sigs = g.properties['top.p_fn'].signals
        self.assertNotIn('f', sigs, "用户函数 f 不应是信号 (iter_121 前泄漏)")
        for s in ('a', 'b', 'data'):
            self.assertIn(s, sigs)


class TestSVASequenceExpansion(unittest.TestCase):
    """#2 sequence 引用展开 + 多时钟噪声."""

    SRC = '''module top(input logic clk, clk2, a, b, c);
  sequence s_seq; @(posedge clk2) a ##1 b; endsequence
  property p_multi;
    @(posedge clk) s_seq |-> c;
  endproperty
  assert property (p_multi);
endmodule'''

    def test_sequence_inner_signals_expanded(self):
        g = _extract(self.SRC)
        sigs = g.properties['top.p_multi'].signals
        for s in ('a', 'b', 'c'):
            self.assertIn(s, sigs, f"sequence 内信号 {s} 应展开进 property")
        self.assertNotIn('s_seq', sigs, "序列名不应留在 signals")
        self.assertNotIn('clk2', sigs, "时钟名不应作为信号 (噪声)")


class TestSVAGenerateAssertions(unittest.TestCase):
    """#5 generate-for 内 assert property 提取."""

    SRC = '''module top(input logic clk, a, output logic [3:0] y);
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : G
    assert property (@(posedge clk) a |-> y[i]);
  end endgenerate
endmodule'''

    def test_per_entry_assertions_extracted(self):
        g = _extract(self.SRC)
        self.assertEqual(len(g.assertions), 4,
                         "generate 4 entry 各 1 断言 (iter_121 前 0 提取)")

    def test_inline_signals_base_only(self):
        g = _extract(self.SRC)
        for a in g.assertions:
            self.assertIn('a', a.signals)
            self.assertIn('y', a.signals, "y[i] 的 base y 应提取")
            self.assertNotIn('i', a.signals, "genvar i 不应是信号")
            self.assertEqual(a.property_ref, '',
                             "inline property 无 property 引用 (旧误填 top.a)")


class TestSVACovergroupPollution(unittest.TestCase):
    """#6 covergroup option 不当 SVA property."""

    SRC = '''interface bus_if(input logic clk);
  logic req, gnt;
  property p_req; @(posedge clk) req |-> ##1 gnt; endproperty
  assert property (p_req);
  covergroup cg @(posedge clk);
    cp: coverpoint req;
  endgroup
endinterface
module top(input logic clk);
  bus_if u_bus(.clk(clk));
endmodule'''

    def test_no_option_pollution(self):
        g = _extract(self.SRC)
        names = list(g.properties.keys())
        self.assertIn('top.u_bus.p_req', names)
        for bad in ('option', 'type_option'):
            self.assertFalse(
                any(bad in n for n in names),
                f"covergroup {bad} 不应是 SVA property: {names}")


if __name__ == '__main__':
    unittest.main()
