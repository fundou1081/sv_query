# test_class_oop.py - Class OOP 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [iter_064 2026-08-29] 行为断言加强: 保留原有"节点存在"断言, 补充
# IS_INSTANCE_OF (top.obj → my_cls) + MEMBER_SELECT (top.p.addr → top.p) +
# DRIVER (top.p.addr → top.out) 三类边断言 — 这是 OOP 域真正可断言的行为金标准.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


class TestClassOOP(unittest.TestCase):
    """Class OOP 信号追踪测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_class_basic(self):
        """[Golden] Class 定义与实例化

        RTL:
        class my_cls;
            logic [7:0] data;
        endclass

        module top;
            my_cls obj = new();
        endmodule

        行为金标准 (class OOP 域):
          - top.obj 节点存在 (CLASS_INSTANCE)
          - my_cls 节点存在 (CLASS)
          - my_cls.data 节点存在 (CLASS_PROPERTY)
          - top.obj → my_cls  IS_INSTANCE_OF 边 (实例→类型)
          - my_cls → my_cls.data  CONSTRAINS 边 (类→成员)
        """
        source = '''class my_cls;
    logic [7:0] data;
endclass

module top;
    my_cls obj = new();
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 原断言
        self.assertIsNotNone(tracer.get_graph())

        graph = tracer.get_graph()
        nodes = list(graph.nodes())

        # 验证: obj 节点存在
        self.assertTrue(any('obj' in n for n in nodes),
            f"obj not found in {nodes}")

        # [iter_064] 行为断言: 完整 OOP 拓扑 — 类型实例化 + 类成员
        self.assertIn('top.obj', nodes, "top.obj CLASS_INSTANCE 节点应存在")
        self.assertIn('my_cls', nodes, "my_cls CLASS 节点应存在")
        self.assertIn('my_cls.data', nodes,
                      "my_cls.data CLASS_PROPERTY 节点应存在")

        # 实例 → 类的 IS_INSTANCE_OF 边
        edge_inst = graph.get_edge('top.obj', 'my_cls')
        self.assertIsNotNone(edge_inst, "实例化 new() 应生成 top.obj → my_cls 边")
        # 类 → 成员的 CONSTRAINS 边 (类管控其成员属性)
        edge_member = graph.get_edge('my_cls', 'my_cls.data')
        self.assertIsNotNone(edge_member, "class 应管控其成员 my_cls.data")

    def test_class_member_access(self):
        """[Golden] Class 成员访问

        RTL:
        class packet;
            logic [31:0] addr;
        endclass

        module top;
            packet p = new();
            logic [31:0] out;
            assign out = p.addr;
        endmodule

        行为金标准:
          - 节点: top.p, top.out, top.p.addr, packet, packet.addr
          - top.p.addr → top.out  DRIVER 边 (assign 语句生成)
          - top.p.addr → top.p    MEMBER_SELECT 边 (实例成员归属)
        """
        source = '''class packet;
    logic [31:0] addr;
endclass

module top;
    packet p = new();
    logic [31:0] out;
    assign out = p.addr;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 原断言
        self.assertIsNotNone(tracer.get_graph())

        graph = tracer.get_graph()
        nodes = list(graph.nodes())

        # 验证: p.addr 或 addr 节点存在
        has_addr = any('addr' in n or 'p.addr' in n for n in nodes)
        self.assertTrue(has_addr,
            f"p.addr not found in {nodes}")

        # [iter_064] 行为断言: OOP 域完整驱动链
        self.assertIn('top.p.addr', nodes,
                      "实例成员节点 top.p.addr 应存在")
        self.assertIn('top.out', nodes, "模块信号 top.out 应存在")

        # assign out = p.addr → top.p.addr 驱动 top.out
        edge_drv = graph.get_edge('top.p.addr', 'top.out')
        self.assertIsNotNone(edge_drv, "成员访问 assign out=p.addr 应生成 DRIVER 边")

        # 成员归属: top.p.addr → top.p (MEMBER_SELECT)
        edge_member = graph.get_edge('top.p.addr', 'top.p')
        self.assertIsNotNone(edge_member,
                             "实例成员应有 top.p.addr → top.p 的 MEMBER_SELECT 归属边")

if __name__ == '__main__':
    unittest.main()
