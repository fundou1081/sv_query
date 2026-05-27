# test_class_constraint_detail.py - 约束详情查询金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
#
# 查询变量关联的约束详情，包括：
#   - 约束表达式文本
#   - 条件上下文（if/else 条件）
#   - 条件变量
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind


# =========================================================================
# 辅助方法
# =========================================================================

def _build_graph(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    return graph, tracer


def _get_constraint_detail(graph, var_id):
    """获取变量关联的约束详情

    返回: list of dict, 每个 dict 包含:
      - constraint_block: CONSTRAINT_BLOCK 节点 ID
      - expr_id: CONSTRAINT_EXPR 节点 ID
      - condition_chain: list of condition 信息 (从外到内)
        每个 condition: {"var": 变量ID, "if_node": CONSTRAINT_IF ID}
      - branch: "consequent" | "alternate" | None (无条件时)
    """
    results = []

    # 找到所有直接引用该变量的 CONSTRAINT_EXPR 节点
    expr_nodes = set()
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if edge.kind == EdgeKind.HAS_LHS and dst == var_id:
            node = graph.get_node(src)
            if node and node.kind == NodeKind.CONSTRAINT_EXPR:
                expr_nodes.add(src)

    for expr_id in expr_nodes:
        # 向上追溯条件链
        condition_chain = []
        branch = None
        current = expr_id

        while current:
            # 找谁 CONSTRAINS/HAS_CONSEQUENT/HAS_ALTERNATE 到 current
            parent = None
            for src, dst in graph.edges():
                edge = graph.get_edge(src, dst)
                if dst != current:
                    continue
                if edge.kind == EdgeKind.HAS_CONSEQUENT:
                    parent = src
                    branch = "consequent"
                elif edge.kind == EdgeKind.HAS_ALTERNATE:
                    parent = src
                    branch = "alternate"
                elif edge.kind == EdgeKind.CONSTRAINS:
                    parent = src

            if parent is None:
                break

            parent_node = graph.get_node(parent)
            if parent_node is None:
                break

            if parent_node.kind == NodeKind.CONSTRAINT_IF:
                # 收集条件变量
                cond_vars = []
                for s2, d2 in graph.edges():
                    e2 = graph.get_edge(s2, d2)
                    if e2.kind == EdgeKind.HAS_CONDITION and s2 == parent:
                        cond_vars.append(d2)
                condition_chain.insert(0, {
                    "if_node": parent,
                    "condition_vars": cond_vars,
                })
                current = parent
            elif parent_node.kind == NodeKind.CONSTRAINT_ELSE:
                current = parent
            elif parent_node.kind == NodeKind.CONSTRAINT_BLOCK:
                # 到达顶层约束块
                results.append({
                    "constraint_block": parent,
                    "expr_id": expr_id,
                    "condition_chain": condition_chain,
                    "branch": branch if condition_chain else None,
                })
                break
            else:
                current = parent
        else:
            # 没找到 CONSTRAINT_BLOCK，但仍返回
            if expr_id not in [r["expr_id"] for r in results]:
                results.append({
                    "constraint_block": None,
                    "expr_id": expr_id,
                    "condition_chain": condition_chain,
                    "branch": branch if condition_chain else None,
                })

    return results


# =========================================================================
# 基础场景
# =========================================================================

class TestConstraintDetail(unittest.TestCase):
    """约束详情查询"""

    def test_simple_no_condition(self):
        """[金标准] 无条件约束

        class packet;
            rand bit [7:0] addr;
            constraint c_addr { addr < 100; }
        endclass

        查询 packet.addr:
          - constraint_block: packet.c_addr
          - condition_chain: [] (无条件)
          - branch: None
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c_addr { addr < 100; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _get_constraint_detail(graph, 'packet.addr')
        self.assertEqual(len(result), 1, "应有 1 个约束表达式")
        self.assertEqual(result[0]['constraint_block'], 'packet.c_addr')
        self.assertEqual(result[0]['condition_chain'], [])
        self.assertIsNone(result[0]['branch'])

    def test_if_else_condition(self):
        """[金标准] if/else 条件约束

        class packet;
            rand bit [7:0] addr;
            rand bit [7:0] mode;
            constraint c_mode {
                if (mode == 0) { addr < 100; }
                else { addr < 200; }
            }
        endclass

        查询 packet.addr:
          - [0] constraint_block: packet.c_mode, branch: consequent
               condition_chain: [{"condition_vars": ["packet.mode"]}]
          - [1] constraint_block: packet.c_mode, branch: alternate
               condition_chain: [{"condition_vars": ["packet.mode"]}]
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    constraint c_mode {
        if (mode == 0) { addr < 100; }
        else { addr < 200; }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _get_constraint_detail(graph, 'packet.addr')
        self.assertEqual(len(result), 2, "应有 2 个约束表达式 (if + else)")

        # if 分支
        if_result = [r for r in result if r['branch'] == 'consequent']
        self.assertEqual(len(if_result), 1)
        self.assertEqual(if_result[0]['constraint_block'], 'packet.c_mode')
        self.assertEqual(len(if_result[0]['condition_chain']), 1)
        self.assertIn('packet.mode', if_result[0]['condition_chain'][0]['condition_vars'])

        # else 分支
        else_result = [r for r in result if r['branch'] == 'alternate']
        self.assertEqual(len(else_result), 1)
        self.assertEqual(else_result[0]['constraint_block'], 'packet.c_mode')

    def test_condition_var_is_tracked(self):
        """[金标准] 条件变量也能查到关联的约束

        查询 packet.mode (条件变量):
          - constraint_block: packet.c_mode
          - condition_chain: [] (mode 本身不在 if body 中，但在 HAS_CONDITION 上)
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    constraint c_mode {
        if (mode == 0) { addr < 100; }
        else { addr < 200; }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        # mode 通过 CONSTRAINS 边关联到 c_mode
        constraints = set()
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge.kind == EdgeKind.CONSTRAINS and dst == 'packet.mode':
                node = graph.get_node(src)
                if node and node.kind == NodeKind.CONSTRAINT_BLOCK:
                    constraints.add(src)
        self.assertIn('packet.c_mode', constraints)

    def test_multiple_constraints(self):
        """[金标准] 变量在多个约束块中

        class packet;
            rand bit [7:0] addr;
            constraint c_range { addr inside {[0:100]}; }
            constraint c_align { addr[1:0] == 0; }
        endclass

        查询 packet.addr:
          - [0] constraint_block: packet.c_range
          - [1] constraint_block: packet.c_align
        """
        source = '''class packet;
    rand bit [7:0] addr;
    constraint c_range { addr inside {[0:100]}; }
    constraint c_align { addr[1:0] == 0; }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _get_constraint_detail(graph, 'packet.addr')
        blocks = {r['constraint_block'] for r in result}
        self.assertIn('packet.c_range', blocks)
        self.assertIn('packet.c_align', blocks)

    def test_nested_if_conditions(self):
        """[金标准] 嵌套 if 条件

        class packet;
            rand bit [7:0] addr;
            rand bit [7:0] mode;
            rand bit [7:0] sel;
            constraint c {
                if (mode == 0) {
                    if (sel == 1) { addr < 50; }
                }
            }
        endclass

        当前实现: 内层 if 被展平为单个 CONSTRAINT_EXPR
        查询 packet.addr:
          - constraint_block: packet.c
            branch: consequent
            condition_chain: [{"condition_vars": ["packet.mode"]}]
        注意: 内层 if (sel == 1) 的条件未被单独识别为 CONSTRAINT_IF
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    rand bit [7:0] sel;
    constraint c {
        if (mode == 0) {
            if (sel == 1) { addr < 50; }
        }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _get_constraint_detail(graph, 'packet.addr')
        self.assertGreaterEqual(len(result), 1)

        # 外层 if 条件 (mode) 应在 condition_chain 中
        self.assertGreaterEqual(len(result[0]['condition_chain']), 1)
        self.assertIn('packet.mode', result[0]['condition_chain'][0]['condition_vars'])
        # sel 也被 CONSTRAINS 引用（展平处理）
        # 内层 if 未被解析为独立 CONSTRAINT_IF，这是已知限制

    def test_inherited_constraint_detail(self):
        """[金标准] 继承约束详情

        class base;
            rand bit [7:0] id;
            constraint c_id { id > 0; }
        endclass
        class packet extends base;
            rand bit [7:0] addr;
        endclass

        查询 packet.id (继承变量):
          - constraint_block: packet.c_id (继承自 base.c_id)
        """
        source = '''class base;
    rand bit [7:0] id;
    constraint c_id { id > 0; }
endclass
class packet extends base;
    rand bit [7:0] addr;
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        result = _get_constraint_detail(graph, 'packet.id')
        self.assertGreaterEqual(len(result), 1)
        blocks = {r['constraint_block'] for r in result}
        self.assertIn('packet.c_id', blocks)


if __name__ == '__main__':
    unittest.main()
