# test_e2e_debug_and_conditions.py - 端到端测试：Debug 追踪 + 条件提取
#
# 场景4: RTL 信号报错，向前/向后追踪到 module port
# 场景5: 复杂嵌套 if 条件提取 true condition → coverage
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind


def _build_graph(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    return tracer.build_graph(), tracer


def _trace_fanin(graph, signal_id, visited=None, depth=0, max_depth=10):
    """向前追踪：找所有驱动该信号的源（直到 port）"""
    if visited is None:
        visited = set()
    if signal_id in visited or depth > max_depth:
        return []
    visited.add(signal_id)

    results = []
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if dst == signal_id and edge.kind == EdgeKind.DRIVER:
            node = graph.get_node(src)
            if node:
                info = {
                    'signal': src,
                    'kind': str(node.kind),
                    'is_port': node.is_port,
                    'depth': depth,
                }
                results.append(info)
                results.extend(_trace_fanin(graph, src, visited, depth + 1, max_depth))
    return results


def _trace_fanout(graph, signal_id, visited=None, depth=0, max_depth=10):
    """向后追踪：找该信号驱动的所有目标（直到 port）"""
    if visited is None:
        visited = set()
    if signal_id in visited or depth > max_depth:
        return []
    visited.add(signal_id)

    results = []
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if src == signal_id and edge.kind == EdgeKind.DRIVER:
            node = graph.get_node(dst)
            if node:
                info = {
                    'signal': dst,
                    'kind': str(node.kind),
                    'is_port': node.is_port,
                    'depth': depth,
                }
                results.append(info)
                results.extend(_trace_fanout(graph, dst, visited, depth + 1, max_depth))
    return results


def trace_signal_debug(graph, signal_id):
    """完整的信号 debug 信息"""
    fanin = _trace_fanin(graph, signal_id)
    fanout = _trace_fanout(graph, signal_id)

    affecting_ports = [f['signal'] for f in fanin if f['is_port']]
    affected_ports = [f['signal'] for f in fanout if f['is_port']]

    return {
        'signal': signal_id,
        'fanin': fanin,
        'fanout': fanout,
        'affecting_ports': affecting_ports,
        'affected_ports': affected_ports,
    }


def extract_true_conditions(graph, signal_id):
    """提取信号涉及的所有 true condition

    从约束图中找 HAS_CONDITION 边，提取条件链。
    返回: list of {condition_vars, branch, expr_node}
    """
    conditions = []

    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if edge.kind == EdgeKind.HAS_LHS and dst == signal_id:
            expr_node = src
            # 向上找 CONSTRAINT_IF
            for s2, d2 in graph.edges():
                e2 = graph.get_edge(s2, d2)
                if e2.kind == EdgeKind.HAS_CONSEQUENT and d2 == expr_node:
                    if_node = s2
                    cond_vars = []
                    for s3, d3 in graph.edges():
                        e3 = graph.get_edge(s3, d3)
                        if e3.kind == EdgeKind.HAS_CONDITION and s3 == if_node:
                            cond_vars.append(d3)
                    conditions.append({
                        'if_node': if_node,
                        'expr_node': expr_node,
                        'condition_vars': cond_vars,
                        'branch': 'consequent',
                    })

    return conditions


def conditions_to_coverage_suggestions(conditions, signal_name):
    """将条件链转换为 coverage 建议"""
    suggestions = []

    for cond in conditions:
        cond_vars = cond['condition_vars']
        branch = cond['branch']

        if len(cond_vars) == 1:
            cv = cond_vars[0].split('.')[-1]
            suggestions.append({
                'type': 'cross',
                'description': f'{signal_name} 在 {cv} 为真时被约束',
                'coverpoint_a': signal_name,
                'coverpoint_b': cv,
                'suggested_bins': f'cross {signal_name}, {cv}',
            })
        elif len(cond_vars) > 1:
            cv_names = [v.split('.')[-1] for v in cond_vars]
            suggestions.append({
                'type': 'multi_cross',
                'description': f'{signal_name} 在 {" && ".join(cv_names)} 条件下被约束',
                'coverpoint_a': signal_name,
                'coverpoint_b': cv_names,
                'suggested_bins': f'cross {signal_name}, {", ".join(cv_names)}',
            })

    return suggestions


# =========================================================================
# 场景4: Debug 追踪
# =========================================================================

class TestDebugSignalTrace(unittest.TestCase):
    """场景4: 信号 Debug 追踪"""

    def test_trace_signal_to_ports(self):
        """[端到端] 追踪 data_reg 到 module port

        module pipeline(input clk, data_in, en, output data_out);
            logic [7:0] data_reg;
            always_ff @(posedge clk)
                if (en) data_reg <= data_in;
            assign data_out = data_reg + 1;
        endmodule

        追踪 data_reg:
          影响它的 input port: data_in, en
          它影响的 output port: data_out
        """
        source = '''module pipeline(input clk, input [7:0] data_in, input en,
                        output logic [7:0] data_out);
    logic [7:0] data_reg;
    always_ff @(posedge clk)
        if (en) data_reg <= data_in;
    assign data_out = data_reg + 1;
endmodule'''
        graph, _ = _build_graph(source)

        result = trace_signal_debug(graph, 'pipeline.data_reg')

        print(f"\n=== Debug: pipeline.data_reg ===")
        print(f"  Fanin (向前追踪):")
        for f in result['fanin']:
            indent = "    " + "  " * f['depth']
            port_mark = " [PORT]" if f['is_port'] else ""
            print(f"{indent}{f['signal']}{port_mark}")
        print(f"  Fanout (向后追踪):")
        for f in result['fanout']:
            indent = "    " + "  " * f['depth']
            port_mark = " [PORT]" if f['is_port'] else ""
            print(f"{indent}{f['signal']}{port_mark}")
        print(f"  影响它的 input port: {result['affecting_ports']}")
        print(f"  它影响的 output port: {result['affected_ports']}")

        self.assertIn('pipeline.data_in', result['affecting_ports'])
        self.assertIn('pipeline.data_out', result['affected_ports'])

    def test_trace_multi_hop(self):
        """[端到端] 多跳追踪

        module chain(input clk, a, output d);
            logic b, c;
            b <= a + 1; c <= b * 2; d <= c - 1;
        endmodule

        追踪 c: fanin → a, fanout → d
        """
        source = '''module chain(input clk, input [7:0] a, output logic [7:0] d);
    logic [7:0] b, c;
    always_ff @(posedge clk) b <= a + 1;
    always_ff @(posedge clk) c <= b * 2;
    always_ff @(posedge clk) d <= c - 1;
endmodule'''
        graph, _ = _build_graph(source)

        result = trace_signal_debug(graph, 'chain.c')

        print(f"\n=== Debug: chain.c ===")
        print(f"  Affecting input ports: {result['affecting_ports']}")
        print(f"  Affected output ports: {result['affected_ports']}")

        self.assertIn('chain.a', result['affecting_ports'])
        self.assertIn('chain.d', result['affected_ports'])


# =========================================================================
# 场景5: 条件提取 → Coverage
# =========================================================================

class TestConditionToCoverage(unittest.TestCase):
    """场景5: 嵌套条件提取 → Coverage"""

    def test_simple_condition(self):
        """[端到端] 简单条件提取

        class packet;
            rand bit [7:0] addr;
            rand bit [7:0] mode;
            constraint c {
                if (mode == 0) { addr < 100; }
                else { addr >= 100; }
            }
        endclass

        查询 addr 的条件:
          - consequent: mode == 0
          - alternate: mode != 0

        转换为 coverage:
          - cross addr, mode
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    constraint c {
        if (mode == 0) { addr inside {[0:99]}; }
        else { addr inside {[100:255]}; }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        conditions = extract_true_conditions(graph, 'packet.addr')

        print(f"\n=== 条件提取: packet.addr ===")
        for cond in conditions:
            cv = [v.split('.')[-1] for v in cond['condition_vars']]
            print(f"  branch={cond['branch']}, condition_vars={cv}")

        # 转换为 coverage 建议
        suggestions = conditions_to_coverage_suggestions(conditions, 'addr')
        print(f"\n=== Coverage 建议 ===")
        for s in suggestions:
            print(f"  {s['type']}: {s['description']}")
            print(f"    → {s['suggested_bins']}")

        # 验证
        self.assertGreater(len(conditions), 0)
        cond_vars = conditions[0]['condition_vars']
        self.assertTrue(any('mode' in v for v in cond_vars))

    def test_nested_if_conditions(self):
        """[端到端] 嵌套 if 条件提取

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

        查询 addr 的条件:
          - mode == 0 (外层)
          - sel == 1 (内层，当前实现可能不识别)

        转换为 coverage:
          - cross addr, mode, sel
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    rand bit [7:0] sel;
    constraint c {
        if (mode == 0) {
            if (sel == 1) { addr inside {[0:49]}; }
        }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        conditions = extract_true_conditions(graph, 'packet.addr')

        print(f"\n=== 嵌套条件提取: packet.addr ===")
        for cond in conditions:
            cv = [v.split('.')[-1] for v in cond['condition_vars']]
            print(f"  branch={cond['branch']}, condition_vars={cv}")

        # 至少应识别外层条件
        all_vars = set()
        for cond in conditions:
            for v in cond['condition_vars']:
                all_vars.add(v.split('.')[-1])

        print(f"  所有条件变量: {all_vars}")
        self.assertIn('mode', all_vars, "应识别外层条件 mode")

    def test_implication_condition(self):
        """[端到端] implication 条件提取

        class packet;
            rand bit [7:0] addr;
            rand bit [7:0] mode;
            constraint c {
                mode == 1 -> { addr < 64; }
            }
        endclass

        查询 addr 的条件:
          - mode == 1 (implication 前件)
        """
        source = '''class packet;
    rand bit [7:0] addr;
    rand bit [7:0] mode;
    constraint c {
        mode == 1 -> { addr inside {[0:63]}; }
    }
endclass
module top; endmodule'''
        graph, _ = _build_graph(source)

        conditions = extract_true_conditions(graph, 'packet.addr')

        print(f"\n=== Implication 条件提取: packet.addr ===")
        for cond in conditions:
            cv = [v.split('.')[-1] for v in cond['condition_vars']]
            print(f"  branch={cond['branch']}, condition_vars={cv}")

        all_vars = set()
        for cond in conditions:
            for v in cond['condition_vars']:
                all_vars.add(v.split('.')[-1])

        self.assertIn('mode', all_vars, "应识别 implication 条件 mode")


if __name__ == '__main__':
    unittest.main()
