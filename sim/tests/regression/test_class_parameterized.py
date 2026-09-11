# test_class_parameterized.py - 参数化 class 支持 (iter_170, 方豆 "按A, 开专项做")
# GenericClassDef (参数化 class 定义) 无成员面 → 特化符号 (实例变量/成员
# 属性/父类链的特化 ClassType) 提供语义成员:
#   semantic_adapter.get_class_members 统一入口 + _scan_class_specializations
#   (含 baseClass 链); class_graph_builder 3 处 + function_extractor +
#   covergroup_extractor (GenericClassDef scope/提取/ctor 分析) 全换统一入口
# 验收: P1 宽度参数 / P2 多特化 / P3 参数 extends (继承约束传播) — 提取/
# 图/方法展开/Q1-Q3 全通; 非参数化零回归
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _tracer(src):
    tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
    tr.build_graph(use_cache=False, target_module='top')
    return tr


WIDTH_SRC = '''class packet #(int W = 8);
    rand bit [W-1:0] data;
    covergroup cg;
      cp: coverpoint data;
    endgroup
    function new(); cg = new(); endfunction
    function void set(input bit [W-1:0] d);
      data = d;
    endfunction
  endclass
  module top(input bit clk, input bit [15:0] din);
    packet #(16) p = new();
    always_ff @(posedge clk) p.set(din);
  endmodule'''


class TestWidthParamClass(unittest.TestCase):
    """P1: 宽度参数 class 全链"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(WIDTH_SRC)

    def test_extraction_rule(self):
        """cg 提取 (in_class/instance_rule — ctor new 从特化成员语法)"""
        # 通过 query 侧面验证: 有 cg 且能 Q1
        self.assertTrue(self.tr.trace_covergroup_sampling('cg'))

    def test_graph_members(self):
        """成员节点 (data/cg) 建立 (原只 packet/top.p)"""
        nodes = self.tr.build_graph(use_cache=False).nodes()
        self.assertIn('packet.data', nodes)
        self.assertIn('packet.cg', nodes)

    def test_q1_method_chain(self):
        """p.set(din) (W=16 特化) → 采样 data → 驱动 {din}"""
        infos = self.tr.trace_covergroup_sampling('cg')
        self.assertEqual(infos[0].sampled, ['top.p.data'])
        self.assertIn('top.din', infos[0].drivers)

    def test_q2_reverse(self):
        matches = {(m.cp_name, m.instance) for m in self.tr.trace_coverpoints('top.p.data')}
        self.assertEqual(matches, {('cp', 'top.p')})


TWO_SPEC_SRC = '''class packet #(int W = 8);
    rand bit [W-1:0] data;
    covergroup cg;
      cp: coverpoint data;
    endgroup
    function new(); cg = new(); endfunction
    function void set(input bit [W-1:0] d);
      data = d;
    endfunction
  endclass
  module top(input bit clk, input bit [15:0] din, input bit [7:0] din8);
    packet #(16) p16 = new();
    packet #(8) p8 = new();
    always_ff @(posedge clk) begin
      p16.set(din);
      p8.set(din8);
    end
  endmodule'''


class TestTwoSpecializations(unittest.TestCase):
    """P2: 双特化 (W=16/8) 各自实例"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(TWO_SPEC_SRC)

    def test_explicit_instances_isolated(self):
        """p16 ← din; p8 ← din8 (逐实例隔离, 同类型级节点不同数据端点)"""
        i16 = self.tr.trace_covergroup_sampling('cg', instance='top.p16')[0]
        self.assertEqual(i16.sampled, ['top.p16.data'])
        self.assertIn('top.din', i16.drivers)
        i8 = self.tr.trace_covergroup_sampling('cg', instance='top.p8')[0]
        self.assertEqual(i8.sampled, ['top.p8.data'])
        self.assertIn('top.din8', i8.drivers)

    def test_auto_multi_missing(self):
        """双实例 auto → 歧义 missing (设计)"""
        infos = self.tr.trace_covergroup_sampling('cg')
        self.assertEqual(infos[0].sampled, [])

    def test_q2_each_instance(self):
        m16 = {m.instance for m in self.tr.trace_coverpoints('top.p16.data')}
        self.assertEqual(m16, {'top.p16'})


PARAM_EXTENDS_SRC = '''class base #(int W = 8);
    rand bit [W-1:0] len;
    constraint c_len { len inside {[1:8]}; }
  endclass
  class packet #(int W = 8) extends base #(W);
    rand bit [W-1:0] data;
    covergroup cg;
      cp: coverpoint data;
      cp_len: coverpoint len;
    endgroup
    function new(); cg = new(); endfunction
    function void set(input bit [W-1:0] d);
      data = d;
    endfunction
  endclass
  module top(input bit clk, input bit [15:0] din);
    packet #(16) p = new();
    always_ff @(posedge clk) p.set(din);
  endmodule'''


class TestParamExtends(unittest.TestCase):
    """P3: 参数化 extends (父类只被继承无实例 — baseClass 链收录)"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(PARAM_EXTENDS_SRC)

    def test_base_members_via_baseclass_chain(self):
        """base.len + 约束建成 (base 无实例变量, 沿特化 baseClass 收录)"""
        nodes = self.tr.build_graph(use_cache=False).nodes()
        self.assertIn('base.len', nodes)
        self.assertIn('packet.len', nodes)
        self.assertIn('packet.c_len', nodes)

    def test_q1_inherited_cp(self):
        infos = {i.cp_name: i for i in self.tr.trace_covergroup_sampling('cg')}
        self.assertEqual(infos['cp'].sampled, ['top.p.data'])
        self.assertEqual(infos['cp_len'].sampled, ['top.p.len'])

    def test_q3_inherited_constraint(self):
        """cp_len 采样 len (父类属性) → 约束 packet.c_len (继承传播)"""
        links = {r.cp_name: r for r in self.tr.trace_covergroup_rand_linkage('cg')}
        blocks = {c.block_id for c in links['cp_len'].constraints}
        self.assertEqual(blocks, {'packet.c_len'})

    def test_constraint_api_base_prop(self):
        cons = self.tr.trace_constraints('packet.len')
        self.assertEqual([c.block_id for c in cons], ['packet.c_len'])


if __name__ == '__main__':
    unittest.main()


# ── iter_178: 参数化 class 的成员解析 helper (_is_class_member /
#    _member_class_name 曾直接 list(cls) → GenericClassDef 不可迭代 → 静默 False)
P5_INNER_MEMBER_SRC = '''class inner #(int W = 8);
    bit [W-1:0] val;
    function void set(input bit [W-1:0] v);
      val = v;
    endfunction
  endclass
  class packet #(int W = 8);
    inner #(W) i;
    function new(); i = new(); endfunction
    function void drive(input bit [W-1:0] v);
      i.set(v);
    endfunction
  endclass
  module top(input bit clk, input bit [7:0] din);
    packet #(8) p = new();
    always_ff @(posedge clk) p.drive(din);
  endmodule'''

P6_THIS_MEMBER_RHS_SRC = '''class packet #(int W = 8);
    bit [W-1:0] data;
    bit [W-1:0] tmp;
    function void helper(input bit [W-1:0] v);
      tmp = v;
    endfunction
    function void set(input bit [W-1:0] d);
      helper(d);
      data = tmp;
    endfunction
  endclass
  module top(input bit clk, input bit [7:0] din);
    packet #(8) p = new();
    always_ff @(posedge clk) p.set(din);
  endmodule'''


class TestParameterizedMemberHelpers(unittest.TestCase):
    """iter_178: 参数化 class 的成员解析 (原 _is_class_member/_member_class_name
    直接 list(cls) → GenericClassDef 不可迭代 → 静默 False/None)"""

    def test_inner_class_member_chain(self):
        """E13 形态 + 参数化: 成员 i (class 类型) → i.set(v) 展开到 i.val"""
        tr = _tracer(P5_INNER_MEMBER_SRC)
        ids = {r.id for r in tr.trace_fanin('top.p.i.val')}
        self.assertIn('top.din', ids, f"参数化成员实例链应贯通, 实际 {ids}")

    def test_this_member_rhs(self):
        """E5 形态 + 参数化: data = tmp (本实例成员) → tmp 由 helper 驱动"""
        tr = _tracer(P6_THIS_MEMBER_RHS_SRC)
        ids = {r.id for r in tr.trace_fanin('top.p.data')}
        self.assertIn('top.din', ids, f"参数化 this 成员链应贯通, 实际 {ids}")
