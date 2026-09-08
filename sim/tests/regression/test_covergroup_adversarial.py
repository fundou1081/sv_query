# test_covergroup_adversarial.py - Covergroup 对抗轮 (iter_167)
# 方豆 "先来再做一些对抗性测试。试着找出盲点。" (iter_156 class 同款方法)
# 盲点扫描结果:
#   ✅ 修 2 真 bug: A2 (自定义类型 cast my_t'(w) 把类型名当信号收集 —
#       CastExpressionSyntax 跳过类型子节点) / C4 (查询传非该类实例
#       instance='top.nope' 静默造 bogus id → 校验实例集, 不符 → missing)
#   📌 登记边界 (静态限定/文档): A5 变量索引 (arr[idx] 不收集 idx —
#       寻址非采样数据) / A8 $root 层次引用 (桥不处理, ref 去 $root) /
#       B1 extends (base cg 自动实例查找不含子类实例 — 显式可查) /
#       B6 同名 class 跨 package (继承 class 域 D5 冲突边界) /
#       C5 同名 cg (查询按名返回所有定义)
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.covergroup_extractor import CovergroupExtractor  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _cgs(src):
    return CovergroupExtractor({'test.sv': src}).extract()


def _tracer(src):
    tr = UnifiedTracer(sources={'test.sv': src}, log_level='ERROR')
    tr.build_graph(use_cache=False, target_module='top')
    return tr


class TestExtractionAdversarial(unittest.TestCase):
    """A 组: 引用收集盲点 (修 + 锁行为)"""

    def test_user_type_cast_no_type_ref(self):
        """[A2 修] my_t'(w): 类型名 my_t 不是信号 — 只收 w"""
        src = '''module top(input logic clk);
    logic [7:0] w;
    typedef logic [7:0] my_t;
    covergroup cg @(posedge clk);
      cp: coverpoint my_t'(w);
    endgroup
  endmodule'''
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual([s.name for s in cp.sampled], ['w'])

    def test_keyword_cast_still_ok(self):
        """unsigned'(w) 关键字 cast 不回归"""
        src = '''module top(input logic clk);
    logic [7:0] w;
    covergroup cg @(posedge clk);
      cp: coverpoint unsigned'(w);
    endgroup
  endmodule'''
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual([s.name for s in cp.sampled], ['w'])

    def test_anonymous_coverpoint(self):
        """无标号 cp (真实常见): 不丢不崩, 采样正确"""
        src = '''module top(input logic clk, input logic [7:0] din);
    covergroup cg @(posedge clk);
      coverpoint din { bins lo[] = {[0:100]}; }
    endgroup
  endmodule'''
        cg = _cgs(src)[0]
        self.assertEqual(len(cg.coverpoints), 1)
        cp = cg.coverpoints[0]
        self.assertEqual([(s.name, s.select) for s in cp.sampled], [('din', '')])

    def test_nested_func_and_system_call(self):
        """嵌套函数 + $countones: callee 全不泄漏, 实参保留"""
        src = '''module top(input logic clk, input logic [7:0] din);
    logic [7:0] q;
    function logic [7:0] f1(logic [7:0] v); return v + 1; endfunction
    function logic [7:0] f2(logic [7:0] v); return f1(v); endfunction
    covergroup cg @(posedge clk);
      cp: coverpoint f2(din) + $countones(q);
    endgroup
  endmodule'''
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual([s.name for s in cp.sampled], ['din', 'q'])

    def test_iff_control_excluded(self):
        """iff 使能不进采样引用"""
        src = '''module top(input logic clk, input logic [7:0] din, input logic en);
    covergroup cg @(posedge clk);
      cp: coverpoint din iff (en == 1);
    endgroup
  endmodule'''
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual([s.name for s in cp.sampled], ['din'])

    def test_partial_ctor_new_rules(self):
        """[B3] ctor 只 new cg_a → cg_a ctor_new / cg_b uninstantiated"""
        src = '''class packet;
    rand bit [7:0] a;
    rand bit [7:0] b;
    covergroup cg_a;
      cp: coverpoint a;
    endgroup
    covergroup cg_b;
      cp: coverpoint b;
    endgroup
    function new();
      cg_a = new();
    endfunction
  endclass
  module top; packet p = new(); endmodule'''
        rules = {(c.name, c.in_class): c.instance_rule for c in _cgs(src)}
        self.assertEqual(rules, {
            ('cg_a', 'packet'): 'ctor_new',
            ('cg_b', 'packet'): 'uninstantiated',
        })


class TestQueryAdversarial(unittest.TestCase):
    """C 组: 查询盲点 (修 + 边界锁行为)"""

    C4_SRC = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(); cg = new(); endfunction
  endclass
  module top;
    packet p = new();
  endmodule'''

    def test_wrong_instance_missing(self):
        """[C4 修] instance='top.nope' (非该类实例) → missing, 不造 bogus id"""
        tr = _tracer(self.C4_SRC)
        infos = tr.trace_covergroup_sampling('cg', instance='top.nope')
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].sampled, [])
        self.assertEqual(infos[0].missing, ['addr'])

    def test_good_instance_still_works(self):
        tr = _tracer(self.C4_SRC)
        infos = tr.trace_covergroup_sampling('cg', instance='top.p')
        self.assertEqual(infos[0].sampled, ['top.p.addr'])

    def test_submodule_cg_q1_q2(self):
        """[C1] 子模块 cg: host=top.u_sub → Q1 采样 id 正确 + Q2 反向"""
        src = '''module sub(input bit clk, input logic [7:0] vin, output logic [7:0] vout);
    logic [7:0] mid;
    assign mid = vin + 1;
    assign vout = mid;
    covergroup cg_sub @(posedge clk);
      cp: coverpoint mid;
    endgroup
  endmodule
  module top(input bit clk, input logic [7:0] din);
    logic [7:0] out;
    sub u_sub(.clk(clk), .vin(din), .vout(out));
  endmodule'''
        tr = _tracer(src)
        infos = tr.trace_covergroup_sampling('cg_sub')
        self.assertEqual(infos[0].sampled, ['top.u_sub.mid'])
        self.assertIn('top.din', infos[0].drivers)
        matches = [(m.cp_name, m.host_module) for m in tr.trace_coverpoints('top.u_sub.mid')]
        self.assertEqual(matches, [('cp', 'top.u_sub')])

    def test_select_bit_id_graceful(self):
        """[C2] 位级 select id 查询空答 (cp 引用 = 基信号粒度); base id 命中"""
        src = '''module top(input bit clk, input logic [7:0] din);
    covergroup cg @(posedge clk);
      cp: coverpoint din[3:0];
    endgroup
  endmodule'''
        tr = _tracer(src)
        self.assertEqual(tr.trace_coverpoints('top.din[3]'), [])
        matches = tr.trace_coverpoints('top.din')
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].select, '[3:0]')

    def test_same_name_cg_module_and_class(self):
        """[C5 边界] module + class 同名 cg: 按名查询返回全部 (消歧 = 未来)"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp_a: coverpoint addr;
    endgroup
    function new(); cg = new(); endfunction
  endclass
  module top(input bit clk, input logic [7:0] din);
    covergroup cg @(posedge clk);
      cp_m: coverpoint din;
    endgroup
    packet p = new();
  endmodule'''
        tr = _tracer(src)
        infos = tr.trace_covergroup_sampling('cg')
        cps = sorted(i.cp_name for i in infos)
        self.assertEqual(cps, ['cp_a', 'cp_m'])

    def test_extends_base_cg_explicit_instance(self):
        """[B1 边界] 子类实例显式查父类 cg: 放行 (实例集空不拦)"""
        src = '''class base;
    rand bit [7:0] len;
    covergroup cg_len;
      cp: coverpoint len;
    endgroup
    function new(); cg_len = new(); endfunction
  endclass
  class packet extends base;
    rand bit [7:0] addr;
  endclass
  module top; packet p = new(); endmodule'''
        tr = _tracer(src)
        infos = tr.trace_covergroup_sampling('cg_len', instance='top.p')
        self.assertEqual(infos[0].sampled, ['top.p.len'])
        # auto 路径: base 无直接实例 → missing (子类实例枚举 = 未来)
        infos = tr.trace_covergroup_sampling('cg_len')
        self.assertEqual(infos[0].sampled, [])


class TestAdvancedForms(unittest.TestCase):
    """X 组 (iter_169): 高级形态验证 — typedef 前置 / option 语句 / class
    cross / $rose 边沿 / enum 成员 / static 成员"""

    def test_typedef_forward_decl_class(self):
        """typedef fwd + 后定义: 全链 (提取/图/方法调用/Q1) 正常"""
        src = (
            "typedef class packet;\n"
            "class packet;\n"
            "  rand bit [7:0] data;\n"
            "  covergroup cg;\n"
            "    cp: coverpoint data;\n"
            "  endgroup\n"
            "  function new(); cg = new(); endfunction\n"
            "  function void set(input bit [7:0] d);\n"
            "    data = d;\n"
            "  endfunction\n"
            "endclass\n"
            "module top(input bit clk, input bit [7:0] din);\n"
            "  packet p = new();\n"
            "  always_ff @(posedge clk) p.set(din);\n"
            "endmodule\n")
        tr = _tracer(src)
        infos = tr.trace_covergroup_sampling('cg')
        self.assertEqual(infos[0].sampled, ['top.p.data'])
        self.assertIn('top.din', infos[0].drivers)

    def test_option_statements_in_cg_body(self):
        """cg 体内 option/type_option 语句: 不产生幽灵 cp, 采样正常"""
        src = (
            "module top(input logic clk, input logic [7:0] din);\n"
            "  covergroup cg @(posedge clk);\n"
            "    option.auto_bin_max = 2;\n"
            "    type_option.weight = 1;\n"
            "    cp: coverpoint din { bins hi[] = {[128:255]}; }\n"
            "  endgroup\n"
            "endmodule\n")
        cg = _cgs(src)[0]
        self.assertEqual(len(cg.coverpoints), 1)
        self.assertEqual([s.name for s in cg.coverpoints[0].sampled], ['din'])

    def test_class_cross_no_crash(self):
        """class 内 cross: 提取正常不崩"""
        src = (
            "class packet;\n"
            "  rand bit [7:0] addr;\n"
            "  rand bit [1:0] mode;\n"
            "  covergroup cg;\n"
            "    cp_a: coverpoint addr;\n"
            "    cp_m: coverpoint mode;\n"
            "    cross cp_a, cp_m;\n"
            "  endgroup\n"
            "  function new(); cg = new(); endfunction\n"
            "endclass\n"
            "module top; packet p = new(); endmodule\n")
        cgs = _cgs(src)
        cg = [c for c in cgs if c.name == 'cg'][0]
        self.assertEqual([cp.name for cp in cg.coverpoints], ['cp_a', 'cp_m'])
        self.assertTrue(cg.crosses)

    def test_edge_expr_coverpoint(self):
        """$rose(din) 边沿表达式: 采样引用 = din (edge 函数不泄漏)"""
        src = (
            "module top(input logic clk, input logic [7:0] din);\n"
            "  covergroup cg @(posedge clk);\n"
            "    cp: coverpoint $rose(din);\n"
            "  endgroup\n"
            "endmodule\n")
        cp = _cgs(src)[0].coverpoints[0]
        self.assertEqual([s.name for s in cp.sampled], ['din'])

    def test_enum_member_sampling(self):
        """enum 类型成员采样: class_prop 引用正确"""
        src = (
            "class packet;\n"
            "  typedef enum { IDLE, RUN, DONE } state_t;\n"
            "  state_t st;\n"
            "  covergroup cg;\n"
            "    cp: coverpoint st;\n"
            "  endgroup\n"
            "  function new(); cg = new(); endfunction\n"
            "endclass\n"
            "module top; packet p = new(); endmodule\n")
        cgs = _cgs(src)
        cg = [c for c in cgs if c.name == 'cg'][0]
        self.assertEqual([(s.name, s.kind, s.host) for s in cg.coverpoints[0].sampled],
                         [('st', 'class_prop', 'packet')])

    def test_static_member_explicit_instance(self):
        """static 成员 + 多实例: auto 歧义 missing (正确), 显式实例可用"""
        src = (
            "class packet;\n"
            "  static int count;\n"
            "  rand bit [7:0] data;\n"
            "  covergroup cg;\n"
            "    cp: coverpoint data;\n"
            "  endgroup\n"
            "  function new(); cg = new(); endfunction\n"
            "  function void set(input bit [7:0] d);\n"
            "    data = d;\n"
            "    count++;\n"
            "  endfunction\n"
            "endclass\n"
            "module top(input bit clk, input bit [7:0] din);\n"
            "  packet p1 = new();\n"
            "  packet p2 = new();\n"
            "  always_ff @(posedge clk) p1.set(din);\n"
            "endmodule\n")
        tr = _tracer(src)
        infos = tr.trace_covergroup_sampling('cg')
        self.assertEqual(infos[0].sampled, [], "双实例歧义 → auto missing")
        infos = tr.trace_covergroup_sampling('cg', instance='top.p1')
        self.assertEqual(infos[0].sampled, ['top.p1.data'])
        self.assertIn('top.din', infos[0].drivers)


if __name__ == '__main__':
    unittest.main()
