# test_covergroup_signal_refs.py - Covergroup G1: in_class 归属 + 采样信号结构化解析
# [G1 iter_162 2026-09-06] 方案 B (独立结构+查询桥) 首步:
#   - CovergroupInfo.in_class: 语义树 class 内 covergroup 归属 (旧恒空,
#     coverage.py --class 过滤静默失效)
#   - CoverpointInfo.sampled: coverpoint 表达式拆到结构化信号引用
#     (SampledSignal: name/kind/host/select/raw), signal 原文保留 (8 消费方)
# 决策: 类型级为主 (class 属性 → class_prop + host=所在 class, D3 一致);
# 表达式 coverpoint 拆到每个信号; bins/iff/时钟语义不在此域。
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.covergroup_extractor import CovergroupExtractor


def _cgs(source):
    return CovergroupExtractor({'test.sv': source}).extract()


def _sig(cp):
    """cp.sampled → [(name, kind, host, select, raw)] 强断言友好形"""
    return [(s.name, s.kind, s.host, s.select, s.raw) for s in cp.sampled]


class TestModuleSignalRefs(unittest.TestCase):
    """G1: module 顶层 coverpoint 表达式 → 采样信号引用"""

    MODULE = '''module top(input logic clk, input logic [7:0] din);
    logic [3:0] a, b;
    logic [7:0] q;
    logic [3:0] arr [0:7];
    typedef struct { logic [3:0] x; } st_t;
    st_t s;
    function logic [7:0] get(logic [7:0] v); return v; endfunction
    covergroup cg @(posedge clk);
      %s
    endgroup
  endmodule'''

    def _cp_sampled(self, cp_decl):
        cgs = _cgs(self.MODULE % cp_decl)
        cg = [c for c in cgs if c.in_class == ''][0]
        self.assertEqual(len(cg.coverpoints), 1)
        return cg.coverpoints[0]

    def test_in_class_empty_for_module(self):
        """module 顶层 covergroup: in_class 恒空 (归属不发生)"""
        cgs = _cgs(self.MODULE % 'cp: coverpoint din;')
        self.assertTrue(all(c.in_class == '' for c in cgs))

    def test_plain_identifier(self):
        cp = self._cp_sampled('cp: coverpoint din;')
        self.assertEqual(cp.signal, 'din', "signal 原文保留")
        self.assertEqual(_sig(cp), [('din', 'module', '', '', 'din')])

    def test_bit_select(self):
        cp = self._cp_sampled('cp: coverpoint din[3:0];')
        self.assertEqual(_sig(cp), [('din', 'module', '', '[3:0]', 'din[3:0]')])

    def test_indexed_select(self):
        cp = self._cp_sampled('cp: coverpoint din[0+:4];')
        self.assertEqual(_sig(cp), [('din', 'module', '', '[0+:4]', 'din[0+:4]')])

    def test_concat_multi_signal(self):
        """{din, a} = 多信号观察 (决策点 2: 拆到每个信号)"""
        cp = self._cp_sampled('cp: coverpoint {din, a};')
        self.assertEqual(_sig(cp),
                         [('din', 'module', '', '', 'din'),
                          ('a', 'module', '', '', 'a')])

    def test_concat_dedup(self):
        cp = self._cp_sampled('cp: coverpoint {din, din};')
        self.assertEqual(_sig(cp), [('din', 'module', '', '', 'din')])

    def test_struct_member(self):
        cp = self._cp_sampled('cp: coverpoint s.x;')
        self.assertEqual(_sig(cp), [('s.x', 'module', '', '', 's.x')])

    def test_member_bit_select(self):
        cp = self._cp_sampled('cp: coverpoint s.x[2];')
        self.assertEqual(_sig(cp), [('s.x', 'module', '', '[2]', 's.x[2]')])

    def test_expression_of_signals(self):
        """表达式 cp: 数据源引用拆出, 常量不产生引用"""
        cp = self._cp_sampled('cp: coverpoint s.x + b[1];')
        self.assertEqual(_sig(cp),
                         [('s.x', 'module', '', '', 's.x'),
                          ('b', 'module', '', '[1]', 'b[1]')])

    def test_ternary_signals(self):
        cp = self._cp_sampled('cp: coverpoint a ? b : din;')
        names = [s.name for s in cp.sampled]
        self.assertEqual(names, ['a', 'b', 'din'])

    def test_bitwise_literal_skipped(self):
        cp = self._cp_sampled("cp: coverpoint (din & 8'hff) | {a, 1'b0};")
        self.assertEqual([s.name for s in cp.sampled], ['din', 'a'])

    def test_array_element(self):
        cp = self._cp_sampled('cp: coverpoint arr[2];')
        self.assertEqual(_sig(cp), [('arr', 'module', '', '[2]', 'arr[2]')])

    def test_array_of_struct_member(self):
        """中段 select 链: st_arr[1].y — select 内嵌 path (近似, 罕见形态)"""
        src = '''module top(input logic clk);
    typedef struct { logic [3:0] x; logic [3:0] y; } st_t;
    st_t st_arr [0:3];
    covergroup cg @(posedge clk);
      cp: coverpoint st_arr[1].y;
    endgroup
  endmodule'''
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual(_sig(cp), [('st_arr[1].y', 'module', '', '', 'st_arr[1].y')])

    def test_function_call_callee_not_signal(self):
        """函数调用 cp: callee 不进引用 (procedural 域), 实参引用保留"""
        cp = self._cp_sampled('cp: coverpoint get(din);')
        self.assertEqual(_sig(cp), [('din', 'module', '', '', 'din')])

    def test_system_call(self):
        cp = self._cp_sampled('cp: coverpoint din & $clog2(16);')
        self.assertEqual([s.name for s in cp.sampled], ['din'])

    def test_cast_and_unary(self):
        src = '''module top(input logic clk);
    logic [7:0] w;
    covergroup cg @(posedge clk);
      cp: coverpoint unsigned'(w) + -w;
    endgroup
  endmodule'''
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual([s.name for s in cp.sampled], ['w'])

    def test_inside_set(self):
        src = '''module top(input logic clk);
    logic [7:0] q;
    covergroup cg @(posedge clk);
      cp: coverpoint q[3:0] inside {[0:5]};
    endgroup
  endmodule'''
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual(_sig(cp), [('q', 'module', '', '[3:0]', 'q[3:0]')])


class TestClassSignalRefs(unittest.TestCase):
    """G1: class 内 covergroup — in_class 归属 + 采样 class 属性 (类型级)"""

    def test_in_class_attribution(self):
        """[金标准] class 内 cg → in_class = class 名 (旧恒空)"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(); cg = new(); endfunction
  endclass
  module top; endmodule'''
        cgs = _cgs(src)
        self.assertGreaterEqual(len(cgs), 1)
        cg = [c for c in cgs if c.name == 'cg'][0]
        self.assertEqual(cg.in_class, 'packet')

    def test_class_prop_kind_and_host(self):
        """class 内 cp 采样属性 → kind=class_prop host=class (类型级, D3)"""
        src = '''class packet;
    rand bit [7:0] addr;
    bit [3:0] tag;
    covergroup cg;
      cp: coverpoint addr;
      cp2: coverpoint {addr, tag};
    endgroup
  endclass'''
        cg = [c for c in _cgs(src) if c.name == 'cg'][0]
        by_name = {c.name: c for c in cg.coverpoints}
        self.assertEqual(_sig(by_name['cp']),
                         [('addr', 'class_prop', 'packet', '', 'addr')])
        self.assertEqual(_sig(by_name['cp2']),
                         [('addr', 'class_prop', 'packet', '', 'addr'),
                          ('tag', 'class_prop', 'packet', '', 'tag')])

    def test_class_prop_select(self):
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr[3:0];
    endgroup
  endclass'''
        cg = [c for c in _cgs(src) if c.name == 'cg'][0]
        self.assertEqual(_sig(cg.coverpoints[0]),
                         [('addr', 'class_prop', 'packet', '[3:0]', 'addr[3:0]')])

    def test_inherited_prop(self):
        """extends 父类属性采样: host = 声明 cg 的 class (成员解析沿 extends
        链 — G3 桥, function_extractor 同款)"""
        src = '''class base;
    rand bit [3:0] len;
  endclass
  class packet extends base;
    rand bit [7:0] addr;
    covergroup cg;
      cp_len: coverpoint len;
      cp_addr: coverpoint addr;
    endgroup
  endclass'''
        cg = [c for c in _cgs(src) if c.name == 'cg'][0]
        by_name = {c.name: c for c in cg.coverpoints}
        self.assertEqual(_sig(by_name['cp_len']),
                         [('len', 'class_prop', 'packet', '', 'len')])
        self.assertEqual(_sig(by_name['cp_addr']),
                         [('addr', 'class_prop', 'packet', '', 'addr')])

    def test_signal_raw_kept(self):
        """signal 原文字段不动 (8 消费方兼容)"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint {addr[3:0], addr[7:4]};
    endgroup
  endclass'''
        cg = [c for c in _cgs(src) if c.name == 'cg'][0]
        cp = cg.coverpoints[0]
        self.assertEqual(cp.signal, '{addr[3:0], addr[7:4]}')
        self.assertEqual(_sig(cp),
                         [('addr', 'class_prop', 'packet', '[3:0]', 'addr[3:0]'),
                          ('addr', 'class_prop', 'packet', '[7:4]', 'addr[7:4]')])


class TestEdgeCases(unittest.TestCase):
    """G1 边界: 匿名 coverpoint / 无采样表达式不崩"""

    def test_anonymous_cp_no_crash(self):
        """covergroup 级裸 bins → slang 匿名 coverpoint (空名): 不崩, 空引用"""
        src = '''class packet2;
    rand bit [7:0] addr;
    covergroup cg2;
      cp2: coverpoint addr;
      bins lo2[] = {[0:100]};
    endgroup
  endclass'''
        cgs = _cgs(src)
        self.assertGreaterEqual(len(cgs), 1)
        for cg in cgs:
            for cp in cg.coverpoints:
                self.assertIsInstance(cp.sampled, list)

    def test_bins_inside_cp_still_extracted(self):
        """class cp 内 bins 提取不受 sampled 影响"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr { bins lo[] = {[0:100]}; }
    endgroup
  endclass'''
        cg = [c for c in _cgs(src) if c.name == 'cg'][0]
        cp = cg.coverpoints[0]
        self.assertEqual([(b.name, b.values) for b in cp.bins], [('lo', '{[0:100]}')])


if __name__ == '__main__':
    unittest.main()
