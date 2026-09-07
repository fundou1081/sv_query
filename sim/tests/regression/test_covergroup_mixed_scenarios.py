# test_covergroup_mixed_scenarios.py - Covergroup 混合真实场景对抗 (iter_168)
# 方豆 "这次可以混合 class module covergroup 来实际测试，这样更接近真实场景"
# 组合 TB 形态 (env{packet p} + module 驱动链 + module/submodule cg) 全管线
# 验证 (提取 + 建图 + Q1-Q4)。
# 盲点修复:
#   M8 槽展开: class 成员实例 (env.p) — IS_INSTANCE_OF 指向类型级成员槽
#     'tb_env.p' 非活对象 'top.e.p' → CovergroupTracer._class_instances 槽
#     展开 (owner 对象 × 成员后缀, 递归至模块层)
#   M8B 嵌套约束: ConstraintTracer 实例→类型解析泛化嵌套链 (top.e.p.addr →
#     top.e IS_INSTANCE_OF tb_env → tb_env.p IS_INSTANCE_OF packet →
#     packet.addr)
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _tracer(src):
    tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
    tr.build_graph(use_cache=False, target_module='top')
    return tr


ENV_SRC = '''class packet;
    rand bit [7:0] addr;
    covergroup cg_p;
      cp: coverpoint addr;
    endgroup
    function new(); cg_p = new(); endfunction
    function void set(input bit [7:0] d);
      addr = d;
    endfunction
  endclass
  class tb_env;
    packet p;
    covergroup cg_env;
      cp_p: coverpoint p.addr;
    endgroup
    function new();
      p = new();
      cg_env = new();
    endfunction
    function void drive(input bit [7:0] d);
      p.set(d);
    endfunction
  endclass
  module top(input bit clk, input bit [7:0] din);
    tb_env e = new();
    always_ff @(posedge clk) begin
      e.drive(din);
    end
  endmodule'''


class TestNestedClassEnv(unittest.TestCase):
    """M8: env 内包 packet — 类中类实例 + 方法链 + cg (真实 TB 形态)"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(ENV_SRC)

    def test_q1_packet_cg_auto_slot_expansion(self):
        """[M8 修] packet 的 cg: auto 实例落到活对象 top.e.p (非类型槽
        tb_env.p) → 采样 top.e.p.addr, 驱动链 {din} 贯通 (drive→p.set)"""
        infos = self.tr.trace_covergroup_sampling('cg_p')
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].sampled, ['top.e.p.addr'])
        self.assertIn('top.din', infos[0].drivers)

    def test_q1_env_cg(self):
        """env 的 cg (采样成员 p.addr): 同样到活对象"""
        infos = self.tr.trace_covergroup_sampling('cg_env')
        self.assertEqual(infos[0].sampled, ['top.e.p.addr'])
        self.assertIn('top.din', infos[0].drivers)

    def test_q2_both_cgs_on_live_object(self):
        """Q2 活对象 id top.e.p.addr → 两个 cg 都采样 (packet cg 实例
        top.e.p / env cg 实例 top.e)"""
        matches = {(m.cg_name, m.instance) for m in self.tr.trace_coverpoints('top.e.p.addr')}
        self.assertEqual(matches, {('cg_p', 'top.e.p'), ('cg_env', 'top.e')})

    def test_explicit_nested_instance(self):
        """显式 instance='top.e.p' 通过校验 (槽展开后 ∈ 实例集)"""
        infos = self.tr.trace_covergroup_sampling('cg_p', instance='top.e.p')
        self.assertEqual(infos[0].sampled, ['top.e.p.addr'])
        self.assertIn('top.din', infos[0].drivers)


ENV_CONST_SRC = ENV_SRC.replace(
    'rand bit [7:0] addr;\n    covergroup cg_p;',
    'rand bit [7:0] addr;\n    constraint c_addr { addr inside {[16:32]}; }\n    covergroup cg_p;')


class TestNestedConstraintResolution(unittest.TestCase):
    """M8B: 嵌套实例属性的约束解析 (class/constraint 域增强)"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(ENV_CONST_SRC)

    def test_q3_nested_instance_constraint(self):
        """[M8B 修] env cg 采样 p.addr → Q3 约束 = packet.c_addr (经嵌套链
        top.e IS_INSTANCE_OF tb_env → tb_env.p IS_INSTANCE_OF packet)"""
        links = {r.cp_name: r for r in self.tr.trace_covergroup_rand_linkage('cg_env')}
        blocks = {c.block_id for c in links['cp_p'].constraints}
        self.assertEqual(blocks, {'packet.c_addr'})

    def test_trace_constraints_nested(self):
        """class 域 API 直查嵌套实例属性 (非 covergroup)"""
        cons = self.tr.trace_constraints('top.e.p.addr')
        self.assertEqual([c.block_id for c in cons], ['packet.c_addr'])


MIX_SRC = '''class packet;
    rand bit [7:0] acc;
    covergroup cg_acc;
      cp: coverpoint acc;
    endgroup
    function new(); cg_acc = new(); endfunction
    function void accumulate(input bit [7:0] v);
      acc = acc + v;
    endfunction
  endclass
  module sub(input bit clk, input logic [7:0] a, input logic [7:0] b,
             output logic [7:0] s);
    assign s = a ^ b;
  endmodule
  module top(input bit clk, input logic [7:0] din, input logic [7:0] din2);
    logic [7:0] xored;
    logic [7:0] w;
    assign w = din & din2;
    sub u_sub(.clk(clk), .a(din), .b(w), .s(xored));
    packet p = new();
    covergroup cg_mod @(posedge clk);
      cp_x: coverpoint xored;
      cp_w: coverpoint {w, din};
    endgroup
    always_ff @(posedge clk) begin
      p.accumulate(xored);
    end
  endmodule'''


class TestFullStackMixed(unittest.TestCase):
    """M3: module assign + submodule 端口 + class 方法 + module/class 双 cg"""

    @classmethod
    def setUpClass(cls):
        cls.tr = _tracer(MIX_SRC)

    def test_module_cg_q1(self):
        """module cg: cp_w 采样 {w, din} → 驱动 {din, din2}"""
        infos = {i.cp_name: i for i in self.tr.trace_covergroup_sampling('cg_mod')}
        self.assertEqual(infos['cp_w'].sampled, ['top.w', 'top.din'])
        self.assertEqual(sorted(infos['cp_w'].drivers), ['top.din', 'top.din2'])
        self.assertEqual(infos['cp_x'].sampled, ['top.xored'])
        self.assertIn('top.u_sub.s', infos['cp_x'].drivers)

    def test_class_cg_q1_cross_domain(self):
        """class cg: p.accumulate(xored) → acc 驱动链跨到 sub 输出"""
        infos = self.tr.trace_covergroup_sampling('cg_acc')
        self.assertEqual(infos[0].sampled, ['top.p.acc'])
        self.assertIn('top.u_sub.s', infos[0].drivers)

    def test_q2_sub_output_not_directly_sampled(self):
        """u_sub.s 是 xored 的驱动不是采样目标 → Q2 空"""
        self.assertEqual(self.tr.trace_coverpoints('top.u_sub.s'), [])

    def test_q2_module_signals(self):
        matches = {(m.cp_name) for m in self.tr.trace_coverpoints('top.w')}
        self.assertEqual(matches, {'cp_w'})


if __name__ == '__main__':
    unittest.main()
