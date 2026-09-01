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
