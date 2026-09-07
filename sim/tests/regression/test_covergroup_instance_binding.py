# test_covergroup_instance_binding.py - Covergroup G2: 实例化绑定 (Q4)
# [G2 iter_163 2026-09-06] 方案 B 第二步:
#   - instance_rule 提取 (module_scope / ctor_new / uninstantiated)
#   - bind_class_covergroups: class cg 定义 × class 实例 → 实例路径绑定 +
#     G1 class_prop ref → 实例 ref (p.addr), Q4 "p.cg 采样 p.addr"
# 决策点 3 (动态=文档): 条件化 new() 存在即 'ctor_new' (分支运行时边界);
# embedded covergroup 只能在新方法赋值 (LRM), 无 new = 实例不活。
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.covergroup_binding import bind_class_covergroups  # noqa: E402
from trace.core.covergroup_extractor import CovergroupExtractor  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _rules(source):
    return {(cg.name, cg.in_class): cg.instance_rule
            for cg in CovergroupExtractor({'test.sv': source}).extract()}


class TestInstanceRules(unittest.TestCase):
    """G2: instance_rule 提取"""

    def test_module_scope(self):
        src = '''module top(input logic clk, input logic din);
    covergroup cg @(posedge clk);
      cp: coverpoint din;
    endgroup
  endmodule'''
        self.assertEqual(_rules(src), {('cg', ''): 'module_scope'})

    def test_class_ctor_new(self):
        """ctor 对成员 cg new() → 每类实例携带 cg 实例"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(); cg = new(); endfunction
  endclass
  module top; endmodule'''
        self.assertEqual(_rules(src), {('cg', 'packet'): 'ctor_new'})

    def test_class_uninstantiated(self):
        """ctor 未 new() 成员 cg → 实例不活 (不静态绑定)"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(); endfunction
  endclass
  module top; endmodule'''
        self.assertEqual(_rules(src), {('cg', 'packet'): 'uninstantiated'})

    def test_class_this_dot_form(self):
        """this.cg = new() 形态同样识别 (赋值目标取最后标识符)"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(); this.cg = new(); endfunction
  endclass
  module top; endmodule'''
        self.assertEqual(_rules(src), {('cg', 'packet'): 'ctor_new'})

    def test_class_conditional_new_docs_boundary(self):
        """条件化 new() (if en) — 分支 = 运行时边界; 存在即 'ctor_new' (决策 3)"""
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(bit en);
      if (en) cg = new();
    endfunction
  endclass
  module top; endmodule'''
        self.assertEqual(_rules(src), {('cg', 'packet'): 'ctor_new'})

    def test_mixed_classes(self):
        """同源多 class + module cg 各自归位"""
        src = '''class a;
    rand bit [7:0] v;
    covergroup cg_a;
      cp: coverpoint v;
    endgroup
    function new(); cg_a = new(); endfunction
  endclass
  class b;
    rand bit [7:0] v;
    covergroup cg_b;
      cp: coverpoint v;
    endgroup
    function new(); endfunction
  endclass
  module top(input logic clk, input logic din);
    covergroup cg_mod @(posedge clk);
      cp: coverpoint din;
    endgroup
  endmodule'''
        rules = _rules(src)
        self.assertEqual(rules, {
            ('cg_a', 'a'): 'ctor_new',
            ('cg_b', 'b'): 'uninstantiated',
            ('cg_mod', ''): 'module_scope',
        })


BIND_SRC = '''class packet;
    rand bit [7:0] addr;
    bit [3:0] tag;
    covergroup cg;
      cp_addr: coverpoint addr;
      cp_tag: coverpoint {addr, tag};
    endgroup
    function new(); cg = new(); endfunction
  endclass
  module top(input logic clk);
    packet p1 = new();
    packet p2 = new();
  endmodule'''


class TestBinding(unittest.TestCase):
    """G2: bind_class_covergroups 纯映射"""

    @classmethod
    def setUpClass(cls):
        cls.cgs = CovergroupExtractor({'test.sv': BIND_SRC}).extract()
        cls.cg = [c for c in cls.cgs if c.name == 'cg'][0]

    def _refs(self, bound):
        return {cp.cp_name: [(s.name, s.select) for s in cp.sampled]
                for cp in bound.coverpoints}

    def test_bind_per_instance(self):
        bounds = bind_class_covergroups(self.cgs, {"packet": ["top.p1", "top.p2"]})
        self.assertEqual([b.instance_path for b in bounds], ["top.p1", "top.p2"])
        for b in bounds:
            refs = self._refs(b)
            # Q4: p.cg 采样 p.addr / p.tag (G1 class_prop ref → 实例 ref)
            self.assertEqual(refs['cp_addr'], [('top.p1.addr' if b.instance_path == 'top.p1'
                                                else 'top.p2.addr', '')])
            self.assertEqual(refs['cp_tag'], [
                (b.instance_path + '.addr', ''),
                (b.instance_path + '.tag', ''),
            ])

    def test_sampled_signals_dedup(self):
        b = bind_class_covergroups(self.cgs, {"packet": ["top.p1"]})[0]
        self.assertEqual(b.sampled_signals, ["top.p1.addr", "top.p1.tag"])

    def test_no_bind_uninstantiated(self):
        src = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp: coverpoint addr;
    endgroup
    function new(); endfunction
  endclass
  module top; packet p = new(); endmodule'''
        cgs = CovergroupExtractor({'test.sv': src}).extract()
        self.assertEqual(bind_class_covergroups(cgs, {"packet": ["top.p"]}), [])

    def test_no_bind_module_scope(self):
        src = '''module top(input logic clk, input logic din);
    covergroup cg @(posedge clk);
      cp: coverpoint din;
    endgroup
  endmodule'''
        cgs = CovergroupExtractor({'test.sv': src}).extract()
        self.assertEqual(bind_class_covergroups(cgs, {}), [])

    def test_unknown_class_instances_no_bind(self):
        self.assertEqual(bind_class_covergroups(self.cgs, {"other": ["top.x"]}), [])


class TestQ4EndToEnd(unittest.TestCase):
    """G2 验收 (Q4): p.cg 采样 p.addr — 绑定 + 主图实例属性贯通.

    链: CovergroupExtractor (cg 定义: cp_addr→addr class_prop host=packet)
    × UnifiedTracer.trace_class_instances (top.p) → 绑定 top.p.cg →
    top.p.addr (图内数据端点, fanin 由 p.set(din) 方法体驱动).

    ⚠️ logic 实参 (4 态→bit 形参 Conversion 壳丢实参) 已在 iter_164 修复 —
    本 fixture 用 logic 端口即该修复的回归覆盖 (原用 bit 规避)。
    """

    SRC = '''class packet;
    rand bit [7:0] addr;
    covergroup cg;
      cp_addr: coverpoint addr;
    endgroup
    function new(); cg = new(); endfunction
    function void set(input bit [7:0] d);
      addr = d;
    endfunction
  endclass
  module top(input logic clk, input logic [7:0] din);
    packet p = new();
    always_ff @(posedge clk) begin
      p.set(din);
    end
  endmodule'''

    def test_q4_chain(self):
        # 单 tracer 顺序: 先无 target 查询 (内部建图), 再 target 建图, 再
        # fanin — iter_164 复测: 连续 build 无状态退化 (P2 原报告系 logic
        # 实参 P1 混淆; P1 修复后本链单 tracer 全程稳定).
        tr = UnifiedTracer(sources={'test.sv': self.SRC}, log_level='ERROR')
        cgs = CovergroupExtractor({'test.sv': self.SRC}).extract()

        cg = [c for c in cgs if c.name == 'cg'][0]
        self.assertEqual((cg.in_class, cg.instance_rule), ('packet', 'ctor_new'))

        insts = {cid: [n.id for n in tr.trace_class_instances(cid)] for cid in ['packet']}
        self.assertEqual(insts, {'packet': ['top.p']})

        bounds = bind_class_covergroups(cgs, insts)
        self.assertEqual(len(bounds), 1)
        b = bounds[0]
        self.assertEqual(b.instance_path, 'top.p')
        # Q4: p.cg 的 cp_addr 采样 p.addr (实例属性)
        self.assertEqual(b.coverpoints[0].cp_name, 'cp_addr')
        self.assertEqual([s.name for s in b.coverpoints[0].sampled], ['top.p.addr'])

        # 贯通: target 建图 (展开方法调用) → p.addr 是图内实例属性数据端点
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.p.addr')}
        self.assertIn('top.din', ids, "p.set(din) 方法体赋值应驱动 p.addr")


if __name__ == '__main__':
    unittest.main()
