"""
[iter_095] T9: class OOP 1:1 truth

1:1 truth 金标准: class 定义/实例化/方法体赋值的精确图结构 —
CLASS / CLASS_PROPERTY / CLASS_INSTANCE 节点 + IS_INSTANCE_OF / CONSTRAINS /
方法体成员 DRIVER 边。任何 class_graph_builder 逻辑变化导致偏离时此测试失败。

Fixture: golden_dataflow_35_class_oop.sv
    class packet (成员 addr/data, task set_addr: addr=a; data=addr)
    module top: packet pkt = new(); pkt.set_addr(din);

1:1 预期 (实测于 iter_095):
- 5 节点: packet / packet.addr / packet.data / top.pkt / top.din
- 4 边: packet→成员 CONSTRAINS ×2, top.pkt→packet IS_INSTANCE_OF,
  packet.addr→packet.data DRIVER (iter_075 方法体赋值)
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"


def _build_graph(fn: str):
    path = FIXTURE_DIR / fn
    tracer = UnifiedTracer(sources={str(path): path.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


class TestClassOopTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_35_class_oop: class 结构"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_35_class_oop.sv")

    def test_node_set_exact(self):
        """节点集精确: CLASS + 2 PROPERTY + CLASS_INSTANCE + din."""
        expected = {"packet", "packet.addr", "packet.data", "top.pkt", "top.din"}
        self.assertEqual(set(self.g.nodes()), expected, "class 节点集偏离")

    def test_node_kinds(self):
        """节点 kind: packet=CLASS, 成员=CLASS_PROPERTY, pkt=CLASS_INSTANCE."""
        g = self.g
        self.assertEqual(g.get_node("packet").kind.name, "CLASS")
        self.assertEqual(g.get_node("packet.addr").kind.name, "CLASS_PROPERTY")
        self.assertEqual(g.get_node("packet.data").kind.name, "CLASS_PROPERTY")
        self.assertEqual(g.get_node("top.pkt").kind.name, "CLASS_INSTANCE")

    def test_edge_set_exact(self):
        """边集精确: CONSTRAINS ×2 + IS_INSTANCE_OF + 方法体 DRIVER."""
        expected = {
            ("packet", "packet.addr", "CONSTRAINS"),
            ("packet", "packet.data", "CONSTRAINS"),
            ("top.pkt", "packet", "IS_INSTANCE_OF"),
            ("packet.addr", "packet.data", "DRIVER"),   # 方法体 data = addr
        }
        actual = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                actual.add((s, d, e.kind.name))
        self.assertEqual(actual, expected, "class 边集偏离")

    def test_method_body_member_driver(self):
        """iter_075 修复锁定: 方法体 data = addr 生成成员间 DRIVER 边."""
        e = self.g.get_edge("packet.addr", "packet.data")
        self.assertIsNotNone(e, "方法体成员赋值边应存在 (iter_075)")
        self.assertEqual(e.kind.name, "DRIVER")


if __name__ == "__main__":
    unittest.main()


class TestClassMethodCallChain(unittest.TestCase):
    """[iter_151 C1] class 方法调用链 — 方法体成员赋值展开到实例属性.

    架构决策 D2: 复用 module task/function 调用机制 (receiver 解析 +
    _find_class_method + internal_drivers 成员展开), 无第二套调用语义。
    p.set(din) (always_ff 内) → 方法体 data=d → DRIVER din→top.p.data。
    """

    SRC = '''class packet;
  bit [7:0] addr;
  bit [7:0] data;
  function void set(input bit [7:0] d);
    data = d;
    addr = d + 1;
  endfunction
endclass
module top (input bit clk, input bit [7:0] din);
  packet p = new();
  always_ff @(posedge clk) begin
    p.set(din);
  end
endmodule
'''

    def _tracer(self, src):
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        return tr

    def test_method_call_drives_instance_property(self):
        """p.set(din) → 方法体 data=d → fanin(p.data) 含 din (C1 前为空)."""
        tr = self._tracer(self.SRC)
        ids = {r.id for r in tr.trace_fanin('top.p.data')}
        self.assertIn('top.din', ids,
                      f"方法调用实参应驱动实例属性, 实际 {ids}")

    def test_multi_member_assignment(self):
        """方法体内多成员 (data/addr) 都展开 (addr = d+1 → din)."""
        tr = self._tracer(self.SRC)
        ids = {r.id for r in tr.trace_fanin('top.p.addr')}
        self.assertIn('top.din', ids,
                      f"addr (d+1) 也应追到 din, 实际 {ids}")

    def test_uninvoked_method_no_edges(self):
        """方法定义但**不被调用** → 不展开 (实例属性无方法驱动)."""
        src = self.SRC.replace(
            "  always_ff @(posedge clk) begin\n    p.set(din);\n  end\nendmodule",
            "endmodule")
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        # data 仍无驱动 (方法没被调用)
        # (若 RTL 无其他赋值 → fanin 空; 有约束等但非数据源)
        has_driver = any(
            d == 'top.p.data'
            and any(e.kind.name == 'DRIVER' and e.assign_type == 'blocking'
                   for e in g._edge_data.get((s, d), []))
            for s, d in g.edges())
        self.assertFalse(has_driver,
                         "未调用的方法不应展开成员驱动边")

    def test_module_function_still_works(self):
        """module task/function 调用路径不回归 (receiver=None)."""
        src = '''module top (input bit [7:0] din, output bit [7:0] out);
  function void set_data(input bit [7:0] d, output bit [7:0] o);
    o = d;
  endfunction
  always_comb begin
    set_data(din, out);
  end
endmodule
'''
        tr = self._tracer(src)
        ids = {r.id for r in tr.trace_fanin('top.out')}
        self.assertIn('top.din', ids,
                      f"module function output 参数链应保持, 实际 {ids}")


if __name__ == "__main__":
    unittest.main()


class TestClassInstanceTypeBridge(unittest.TestCase):
    """[iter_152 C2] 实例↔类型级桥 + 查询语义 (架构决策 D3).

    D3: 类型级 (packet.data) = 结构宿主 (trace_class_members), 实例级
    (top.p1.data) = 数据端点 (fanin); 桥 = IS_INSTANCE_OF 反向查询
    (trace_class_instances) + 成员实例 (trace_member_instances, 仅图内
    已建节点 — 未使用实例成员不臆造)。
    """

    SRC = '''class packet;
  rand bit [7:0] addr;
  bit [7:0] data;
  constraint c_addr { addr < 16; }
  function void set(input bit [7:0] d);
    data = d;
  endfunction
endclass
module top (input bit clk, input bit [7:0] din);
  packet p1 = new();
  packet p2 = new();
  always_ff @(posedge clk) begin
    p1.set(din);
  end
endmodule
'''

    def setUp(self):
        self.tr = UnifiedTracer(sources={'t.sv': self.SRC}, log_level='ERROR')
        self.tr.build_graph(use_cache=False, target_module='top')

    def test_type_level_members_structural(self):
        """类型级成员 = 结构参考 (属性/约束块/表达式)."""
        ids = {n.id for n in self.tr.trace_class_members('packet')}
        self.assertIn('packet.addr', ids)
        self.assertIn('packet.data', ids)
        self.assertIn('packet.c_addr', ids)

    def test_class_instances_reverse(self):
        """类型 → 实例 (IS_INSTANCE_OF 反向): p1/p2 都在."""
        ids = {n.id for n in self.tr.trace_class_instances('packet')}
        self.assertEqual(ids, {'top.p1', 'top.p2'})

    def test_member_instances_only_built(self):
        """类型属性 → 已建实例属性: p1.data 在 (被 set 使用), p2.data 不臆造."""
        ids = {n.id for n in self.tr.trace_member_instances('packet.data')}
        self.assertEqual(ids, {'top.p1.data'},
                         "仅返回图内已存在的实例成员节点")
        # addr 未被 RTL 使用 → 无实例成员节点
        self.assertEqual(self.tr.trace_member_instances('packet.addr'), [])

    def test_data_endpoint_is_instance(self):
        """D3: 数据端点 = 实例 (fanin(p1.data) 通); 类型级是结构非数据."""
        ids = {r.id for r in self.tr.trace_fanin('top.p1.data')}
        self.assertIn('top.din', ids,
                      "实例属性数据流应通 (方法调用链 C1)")


if __name__ == "__main__":
    unittest.main()


class TestConstraintTracing(unittest.TestCase):
    """[iter_153 C3] constraint 语义查询 (架构决策 D4: 独立 tracer).

    约束 = 声明式关系 (CONSTRAINS/HAS_*), 不走数据 fanin —
    trace_constraints(prop) 回答 "属性受哪些约束 / 约束涉及哪些变量"。
    """

    SRC = '''class packet;
  rand bit [7:0] addr;
  rand bit [7:0] data;
  bit [3:0] tag;
  constraint c_addr { addr inside {[0:15]}; addr != data; }
  constraint c_data_if { if (tag > 3) data < 200; else data > 10; }
  constraint c_range { addr > 0; }
endclass
module top (input bit clk, input bit [7:0] din);
  packet p = new();
  always_ff @(posedge clk) begin
    p.addr <= din;
  end
endmodule
'''

    def setUp(self):
        self.tr = UnifiedTracer(sources={'t.sv': self.SRC}, log_level='ERROR')
        self.tr.build_graph(use_cache=False, target_module='top')

    def test_type_prop_constraints(self):
        """packet.addr 受 c_addr (含 data 交叉引用) + c_range."""
        res = self.tr.trace_constraints('packet.addr')
        blocks = {r.block_id for r in res}
        self.assertEqual(blocks, {'packet.c_addr', 'packet.c_range'})
        c_addr = next(r for r in res if r.block_id == 'packet.c_addr')
        self.assertIn('packet.addr', c_addr.vars)
        self.assertIn('packet.data', c_addr.vars)  # addr != data 交叉

    def test_if_constraint_condition_var(self):
        """c_data_if: data 受约束且条件变量 tag 识别."""
        res = self.tr.trace_constraints('packet.data')
        c_if = next((r for r in res if r.block_id == 'packet.c_data_if'), None)
        self.assertIsNotNone(c_if, "data 应受 c_data_if 约束")
        self.assertIn('packet.data', c_if.vars)
        self.assertIn('packet.tag', c_if.conditions)

    def test_instance_prop_resolves_to_type(self):
        """实例属性 top.p.addr (REG) 自动解析类型级约束 (D3: 约束在类型作用于实例)."""
        res = self.tr.trace_constraints('top.p.addr')
        blocks = {r.block_id for r in res}
        self.assertEqual(blocks, {'packet.c_addr', 'packet.c_range'},
                         "实例属性应查得同类型级约束")

    def test_constraint_not_data_fanin(self):
        """约束关系不进数据 fanin (D4/iter_139): fanin(p.addr) 只含数据源."""
        ids = {r.id for r in self.tr.trace_fanin('top.p.addr')}
        self.assertNotIn('packet.c_addr', ids,
                         "约束块不应作为数据驱动源")
        self.assertIn('top.din', ids)


if __name__ == "__main__":
    unittest.main()


class TestClassKindSemantics(unittest.TestCase):
    """[iter_154 C4] 查询层 class kind 语义 + 冲突检测 (架构决策 D5).

    - 类型级 CLASS_PROPERTY = 结构宿主非数据端点: fanin 空 (模板方法体
      DRIVER 不作实例驱动答案), 实例数据流不受影响
    - 同名类型级 class 定义 (跨文件): 冲突显式告警 + 首定义保留
    - get_classes 按对象身份去重 (同名不同定义暴露给冲突检测)
    """

    SRC = '''class packet;
  bit [7:0] addr;
  bit [7:0] data;
  function void copy();
    data = addr;
  endfunction
endclass
module top (input bit clk, input bit [7:0] din);
  packet p = new();
  always_ff @(posedge clk) begin
    p.addr <= din;
  end
endmodule
'''

    def setUp(self):
        self.tr = UnifiedTracer(sources={'t.sv': self.SRC}, log_level='ERROR')
        self.tr.build_graph(use_cache=False, target_module='top')

    def test_type_prop_fanin_empty(self):
        """类型级属性非数据端点 (D3): fanin(packet.data) 空 (模板驱动不作答)."""
        self.assertEqual(self.tr.trace_fanin('packet.data'), [],
                         "类型级属性 fanin 应空 (模板非实例驱动)")
        self.assertEqual(self.tr.trace_fanin('packet.data', depth=1), [])

    def test_instance_fanin_kept(self):
        """实例数据流不受类型级守卫影响."""
        ids = {r.id for r in self.tr.trace_fanin('top.p.addr')}
        self.assertIn('top.din', ids)

    def test_duplicate_class_warns_and_keeps_first(self):
        """同名 class 跨文件: 冲突告警 + 首定义保留 (D5 禁止静默)."""
        import io
        import logging
        from trace.unified_tracer import UnifiedTracer as UT
        src2 = '''class packet;
  bit [15:0] b;
endclass
'''
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        old_lvl = root.level
        root.setLevel(logging.WARNING)
        root.addHandler(handler)
        try:
            tr = UT(sources={'a.sv': self.SRC, 'b.sv': src2},
                    log_level='WARNING')
            g = tr.build_graph(use_cache=False, target_module='top')
        finally:
            root.removeHandler(handler)
            root.setLevel(old_lvl)
        self.assertIn("同名 class 定义冲突", stream.getvalue(),
                      "冲突应显式告警 (非静默)")
        self.assertIn('packet.addr', g.nodes(), "首定义成员保留")
        self.assertNotIn('packet.b', g.nodes(), "第二定义被跳过 (告警可见)")


if __name__ == "__main__":
    unittest.main()


class TestClassMethodAdversarial(unittest.TestCase):
    """[iter_156] class 对抗回归 — 多实例隔离 / module 同名优先 / 函数返回.

    E1: p1/p2 同方法各驱动各属性 (实例隔离)
    E11: module 同名 function 不抢 class 方法 (receiver 优先)
    E4: 函数返回值 (assign out = p.get(); return data → receiver.data)
    """

    def test_multi_instance_isolation(self):
        """E1: p1.set(d1)/p2.set(d2) 各隔离."""
        src = '''class packet;
  bit [7:0] data;
  function void set(input bit [7:0] d);
    data = d;
  endfunction
endclass
module top (input bit clk, input bit [7:0] d1, d2);
  packet p1 = new();
  packet p2 = new();
  always_ff @(posedge clk) begin
    p1.set(d1);
    p2.set(d2);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        self.assertIn('top.d1', {r.id for r in tr.trace_fanin('top.p1.data')})
        self.assertNotIn('top.d2', {r.id for r in tr.trace_fanin('top.p1.data')})
        self.assertIn('top.d2', {r.id for r in tr.trace_fanin('top.p2.data')})

    def test_module_same_name_not_steal_class_method(self):
        """E11: module 同名 function 不抢 class 方法 (iter_156 修)."""
        src = '''class packet;
  bit [7:0] data;
  function void set(input bit [7:0] d);
    data = d;
  endfunction
endclass
module top (input bit clk, input bit [7:0] d);
  packet p = new();
  function void set(input bit [7:0] x); endfunction
  always_ff @(posedge clk) begin
    p.set(d);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        self.assertIn('top.d', {r.id for r in tr.trace_fanin('top.p.data')},
                      "class 方法调用应优先 class 方法 (receiver 明确)")

    def test_function_return_drives_lhs(self):
        """E4: assign out = p.get() (return data) → out 由 p.data 驱动 (无假节点)."""
        src = '''class packet;
  bit [7:0] data;
  function void set(input bit [7:0] d);
    data = d;
  endfunction
  function bit [7:0] get();
    return data;
  endfunction
endclass
module top (input bit clk, input bit [7:0] d, output bit [7:0] out);
  packet p = new();
  always_ff @(posedge clk) begin
    p.set(d);
  end
  assign out = p.get();
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.out')}
        self.assertIn('top.p.data', ids,
                      f"函数返回值应连 receiver 成员, 实际 {ids}")
        self.assertIn('top.d', ids, "链到底应到 d")
        self.assertNotIn('top.get', {s for s, _ in tr._graph.edges()},
                         "不应有 module 隐式返回假节点 top.get")


if __name__ == "__main__":
    unittest.main()


class TestClassMethodExtras(unittest.TestCase):
    """[iter_157] class 方法缺口修复回归 — E7 继承 / E8 数组 / E3 跨实例参数.

    E7: sub_packet extends packet, 子类实例调父类 set → 沿 extends 链查找
    E8: class 数组 arr[0].set(d0) → 数组元素实例隔离
    E3: p1.copy(p2) (data = other.data) → 跨实例成员实参映射
    """

    def test_inherited_method_lookup(self):
        """E7: 父类方法经 extends 链可查 (子类实例调用)."""
        src = '''class packet;
  bit [7:0] data;
  function void set(input bit [7:0] d);
    data = d;
  endfunction
endclass
class sub_packet extends packet;
  bit [7:0] extra;
endclass
module top (input bit clk, input bit [7:0] d);
  sub_packet p = new();
  always_ff @(posedge clk) begin
    p.set(d);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        self.assertIn('top.d', {r.id for r in tr.trace_fanin('top.p.data')},
                      "继承方法 (父类 set) 应展开到子类实例属性")

    def test_class_array_element_isolation(self):
        """E8: arr[0].set(d0) / arr[1].set(d1) 各驱动各元素."""
        src = '''class packet;
  bit [7:0] data;
  function void set(input bit [7:0] d);
    data = d;
  endfunction
endclass
module top (input bit clk, input bit [7:0] d0, d1);
  packet arr[2];
  always_ff @(posedge clk) begin
    arr[0].set(d0);
    arr[1].set(d1);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids0 = {r.id for r in tr.trace_fanin('top.arr[0].data')}
        ids1 = {r.id for r in tr.trace_fanin('top.arr[1].data')}
        self.assertIn('top.d0', ids0)
        self.assertNotIn('top.d1', ids0)
        self.assertIn('top.d1', ids1)
        self.assertNotIn('top.d0', ids1)

    def test_cross_instance_member_arg(self):
        """E3: p1.copy(p2) (data = other.data) → p1.data ← p2.data ← d."""
        src = '''class packet;
  bit [7:0] data;
  function void copy(input packet other);
    data = other.data;
  endfunction
endclass
module top (input bit clk, input bit [7:0] d);
  packet p1 = new();
  packet p2 = new();
  always_ff @(posedge clk) begin
    p2.data <= d;
    p1.copy(p2);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids1 = {r.id for r in tr.trace_fanin('top.p1.data')}
        self.assertIn('top.p2.data', ids1,
                      "copy 应展开 other.data → 实参 p2.data")
        self.assertIn('top.d', ids1, "链到底应到 d")


if __name__ == "__main__":
    unittest.main()


class TestNestedMethodCall(unittest.TestCase):
    """[iter_158] E5/E13 方法内嵌套调用展开 (静态限定).

    E5: set 内调 helper(d) (隐式 this) + 成员链 data=tmp → 全链到底
    E13: set_inner 内调 i.set(v) (成员 receiver, 组合 class) → p.i.val
    不建模 (动态): virtual override / 句柄运行时重指向 (文档标记).
    """

    def test_nested_implicit_this_call(self):
        """E5: helper(d) 隐式 this → p.tmp ← d; data=tmp 成员链 → p.data."""
        src = '''class packet;
  bit [7:0] data;
  bit [7:0] tmp;
  function void helper(input bit [7:0] x);
    tmp = x;
  endfunction
  function void set(input bit [7:0] d);
    helper(d);
    data = tmp;
  endfunction
endclass
module top (input bit clk, input bit [7:0] d);
  packet p = new();
  always_ff @(posedge clk) begin
    p.set(d);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids_data = {r.id for r in tr.trace_fanin('top.p.data')}
        self.assertIn('top.d', ids_data,
                      f"data 应经成员链+helper 到底, 实际 {ids_data}")
        ids_tmp = {r.id for r in tr.trace_fanin('top.p.tmp')}
        self.assertIn('top.d', ids_tmp, "helper 展开应驱动 tmp")
        # 无垃圾节点 (symbol 对象 str)
        self.assertFalse(any('Symbol(' in x for x in ids_data | ids_tmp),
                         "不应有 symbol 对象垃圾节点")

    def test_nested_member_receiver_call(self):
        """E13: i.set(v) — receiver 是外层实例的 class 成员 (组合)."""
        src = '''class inner;
  bit [7:0] val;
  function void set(input bit [7:0] v);
    val = v;
  endfunction
endclass
class packet;
  inner i;
  function void set_inner(input bit [7:0] v);
    i.set(v);
  endfunction
endclass
module top (input bit clk, input bit [7:0] d);
  packet p = new();
  always_ff @(posedge clk) begin
    p.set_inner(d);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.p.i.val')}
        self.assertIn('top.d', ids,
                      f"组合成员 i.set 应链到底, 实际 {ids}")


if __name__ == "__main__":
    unittest.main()


class TestCompositeArrayAndDefaults(unittest.TestCase):
    """[iter_159] 组合数组 receiver + 默认参数语义.

    - 组合数组: packet.bus[2] (inner 数组), set_bus 内 bus[0].set(v) →
      静态 receiver (成员数组 + 常量索引) → p.bus[0].val 链到底
    - 默认参数无实参 (p.set()): 数据源为默认常量 — 无信号可追, 查询空
      (常量驱动不建假信号源), 不崩
    """

    def test_composite_array_member_receiver(self):
        src = '''class inner;
  bit [7:0] val;
  function void set(input bit [7:0] v);
    val = v;
  endfunction
endclass
class packet;
  inner bus[2];
  function void set_bus(input bit [7:0] v);
    bus[0].set(v);
  endfunction
endclass
module top (input bit clk, input bit [7:0] d);
  packet p = new();
  always_ff @(posedge clk) begin
    p.set_bus(d);
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        tr.build_graph(use_cache=False, target_module='top')
        ids = {r.id for r in tr.trace_fanin('top.p.bus[0].val')}
        self.assertIn('top.d', ids,
                      f"组合数组元素 receiver 应链到底, 实际 {ids}")

    def test_default_param_no_arg_no_crash(self):
        """E15: p.set() 无实参用默认常量 — 不崩; 常量源无信号可追 (空答合理)."""
        src = '''class packet;
  bit [7:0] data;
  function void set(input bit [7:0] d = 8'h5);
    data = d;
  endfunction
endclass
module top (input bit clk);
  packet p = new();
  always_ff @(posedge clk) begin
    p.set();
  end
endmodule
'''
        tr = UnifiedTracer(sources={'t.sv': src}, log_level='ERROR')
        g = tr.build_graph(use_cache=False, target_module='top')
        # data 由默认常量驱动 — 无信号源; 且无垃圾节点 (Symbol(...) 等)
        ids = {r.id for r in tr.trace_fanin('top.p.data')}
        for n in g.nodes():
            self.assertNotIn('Symbol(', n, f"不应有 symbol 垃圾节点: {n}")


if __name__ == "__main__":
    unittest.main()
