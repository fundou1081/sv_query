# test_typedef.py - Typedef 金标准
# [铁律13] 金标准测试
# [铁律15] Visitor 模式
# [iter_063 2026-08-29] 升级断言强度: 保留原有 AST/pyslang 语法断言,
# 对 test_typedef_signal_tracking 补充 DRIVER 边行为断言 — typedef
# struct 字段赋值的驱动关系 (常量 → pkt.addr).
"""
Typedef 语法覆盖:
1. typedef enum
2. typedef struct
3. typedef union
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer


def _build_graph(source, filename: str = 'test.sv'):
    """[iter_063] 构建 tracer graph 的统一 helper (行为断言用)"""
    tracer = UnifiedTracer(sources={filename: source})
    tracer.build_graph()
    return tracer.get_graph()


class TestTypedef(unittest.TestCase):
    """Typedef 支持测试"""

    def _make_tracer(self, source):
        pyslang.SyntaxTree.fromText(source)
        return UnifiedTracer(sources={'test.sv': source})

    def test_typedef_enum(self):
        """[Golden] typedef enum

        RTL:
        typedef enum {IDLE, RUN, STOP} state_t;

        预期:
        - TypedefDeclaration 存在
        - 名称为 state_t
        - 类型为 EnumType
        - [iter_063] typedef enum 本身是纯类型声明, 不产生 DRIVER 边
          (行为金标准: 类型定义不驱动任何信号)
        """
        source = '''module top;
    typedef enum {IDLE, RUN, STOP} state_t;
    state_t state;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 TypedefDeclaration
        typedef_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.TypedefDeclaration:
                typedef_decl = m
                break

        self.assertIsNotNone(typedef_decl, "TypedefDeclaration not found")
        self.assertEqual(str(typedef_decl.name).strip(), 'state_t')

        # 检查类型
        self.assertEqual(typedef_decl.type.kind, pyslang.SyntaxKind.EnumType)

        # [iter_063] 行为断言: typedef enum 是纯类型声明, 图中无驱动边.
        # 行为金标准: typedef 不产生 DRIVER 边 (类型声明 ≠ 驱动).
        graph = _build_graph(source)
        # 节点存在 (state 信号被声明)
        nodes = list(graph.nodes())
        self.assertIn('top.state', nodes, "typedef 变量应生成节点")
        # 边集应为空 (没有 assign 赋值)
        edges = list(graph.edges())
        self.assertEqual(len(edges), 0,
            "纯 typedef 声明 (无赋值) 不应产生任何 DRIVER 边")

    def test_typedef_struct(self):
        """[Golden] typedef struct

        RTL:
        typedef struct {
            logic [7:0] addr;
            logic [31:0] data;
        } packet_t;

        预期:
        - TypedefDeclaration 存在
        - 名称为 packet_t
        - 类型为 StructType
        - [iter_063] 同 enum — typedef struct 是纯类型声明, 无驱动边
        """
        source = '''module top;
    typedef struct {
        logic [7:0] addr;
        logic [31:0] data;
    } packet_t;
    packet_t pkt;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 TypedefDeclaration
        typedef_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.TypedefDeclaration:
                typedef_decl = m
                break

        self.assertIsNotNone(typedef_decl, "TypedefDeclaration not found")
        self.assertEqual(str(typedef_decl.name).strip(), 'packet_t')

        # 检查类型
        self.assertEqual(typedef_decl.type.kind, pyslang.SyntaxKind.StructType)

        # [iter_063] 行为断言: typedef struct 纯声明, 无驱动边
        graph = _build_graph(source)
        edges = list(graph.edges())
        self.assertEqual(len(edges), 0,
            "纯 typedef struct 声明不应产生 DRIVER 边")

    def test_typedef_union(self):
        """[Golden] typedef union

        RTL:
        typedef union {
            logic [31:0] word;
            logic [7:0] bytes[4];
        } mem_t;

        预期:
        - TypedefDeclaration 存在
        - 名称为 mem_t
        - 类型为 UnionType
        - [iter_063] 同 struct — typedef union 是纯类型声明, 无驱动边
        """
        source = '''module top;
    typedef union {
        logic [31:0] word;
        logic [7:0] bytes[4];
    } mem_t;
    mem_t mem;
endmodule'''
        tree = pyslang.SyntaxTree.fromText(source)
        root = tree.root

        # 检查 Module members
        members = list(root.members)

        # 查找 TypedefDeclaration
        typedef_decl = None
        for m in members:
            if m.kind == pyslang.SyntaxKind.TypedefDeclaration:
                typedef_decl = m
                break

        self.assertIsNotNone(typedef_decl, "TypedefDeclaration not found")
        self.assertEqual(str(typedef_decl.name).strip(), 'mem_t')

        # 检查类型
        self.assertEqual(typedef_decl.type.kind, pyslang.SyntaxKind.UnionType)

        # [iter_063] 行为断言: typedef union 纯声明, 无驱动边
        graph = _build_graph(source)
        edges = list(graph.edges())
        self.assertEqual(len(edges), 0,
            "纯 typedef union 声明不应产生 DRIVER 边")

    def test_typedef_signal_tracking(self):
        """[Golden] typedef 信号追踪

        RTL:
        typedef struct {
            logic [7:0] addr;
            logic [31:0] data;
        } packet_t;

        module top;
            packet_t pkt;
            assign pkt.addr = 8'h0;
        endmodule

        预期:
        - pkt.addr 节点存在
        - [iter_063] 行为断言: 常量 8'h0 → pkt.addr DRIVER 边 (struct 字段赋值)
        """
        source = '''typedef struct {
    logic [7:0] addr;
    logic [31:0] data;
} packet_t;

module top;
    packet_t pkt;
    assign pkt.addr = 8'h0;
endmodule'''
        tracer = self._make_tracer(source)
        tracer.build_graph()

        # 金标准: 图建立成功
        self.assertIsNotNone(tracer.get_graph())

        nodes = list(tracer.get_graph().nodes())

        # 验证: pkt.addr 节点存在
        has_pkt_addr = any('pkt.addr' in n for n in nodes)
        self.assertTrue(has_pkt_addr, f"pkt.addr not found in {nodes}")

        # [iter_063] 行为断言: 常量 8'h0 → pkt.addr DRIVER 边存在
        # typedef struct 字段的连续赋值应产生驱动边.
        graph = tracer.get_graph()
        # 验证至少有一条 → pkt.addr 的入边
        in_edges_to_addr = [u for u, v in graph.edges() if v == 'top.pkt.addr']
        self.assertGreaterEqual(len(in_edges_to_addr), 1,
            "assign pkt.addr = 8'h0 应生成 →pkt.addr 的 DRIVER 边")


if __name__ == '__main__':
    unittest.main()
