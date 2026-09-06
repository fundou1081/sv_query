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
