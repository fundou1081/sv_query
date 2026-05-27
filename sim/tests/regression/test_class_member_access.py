# test_class_member_access.py - Class 实例成员访问金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
# [铁律18] 负面测试
#
# P0: MEMBER_SELECT 边 + p.addr 追踪
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind


class TestClassMemberAccess(unittest.TestCase):
    """Class 实例成员访问 (p.addr) 信号追踪"""

    def _build_graph(self, source):
        tracer = UnifiedTracer(sources={'test.sv': source})
        return tracer.build_graph(), tracer

    def test_basic_member_access_driver(self):
        """[金标准] p.addr 作为 assign 的 driver

        RTL:
        class packet;
            logic [7:0] addr;
        endclass

        module top;
            packet p = new();
            logic [7:0] out;
            assign out = p.addr;
        endmodule

        预期:
        - top.p.addr 节点存在，类型为 CLASS_INSTANCE_PROPERTY
        - top.p.addr --DRIVER--> top.out
        - top.p.addr --MEMBER_SELECT--> top.p
        - top.p.addr --MEMBER_SELECT--> packet.addr
        """
        source = '''class packet;
    logic [7:0] addr;
endclass

module top;
    packet p = new();
    logic [7:0] out;
    assign out = p.addr;
endmodule'''
        graph, tracer = self._build_graph(source)

        # top.p.addr 节点存在
        p_addr = graph.get_node('top.p.addr')
        self.assertIsNotNone(p_addr, "top.p.addr 节点应存在")
        self.assertEqual(p_addr.kind, NodeKind.CLASS_INSTANCE_PROPERTY,
            "top.p.addr 应为 CLASS_INSTANCE_PROPERTY")

        # DRIVER 边: top.p.addr -> top.out
        driver_edge = graph.get_edge('top.p.addr', 'top.out')
        self.assertIsNotNone(driver_edge, "top.p.addr -> top.out DRIVER 边应存在")
        self.assertEqual(driver_edge.kind, EdgeKind.DRIVER)

        # MEMBER_SELECT 边: top.p.addr -> top.p
        ms_edge = graph.get_edge('top.p.addr', 'top.p')
        self.assertIsNotNone(ms_edge, "top.p.addr -> top.p MEMBER_SELECT 边应存在")
        self.assertEqual(ms_edge.kind, EdgeKind.MEMBER_SELECT)

        # MEMBER_SELECT 边: top.p.addr -> packet.addr (class property)
        ms_class_edge = graph.get_edge('top.p.addr', 'packet.addr')
        self.assertIsNotNone(ms_class_edge, "top.p.addr -> packet.addr MEMBER_SELECT 边应存在")
        self.assertEqual(ms_class_edge.kind, EdgeKind.MEMBER_SELECT)

    def test_multiple_member_access(self):
        """[金标准] 多个成员访问: p.addr 和 p.data

        RTL:
        class packet;
            logic [7:0] addr;
            logic [31:0] data;
        endclass

        module top;
            packet p = new();
            logic [7:0] out_addr;
            logic [31:0] out_data;
            assign out_addr = p.addr;
            assign out_data = p.data;
        endmodule

        预期:
        - top.p.addr 和 top.p.data 都是 CLASS_INSTANCE_PROPERTY
        - 各自有 DRIVER 和 MEMBER_SELECT 边
        """
        source = '''class packet;
    logic [7:0] addr;
    logic [31:0] data;
endclass

module top;
    packet p = new();
    logic [7:0] out_addr;
    logic [31:0] out_data;
    assign out_addr = p.addr;
    assign out_data = p.data;
endmodule'''
        graph, tracer = self._build_graph(source)

        # 两个实例属性节点都存在
        self.assertIsNotNone(graph.get_node('top.p.addr'))
        self.assertIsNotNone(graph.get_node('top.p.data'))
        self.assertEqual(graph.get_node('top.p.addr').kind, NodeKind.CLASS_INSTANCE_PROPERTY)
        self.assertEqual(graph.get_node('top.p.data').kind, NodeKind.CLASS_INSTANCE_PROPERTY)

        # 各自的 DRIVER 边
        self.assertIsNotNone(graph.get_edge('top.p.addr', 'top.out_addr'))
        self.assertIsNotNone(graph.get_edge('top.p.data', 'top.out_data'))

        # 各自的 MEMBER_SELECT 边
        self.assertIsNotNone(graph.get_edge('top.p.addr', 'top.p'))
        self.assertIsNotNone(graph.get_edge('top.p.data', 'top.p'))

        # class property 连接
        self.assertIsNotNone(graph.get_edge('top.p.addr', 'packet.addr'))
        self.assertIsNotNone(graph.get_edge('top.p.data', 'packet.data'))

    def test_member_access_in_always_ff(self):
        """[金标准] p.addr 在 always_ff 中作为 driver

        RTL:
        class packet;
            logic [7:0] addr;
        endclass

        module top;
            packet p = new();
            logic [7:0] reg_out;
            always_ff @(posedge clk) reg_out <= p.addr;
        endmodule

        预期:
        - top.p.addr --DRIVER--> top.reg_out
        - top.p.addr --MEMBER_SELECT--> top.p
        """
        source = '''class packet;
    logic [7:0] addr;
endclass

module top(input clk);
    packet p = new();
    logic [7:0] reg_out;
    always_ff @(posedge clk) reg_out <= p.addr;
endmodule'''
        graph, tracer = self._build_graph(source)

        # top.p.addr 存在
        p_addr = graph.get_node('top.p.addr')
        self.assertIsNotNone(p_addr)

        # DRIVER 边
        driver_edge = graph.get_edge('top.p.addr', 'top.reg_out')
        self.assertIsNotNone(driver_edge, "p.addr 应驱动 reg_out")
        self.assertEqual(driver_edge.kind, EdgeKind.DRIVER)

        # MEMBER_SELECT 边
        ms_edge = graph.get_edge('top.p.addr', 'top.p')
        self.assertIsNotNone(ms_edge)

    def test_class_property_node_unchanged(self):
        """[负面] class property 节点不应被升级为 CLASS_INSTANCE_PROPERTY

        packet.addr 是 CLASS_PROPERTY，不是 CLASS_INSTANCE_PROPERTY
        """
        source = '''class packet;
    logic [7:0] addr;
endclass

module top;
    packet p = new();
    logic [7:0] out;
    assign out = p.addr;
endmodule'''
        graph, tracer = self._build_graph(source)

        # packet.addr 仍然是 CLASS_PROPERTY
        class_prop = graph.get_node('packet.addr')
        self.assertIsNotNone(class_prop)
        self.assertEqual(class_prop.kind, NodeKind.CLASS_PROPERTY,
            "packet.addr 应保持 CLASS_PROPERTY，不应被升级")

    def test_struct_member_not_mismatched(self):
        """[负面] struct 成员不应被错误识别为 class 实例成员

        RTL: struct 的 member 应该保持原样，不创建 MEMBER_SELECT 到 class
        """
        source = '''module top;
    struct {
        logic [7:0] addr;
        logic [7:0] data;
    } s;
    logic [7:0] out;
    assign out = s.addr;
endmodule'''
        graph, tracer = self._build_graph(source)

        # s.addr 不应有 MEMBER_SELECT 边到任何 class property
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge.kind == EdgeKind.MEMBER_SELECT:
                self.fail(f"struct 成员不应有 MEMBER_SELECT 边: {src} -> {dst}")


class TestClassInstanceNode(unittest.TestCase):
    """Class 实例节点接入 (P1)"""

    def _build_graph(self, source):
        tracer = UnifiedTracer(sources={'test.sv': source})
        return tracer.build_graph(), tracer

    def test_instance_upgraded_to_class_instance(self):
        """[金标准] p1 = new() 实例节点升级为 CLASS_INSTANCE

        RTL:
        class packet;
            logic [7:0] addr;
        endclass

        module top;
            packet p1 = new();
        endmodule

        预期:
        - top.p1 类型为 CLASS_INSTANCE (不是 SIGNAL)
        - top.p1 --IS_INSTANCE_OF--> packet
        """
        source = '''class packet;
    logic [7:0] addr;
endclass

module top;
    packet p1 = new();
endmodule'''
        graph, tracer = self._build_graph(source)

        p1 = graph.get_node('top.p1')
        self.assertIsNotNone(p1, "top.p1 节点应存在")
        self.assertEqual(p1.kind, NodeKind.CLASS_INSTANCE,
            "top.p1 应为 CLASS_INSTANCE")

        # IS_INSTANCE_OF 边
        iso_edge = graph.get_edge('top.p1', 'packet')
        self.assertIsNotNone(iso_edge, "top.p1 -> packet IS_INSTANCE_OF 边应存在")
        self.assertEqual(iso_edge.kind, EdgeKind.IS_INSTANCE_OF)

    def test_two_instances_independent(self):
        """[金标准] 两个实例独立接入

        RTL:
        class packet;
            logic [7:0] addr;
        endclass

        module top;
            packet p1 = new();
            packet p2 = new();
        endmodule

        预期:
        - top.p1 和 top.p2 都是 CLASS_INSTANCE
        - 各自有 IS_INSTANCE_OF 边到 packet
        """
        source = '''class packet;
    logic [7:0] addr;
endclass

module top;
    packet p1 = new();
    packet p2 = new();
endmodule'''
        graph, tracer = self._build_graph(source)

        self.assertEqual(graph.get_node('top.p1').kind, NodeKind.CLASS_INSTANCE)
        self.assertEqual(graph.get_node('top.p2').kind, NodeKind.CLASS_INSTANCE)

        self.assertIsNotNone(graph.get_edge('top.p1', 'packet'))
        self.assertIsNotNone(graph.get_edge('top.p2', 'packet'))

    def test_instance_with_member_drivers(self):
        """[金标准] 实例接入 + 成员驱动组合

        验证 P0 (MEMBER_SELECT) + P1 (CLASS_INSTANCE) 同时工作
        """
        source = '''class packet;
    logic [7:0] addr;
endclass

module top;
    packet p = new();
    logic [7:0] out;
    assign out = p.addr;
endmodule'''
        graph, tracer = self._build_graph(source)

        # P1: 实例节点
        p = graph.get_node('top.p')
        self.assertEqual(p.kind, NodeKind.CLASS_INSTANCE)
        self.assertIsNotNone(graph.get_edge('top.p', 'packet'))

        # P0: 成员访问
        p_addr = graph.get_node('top.p.addr')
        self.assertEqual(p_addr.kind, NodeKind.CLASS_INSTANCE_PROPERTY)
        self.assertIsNotNone(graph.get_edge('top.p.addr', 'top.p'))
        self.assertIsNotNone(graph.get_edge('top.p.addr', 'packet.addr'))
        self.assertIsNotNone(graph.get_edge('top.p.addr', 'top.out'))

    def test_non_class_variable_unchanged(self):
        """[负面] 普通变量不应被升级为 CLASS_INSTANCE"""
        source = '''module top;
    logic [7:0] data;
    logic [7:0] out;
    assign out = data;
endmodule'''
        graph, tracer = self._build_graph(source)

        data = graph.get_node('top.data')
        self.assertIsNotNone(data)
        self.assertEqual(data.kind, NodeKind.SIGNAL,
            "普通变量应保持 SIGNAL 类型")

        # 不应有 IS_INSTANCE_OF 边
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            self.assertNotEqual(edge.kind, EdgeKind.IS_INSTANCE_OF,
                "普通模块不应有 IS_INSTANCE_OF 边")


class TestClassMemberAccessAdvanced(unittest.TestCase):
    """Class 实例成员访问高级场景"""

    def _build_graph(self, source):
        tracer = UnifiedTracer(sources={'test.sv': source})
        return tracer.build_graph(), tracer

    def test_two_instances_same_class(self):
        """[金标准] 同一 class 的两个实例

        RTL:
        class packet;
            logic [7:0] addr;
        endclass

        module top;
            packet p1 = new();
            packet p2 = new();
            logic [7:0] out1, out2;
            assign out1 = p1.addr;
            assign out2 = p2.addr;
        endmodule

        预期:
        - top.p1.addr 和 top.p2.addr 独立
        - 各自连接到 packet.addr
        """
        source = '''class packet;
    logic [7:0] addr;
endclass

module top;
    packet p1 = new();
    packet p2 = new();
    logic [7:0] out1, out2;
    assign out1 = p1.addr;
    assign out2 = p2.addr;
endmodule'''
        graph, tracer = self._build_graph(source)

        # 两个实例属性节点
        self.assertIsNotNone(graph.get_node('top.p1.addr'))
        self.assertIsNotNone(graph.get_node('top.p2.addr'))

        # 各自的 DRIVER 边
        self.assertIsNotNone(graph.get_edge('top.p1.addr', 'top.out1'))
        self.assertIsNotNone(graph.get_edge('top.p2.addr', 'top.out2'))

        # 各自的 MEMBER_SELECT 边
        self.assertIsNotNone(graph.get_edge('top.p1.addr', 'top.p1'))
        self.assertIsNotNone(graph.get_edge('top.p2.addr', 'top.p2'))

        # 都连接到同一个 class property
        self.assertIsNotNone(graph.get_edge('top.p1.addr', 'packet.addr'))
        self.assertIsNotNone(graph.get_edge('top.p2.addr', 'packet.addr'))


if __name__ == '__main__':
    unittest.main()
