# test_port_inout.py - PORT_INOUT 测试
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
#
# [iter_064 2026-08-29] 升级断言强度: 保留原有节点/kind 断言, 补充
# UnifiedTracer + graph.get_edge 行为断言 — 验证三态缓冲确实生成了
# DRIVER 边 (条件驱动) + BRANCH_* 边, 多 inout 端口的 PORT_INOUT kind
# 与节点一致性.
"""
PORT_INOUT 相关测试:
1. 多 inout 端口
2. 三态缓冲
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.graph.models import EdgeKind, NodeKind
from trace.unified_tracer import UnifiedTracer


class TestPortInout(unittest.TestCase):
    """PORT_INOUT 测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'t.sv': source})

    def _build_graph(self, source):
        """[iter_064] 构建 tracer graph 的统一 helper (行为断言用)"""
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_tri_state_buffer(self):
        """[Golden] 三态缓冲

        RTL: assign bidir = en ? data : 1'bz;

        预期:
        - bidir 节点存在
        - 驱动追溯正确处理三态
        - [iter_064] data → bidir DRIVER 边 (条件 en) + BRANCH 边族
          (en → ternary, data → ternary, ternary → bidir)
        """
        source = '''
module top (
    input logic clk,
    input logic en,
    input logic data,
    inout logic bidir
);
    assign bidir = en ? data : 1'bz;
endmodule'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        # 金标准: bidir 节点存在
        self.assertTrue(any('bidir' in n for n in nodes),
            f"bidir 节点应存在，实际节点: {nodes}")

        # [iter_064] 行为断言: 三态驱动 data → bidir (条件 en)
        driver_edge = graph.get_edge('top.data', 'top.bidir')
        self.assertIsNotNone(driver_edge, "三态使能分支 data→bidir 应生成 DRIVER 边")
        self.assertEqual(driver_edge.kind, EdgeKind.DRIVER,
            f"data→bidir 应为 DRIVER 边, 实际 {driver_edge.kind}")
        self.assertEqual(driver_edge.assign_type, 'continuous',
            "连续赋值三态应标记 continuous")
        self.assertEqual(driver_edge.condition, 'en',
            "三态使能条件 en 应作为 DRIVER 边的 condition")

        # [iter_064] 行为断言: 三目条件节点 bidir.ternary_en 存在且连接 en
        self.assertIn('top.bidir.ternary_en', nodes,
            "三目中间节点 bidir.ternary_en 应生成")
        branch_cond = graph.get_edge('top.en', 'top.bidir.ternary_en')
        self.assertIsNotNone(branch_cond, "en → ternary_en BRANCH_CONDITION 边应存在")
        self.assertEqual(branch_cond.kind, EdgeKind.BRANCH_CONDITION,
            f"en → ternary 应为 BRANCH_CONDITION, 实际 {branch_cond.kind}")

        # 三目结果回灌 bidir
        branch_result = graph.get_edge('top.bidir.ternary_en', 'top.bidir')
        self.assertIsNotNone(branch_result, "ternary_en → bidir BRANCH_RESULT 边应存在")
        self.assertEqual(branch_result.kind, EdgeKind.BRANCH_RESULT,
            f"ternary_en → bidir 应为 BRANCH_RESULT, 实际 {branch_result.kind}")

    def test_multiple_inout_ports(self):
        """[Golden] 多 inout 端口

        RTL: 多个 inout 端口

        预期:
        - 所有 inout 端口节点存在
        - [iter_064] 每个端口 node.kind 均为 PORT_INOUT (类型断言)
        """
        source = '''
module top (
    inout logic port_a,
    inout logic port_b,
    inout logic port_c
);
    // 简化：双向端口
endmodule'''

        graph = self._build_graph(source)
        nodes = list(graph.nodes())

        # 金标准: port_a, port_b, port_c 节点存在
        self.assertTrue(any('port_a' in n for n in nodes), "port_a 应存在")
        self.assertTrue(any('port_b' in n for n in nodes), "port_b 应存在")
        self.assertTrue(any('port_c' in n for n in nodes), "port_c 应存在")

        # [iter_064] 行为断言: 每个端口 kind 均为 PORT_INOUT
        # 纯声明端口无 DRIVER 边 (工具缺口 — 需 driver 才出边), 只断言 kind.
        for port in ('port_a', 'port_b', 'port_c'):
            node = graph.get_node(f'top.{port}')
            self.assertIsNotNone(node, f"top.{port} 节点应存在")
            self.assertEqual(node.kind, NodeKind.PORT_INOUT,
                f"top.{port} kind 应为 PORT_INOUT, 实际 {node.kind}")

        # 备注: 多 inout 纯声明场景无 DRIVER 边 (无赋值语句驱动它们),
        # 故不补边断言 — 注释说明此为声明场景, 非驱动场景.

    def test_inout_kind(self):
        """[Golden] inout 端口 kind 正确

        预期:
        - inout 端口 kind 为 PORT_INOUT
        - [iter_064] 单端口无 driver 时无 DRIVER 边 (纯声明场景)
        """
        source = '''
module top (
    inout logic bidir
);
endmodule'''

        graph = self._build_graph(source)

        # 金标准: bidir 节点 kind 为 PORT_INOUT
        bidir_node = graph.get_node('top.bidir')
        self.assertIsNotNone(bidir_node, "bidir 节点应存在")
        self.assertEqual(bidir_node.kind, NodeKind.PORT_INOUT,
            f"bidir kind 应为 PORT_INOUT，实际: {bidir_node.kind}")

        # [iter_064] 行为断言: 纯声明 inout 无入边 (无 driver 驱动它)
        # 端口单向声明不产生 DRIVER 边; 只有当 assign/always 等驱动它时才有.
        # 这里确认无入边, 与 test_tri_state_buffer 形成对照.
        in_edges = [u for u, _v in graph.in_edges('top.bidir')]
        self.assertEqual(len(in_edges), 0,
            "纯声明 inout 端口无 driver 入边 (工具行为: 仅声明不驱动时无 DRIVER 边)")


if __name__ == '__main__':
    unittest.main()
