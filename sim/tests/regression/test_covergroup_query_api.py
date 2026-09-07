# test_covergroup_query_api.py - Covergroup G3: 查询 API (Q1-Q3)
# [G3 iter_165 2026-09-06] 方案 B / D4 范式 — query/covergroup.py:
#   Q1 trace_covergroup_sampling: cp 采样信号 → fanin (数据 fanin 单一实现)
#   Q2 trace_coverpoints(signal): 反向 (module 顶层 / class 类型级 / 实例级)
#   Q3 trace_covergroup_rand_linkage: class cg 采样属性 → 约束 (ConstraintTracer)
# 观察边不进主图; class cg 数据端点 = 实例 (D3), 单实例自动取/多实例显式。
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _tracer(src):
    tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
    tr.build_graph(use_cache=False, target_module='top')
    return tr


MOD_SRC = '''module top(input bit clk, input bit [7:0] a);
    logic [7:0] din;
    assign din = a + 1;
    covergroup cg_mod @(posedge clk);
      cp_d: coverpoint din;
      cp_c: coverpoint {din, a};
    endgroup
  endmodule'''

CLS_SRC = '''class packet;
    rand bit [7:0] addr;
    rand bit [3:0] tag;
    constraint c_addr { addr inside {[0:100]}; }
    constraint c_tag { tag > 5; }
    covergroup cg;
      cp_addr: coverpoint addr;
      cp_both: coverpoint {addr, tag};
    endgroup
    function new(); cg = new(); endfunction
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


class TestModuleQueries(unittest.TestCase):
    """G3 Q1/Q2 — module 顶层 covergroup (宿主锚 host_module)"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(MOD_SRC)

    def test_q1_sampling_chain_module(self):
        """Q1: cp_d 采样 top.din → 驱动 {top.a}; cp_c 拆 {din, a}"""
        infos = {i.cp_name: i for i in self.tr.trace_covergroup_sampling('cg_mod')}
        d = infos['cp_d']
        self.assertEqual(d.sampled, ['top.din'])
        self.assertEqual(d.drivers, ['top.a'])
        c = infos['cp_c']
        self.assertEqual(c.sampled, ['top.din', 'top.a'])
        self.assertEqual(c.drivers, ['top.a'], "din 由 a 驱动, a 无驱动 → 并集 {a}")

    def test_q2_reverse_module(self):
        """Q2: top.din 被 cp_d + cp_c 采样; top.a 只被 cp_c"""
        din_matches = {(m.cp_name, m.host_module) for m in self.tr.trace_coverpoints('top.din')}
        self.assertEqual(din_matches, {('cp_d', 'top'), ('cp_c', 'top')})
        a_matches = {m.cp_name for m in self.tr.trace_coverpoints('top.a')}
        self.assertEqual(a_matches, {'cp_c'})


class TestClassQueries(unittest.TestCase):
    """G3 Q1/Q2/Q3 — class 内 covergroup (类型级 + 实例级)"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(CLS_SRC)

    def test_q1_auto_unique_instance(self):
        """Q1: 单实例自动取 top.p — cp_addr 采样 p.addr → 驱动 {din}"""
        infos = {i.cp_name: i for i in self.tr.trace_covergroup_sampling('cg')}
        a = infos['cp_addr']
        self.assertEqual(a.sampled, ['top.p.addr'])
        self.assertIn('top.din', a.drivers)
        b = infos['cp_both']
        self.assertEqual(b.sampled, ['top.p.addr', 'top.p.tag'])

    def test_q1_explicit_instance(self):
        infos = {i.cp_name: i
                 for i in self.tr.trace_covergroup_sampling('cg', instance='top.p')}
        self.assertEqual(infos['cp_addr'].sampled, ['top.p.addr'])
        self.assertIn('top.din', infos['cp_addr'].drivers)

    def test_q2_type_level(self):
        """Q2 类型级: packet.addr 被 cp_addr + cp_both 采样 (模板结构)"""
        matches = {(m.cp_name, m.in_class, m.instance)
                   for m in self.tr.trace_coverpoints('packet.addr')}
        self.assertEqual(matches, {('cp_addr', 'packet', ''), ('cp_both', 'packet', '')})

    def test_q2_instance_level(self):
        """Q2 实例级: top.p.addr → 同 cp, 标注实例 top.p"""
        matches = {(m.cp_name, m.instance) for m in self.tr.trace_coverpoints('top.p.addr')}
        self.assertEqual(matches, {('cp_addr', 'top.p'), ('cp_both', 'top.p')})

    def test_q2_no_module_match(self):
        """module 信号不被 class cg 采样 → 空"""
        self.assertEqual(self.tr.trace_coverpoints('top.din'), [])

    def test_q3_rand_linkage_type_and_instance(self):
        """Q3: cp_addr 采样 addr → 约束 c_addr; cp_both → addr+tag 各自约束"""
        links = {r.cp_name: r for r in self.tr.trace_covergroup_rand_linkage('cg')}
        self.assertEqual(links['cp_addr'].prop_id, 'top.p.addr', "单实例自动解析")
        blocks = {c.block_id for c in links['cp_addr'].constraints}
        self.assertEqual(blocks, {'packet.c_addr'})
        both = {r.prop_id: {c.block_id for c in r.constraints}
                for r in self.tr.trace_covergroup_rand_linkage('cg', cp_name='cp_both')}
        self.assertEqual(both, {
            'top.p.addr': {'packet.c_addr'},
            'top.p.tag': {'packet.c_tag'},
        })

    def test_q3_explicit_instance(self):
        links = {r.prop_id for r in
                 self.tr.trace_covergroup_rand_linkage('cg', instance='top.p')}
        self.assertEqual(links, {'top.p.addr', 'top.p.tag'})


class TestMultiInstanceAmbiguity(unittest.TestCase):
    """G3 边界: 多实例 class cg — Q1 须显式 instance"""

    SRC = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(); cg = new(); endfunction
    function void set(input bit [7:0] d);
      addr = d;
    endfunction
  endclass
  module top(input bit clk, input bit [7:0] din);
    packet p1 = new();
    packet p2 = new();
    always_ff @(posedge clk) begin
      p1.set(din);
    end
  endmodule'''

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(cls.SRC)

    def test_multi_instance_requires_explicit(self):
        """2 实例 → Q1 缺省歧义 (missing), 显式 p1/p2 各得其所"""
        infos = self.tr.trace_covergroup_sampling('cg')
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].sampled, [], "多实例歧义 → 不臆测实例")
        self.assertEqual(infos[0].missing, ['addr'])
        i1 = self.tr.trace_covergroup_sampling('cg', instance='top.p1')[0]
        self.assertEqual(i1.sampled, ['top.p1.addr'])
        self.assertIn('top.din', i1.drivers)
        i2 = self.tr.trace_covergroup_sampling('cg', instance='top.p2')[0]
        self.assertEqual(i2.sampled, ['top.p2.addr'])
        self.assertEqual(i2.drivers, [], "p2.set 未调用 → p2.addr 无驱动")

    def test_q2_multi_instance_each(self):
        """Q2: 类型级 packet.addr → 模板匹配 (instance=''); 实例级查询
        top.p1.addr / top.p2.addr 各自标注实例 (分开的查询域, D3)"""
        type_matches = {m.instance for m in self.tr.trace_coverpoints('packet.addr')}
        self.assertEqual(type_matches, {''})
        p1_matches = {m.instance for m in self.tr.trace_coverpoints('top.p1.addr')}
        self.assertEqual(p1_matches, {'top.p1'})
        p2_matches = {m.instance for m in self.tr.trace_coverpoints('top.p2.addr')}
        self.assertEqual(p2_matches, {'top.p2'})


if __name__ == '__main__':
    unittest.main()
