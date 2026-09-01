#==============================================================================
# test_alias.py - alias 语法独立 regression
# [iter_081] A 组: 主路径语法补独立行为断言文件
# 背景: alias 之前只有 integration/test_aliases.py (4 测试), 无 regression 行为断言.
# 行为金标准 (module 域): alias b = a; → refs[0]=target(b), refs[1]=source(a) → a→b DRIVER 边.
# 注意 (SV 规范): alias 只用于 net (wire), 不能 logic 变量 (探针实证).
#==============================================================================

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


def _build_graph(source):
    """构建 tracer graph 的统一 helper"""
    tracer = UnifiedTracer(sources={'t.sv': source})
    tracer.build_graph()
    return tracer.get_graph()


class TestAlias(unittest.TestCase):
    """alias — 主路径语法"""

    def test_alias_simple(self):
        """[Golden] alias y = a; (wire)
        行为: refs[0]=target(y), refs[1]=source(a) → a→y DRIVER 边.
        """
        src = 'module top(input wire a, output wire y); alias y = a; endmodule'
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y'),
                             "alias y = a 应生成 a→y DRIVER 边")

    def test_alias_multi_target(self):
        """[Golden] 多 alias 独立: alias y1 = a; alias y2 = a;
        行为: a 分别驱动 y1, y2.
        """
        src = ('module top(input wire a, output wire y1, y2); '
               'alias y1 = a; alias y2 = a; endmodule')
        pyslang.SyntaxTree.fromText(src)
        graph = _build_graph(src)
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y1'), "a→y1 应存在")
        self.assertIsNotNone(graph.get_edge('top.a', 'top.y2'), "a→y2 应存在")

    def test_alias_not_for_logic(self):
        """[Golden] alias 用于 logic 变量是非法 SV (仅 net):
        行为: 编译必须报错 (Elaboration error) — 锁定工具语义边界.
        """
        src = 'module top(input logic a, output logic y); alias y = a; endmodule'
        pyslang.SyntaxTree.fromText(src)
        # pyslang strict elaboration 拒绝 (alias 仅 net): 期望 CompilationError
        from trace.core.compiler import CompilationError

        with self.assertRaises(CompilationError):
            _build_graph(src)


if __name__ == '__main__':
    unittest.main()
