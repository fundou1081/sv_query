# test_dpi.py - DPI 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [iter_064 2026-08-29] 行为断言加强: 保留 AST 断言 (DPIImport 节点 + 方法名),
# 补充 graph 节点断言. 关键发现 (iter_064 探测):
# - 单纯 import "DPI-C" function/task 声明**不生成任何 graph 节点或边**
#   (DPI 是外部 C 接口, 内部信号拓扑不可见 — 期望行为, 不是工具缺口).
# - DPI 函数调用站点 (assign result = add(1, 2)) 仅生成 LHS 节点,
#   **不生成 DRIVER 边** — 工具缺口 (DPI 函数体不可见, 调用结果不可推导),
#   记录在 EXTRACTION_COVERAGE. 此文件只断言可达节点 (DPI import 自身无节点).
"""
DPI 语法覆盖:
1. import \"DPI-C\" function
2. import \"DPI-C\" task
3. DPI 调用站点的信号节点提取 (LHS)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


class TestDPI(unittest.TestCase):
    """DPI 支持测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def _build_graph(self, source):
        tracer = self._make_tracer(source)
        tracer.build_graph()
        return tracer.get_graph()

    def test_dpi_function_import(self):
        """[Golden] import \"DPI-C\" function

        RTL:
        module top;
            import \"DPI-C\" function int add(input int a, input int b);
        endmodule

        预期:
        - DPIImport 存在 (AST 断言)
        - 方法名为 add (AST 断言)
        - 行为金标准: DPI import 自身**不**生成 graph 节点/边
          (DPI 是外部 C 接口声明, 没有内部信号拓扑). 这是期望行为,
          不是工具缺口 — 调用方通过 AST 断言确认 DPI import 已被
          pyslang 接受.
        """
        source = '''module top;
    import \"DPI-C\" function int add(input int a, input int b);
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 DPIImport
        dpi_import = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.DPIImport:
                dpi_import = m
                break

        self.assertIsNotNone(dpi_import, "DPIImport not found")

        # 检查方法名
        method = dpi_import.method
        self.assertEqual(str(method.name).strip(), 'add')

        # [iter_064] 行为断言: graph 构建成功 (DPI 声明无害) 且不引入
        # 任何奇怪节点. 工具现状 (iter_064 探测): 单纯 DPI import 声明
        # 不会产生任何 module 节点 — 纯 DPI 的 module graph 为空.
        # 这与"纯 import DPI 不应引入信号节点"的断言方向一致:
        # graph 没有信号节点 = 期望行为 (DPI 是外部接口).
        graph = self._build_graph(source)
        self.assertIsNotNone(graph)
        nodes = list(graph.nodes())
        # DPI 不应生成额外 add 节点 (因为 DPI 是外部 C 函数)
        self.assertNotIn('top.add', nodes,
                         "DPI import 不应生成 graph 节点 add (它是外部 C 函数)")

    def test_dpi_task_import(self):
        """[Golden] import \"DPI-C\" task

        RTL:
        module top;
            import \"DPI-C\" task reset();
        endmodule

        预期:
        - DPIImport 存在 (AST 断言)
        - 方法名为 reset (AST 断言)
        - 行为金标准: 同 test_dpi_function_import — DPI import 自身
          不生成 graph 行为.
        """
        source = '''module top;
    import \"DPI-C\" task reset();
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 DPIImport
        dpi_import = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.DPIImport:
                dpi_import = m
                break

        self.assertIsNotNone(dpi_import, "DPIImport not found")

        # 检查方法名
        method = dpi_import.method
        self.assertEqual(str(method.name).strip(), 'reset')

        # [iter_064] 行为断言: graph 构建不报错, DPI 不产生 reset 信号节点
        graph = self._build_graph(source)
        self.assertIsNotNone(graph)
        nodes = list(graph.nodes())
        self.assertNotIn('top.reset', nodes,
                         "DPI import task reset() 不应生成 graph 节点 (外部 C 接口)")

    def test_dpi_signal_tracking(self):
        """[Golden] DPI 调用站点的 LHS 信号节点追踪

        RTL:
        module top;
            import \"DPI-C\" function int add(input int a, input int b);

            int result;
            assign result = add(1, 2);
        endmodule

        预期:
        - result 节点存在 (行为金标准 — LHS 信号被识别)
        - 工具缺口注意 (iter_064 探测): DPI 函数体内代码不可见,
          assign result = add(1, 2) 不会生成 5→result DRIVER 边
          (无法推导外部 C 函数的返回值). 这是已知的 EXTRACTION_COVERAGE,
          此测试只断言 LHS 节点存在.
        """
        source = '''module top;
    import \"DPI-C\" function int add(input int a, input int b);

    int result;
    assign result = add(1, 2);
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())

        graph = tracer.get_graph()
        nodes = list(graph.nodes())

        # 验证: result 节点存在
        has_result = any('result' in n for n in nodes)
        self.assertTrue(has_result, f"result not found in {nodes}")

        # [iter_064] 行为断言: result 节点是 assign LHS, 必然存在
        # (与原始节点存在检查对齐, 无更强的 DRIVER 边可断言 — 工具缺口).
        self.assertIn('top.result', nodes, "DPI 调用 LHS result 节点应被提取")


if __name__ == '__main__':
    unittest.main()
