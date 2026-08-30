# test_interface_basic.py - 基础 Interface 测试
#
# [iter_064 2026-08-29] 升级断言强度: 保留原有节点存在断言, 补充
# UnifiedTracer + graph.get_edge 行为断言 — 验证 interface 内信号
# 跨模块传递时确实生成了 DRIVER 边 (assign_type=continuous).
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.core.graph.models import EdgeKind
from trace.unified_tracer import UnifiedTracer


class TestInterfaceBasic(unittest.TestCase):
    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        """[iter_064] 构建 tracer graph 的统一 helper (行为断言用)"""
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_simple_interface(self):
        """[Golden] 简单 interface — 模块内驱动 interface 信号
        RTL: interface my_if { logic [7:0] data; }
             module top(my_if tb, input [7:0] din);
                 assign tb.data = din;
             endmodule
        金标准:
        - graph 构建成功 (非空)
        - tb.data 节点存在
        - [iter_064] top.din → top.tb.data DRIVER 边存在 (continuous 赋值)
        """
        source = '''
interface my_if;
    logic [7:0] data;
endinterface

module top(my_if tb, input [7:0] din);
    assign tb.data = din;
endmodule'''

        graph = self._build_graph(source)

        self.assertIsNotNone(graph)
        nodes = list(graph.nodes())
        self.assertTrue(any('tb.data' in n for n in nodes), f'tb.data not in {nodes}')

        # [iter_064] 行为断言: 跨 interface 信号流应生成 DRIVER 边
        driver_edge = graph.get_edge('top.din', 'top.tb.data')
        self.assertIsNotNone(driver_edge,
            "assign tb.data = din 应生成 din → tb.data DRIVER 边")
        self.assertEqual(driver_edge.kind, EdgeKind.DRIVER,
            f"din → tb.data 应为 DRIVER 边, 实际 {driver_edge.kind}")
        self.assertEqual(driver_edge.assign_type, 'continuous',
            "interface 内连续赋值应标记 continuous")

if __name__ == '__main__':
    unittest.main()
