# test_class_method_call_logic_arg.py - class 方法调用 logic 实参展开 (P1 修复)
# [iter_164 2026-09-06] 方豆 "先处理发现的 class 域问题"
#
# 根因: logic 实参 → bit 形参 (4→2 态) 时 slang 插隐式
# ExpressionKind.Conversion 壳; _parse_invocation_call 守卫
# (not hasattr(expr,'expr') and not is_semantic ...) 静默 continue 丢实参
# → 方法展开断 (bit 通 / logic 断; 与 covergroup 无关, iter_163 实证,
# class truth 全 bit 未暴露)。修复: 实参 + Assignment rhs 剥 Conversion 链
# (iter_136 端口同款壳, 此处调用实参)。
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _fanin(src, signal):
    tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
    tr.build_graph(use_cache=False, target_module='top')
    return {r.id for r in tr.trace_fanin(signal)}


class TestClassMethodLogicArg(unittest.TestCase):
    """P1: class 方法调用 — logic 4 态实参 → 实例成员展开 (修复前断)"""

    def test_logic_arg_drives_instance_property(self):
        """logic din → p.set(din) → fanin(p.addr) = {din} (P1 前空)"""
        src = '''class packet;
    bit [7:0] addr;
    function void set(input bit [7:0] d);
      addr = d;
    endfunction
  endclass
  module top(input bit clk, input logic [7:0] din);
    packet p = new();
    always_ff @(posedge clk) begin
      p.set(din);
    end
  endmodule'''
        ids = _fanin(src, 'top.p.addr')
        self.assertIn('top.din', ids, f"logic 实参应驱动实例属性, 实际 {ids}")

    def test_bit_arg_still_works(self):
        """bit 实参路径不回归"""
        src = '''class packet;
    bit [7:0] addr;
    function void set(input bit [7:0] d);
      addr = d;
    endfunction
  endclass
  module top(input bit clk, input bit [7:0] din);
    packet p = new();
    always_ff @(posedge clk) begin
      p.set(din);
    end
  endmodule'''
        self.assertIn('top.din', _fanin(src, 'top.p.addr'))

    def test_mixed_multi_arg(self):
        """多参混合 logic/bit: 各自驱动对应成员"""
        src = '''class packet;
    bit [7:0] addr;
    bit [3:0] tag;
    function void set(input bit [7:0] d, input bit [3:0] t);
      addr = d;
      tag = t;
    endfunction
  endclass
  module top(input bit clk, input logic [7:0] din, input bit [3:0] tsel);
    packet p = new();
    always_ff @(posedge clk) begin
      p.set(din, tsel);
    end
  endmodule'''
        self.assertIn('top.din', _fanin(src, 'top.p.addr'))
        self.assertIn('top.tsel', _fanin(src, 'top.p.tag'))

    def test_named_arg_logic(self):
        """命名参数 .d(din) + logic 实参"""
        src = '''class packet;
    bit [7:0] addr;
    function void set(input bit [7:0] d);
      addr = d;
    endfunction
  endclass
  module top(input bit clk, input logic [7:0] din);
    packet p = new();
    always_ff @(posedge clk) begin
      p.set(.d(din));
    end
  endmodule'''
        self.assertIn('top.din', _fanin(src, 'top.p.addr'))

    def test_module_function_logic_arg(self):
        """module task/function 同样受益 (logic 入参 → output 贯通)"""
        src = '''module top(input bit clk, input logic [7:0] din, output bit [7:0] out);
    function void pass(input bit [7:0] d, output bit [7:0] o);
      o = d;
    endfunction
    always_ff @(posedge clk) pass(din, out);
  endmodule'''
        self.assertIn('top.din', _fanin(src, 'top.out'))

    def test_sequential_builds_stable(self):
        """连续 build + 中间查询不退化 (iter_163 P2 复测 — bit fixture 无
        状态退化, 原报告系 P1 混淆): 顺序无 target → target → fanin"""
        src = '''class packet;
    bit [7:0] addr;
    function void set(input bit [7:0] d);
      addr = d;
    endfunction
  endclass
  module top(input bit clk, input bit [7:0] din);
    packet p = new();
    always_ff @(posedge clk) begin
      p.set(din);
    end
  endmodule'''
        tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
        # 先无 target 查询 (内部建图), 再 target 建图, 再 fanin
        tr.trace_class_instances('packet')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.p.addr')}
        self.assertIn('top.din', ids, f"连续 build 后 fanin 应稳定, 实际 {ids}")
        # 再重建一次仍稳定
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.p.addr')}
        self.assertIn('top.din', ids)


if __name__ == '__main__':
    unittest.main()
