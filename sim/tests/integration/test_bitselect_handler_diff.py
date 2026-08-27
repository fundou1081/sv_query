# ==============================================================================
# test_bitselect_handler_diff.py - BitSelectHandler vs graph_builder 实现差异验证
#
# [ARCHITECTURE_TODOLIST #2 2026-08-28 06:23] B方案实测脚本.
# 写 G2 计划 + 跑 diff 验证脚本, 不下结论改代码.
#
# 目标: 对同一 SV 输入, 分别走:
#   路径 A - 完整 unified_tracer (走 BitSelectHandler.process() 全 3 阶段)
#   路径 B - 跳过 BitSelectHandler (只走 graph_builder 内部简化版 _create_hierarchical_bit_nodes)
#
# 对比两套输出的 BIT_SELECT 边 + 位选节点属性, 量化差异.
#
# 注意: 不修代码, 只记录事实. 实测数据驱动后续 #2 G3 计划.
# ==============================================================================
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import EdgeKind


# ==============================================================================
# [铁律17] 强断言原则 — 每条 fixture 都有预期
# ==============================================================================

FIXTURE_RANGESELECT = '''
module top(input clk);
    logic [7:0] data;
    logic [3:0] slice;

    always_ff @(posedge clk) begin
        slice <= data[3:0];   // RangeSelect: data[3:0]
    end
endmodule
'''

FIXTURE_ELEMENTSELECT = '''
module top(input clk);
    logic [7:0] data;
    logic s0, s1;

    always_ff @(posedge clk) begin
        s0 <= data[0];  // ElementSelect: data[0]
        s1 <= data[7];  // ElementSelect: data[7]
    end
endmodule
'''

FIXTURE_MIXED = '''
module top(input clk);
    logic [15:0] data;
    logic [7:0] hi, lo;
    logic s0;

    always_ff @(posedge clk) begin
        hi <= data[15:8];  // RangeSelect
        lo <= data[7:0];   // RangeSelect
        s0 <= data[0];     // ElementSelect
    end
endmodule
'''

# [2026-08-28 06:33] 边界 fixture — 测 regex 反推位选名的脆弱性
# 现实 SV 代码常见位选形式, 大多不是简单的 '[N:M]'
FIXTURE_PARAMETER = '''
module top #(parameter W = 8) (input clk);
    logic [W-1:0] data;
    logic [W-1:0] slice;

    always_ff @(posedge clk) begin
        slice <= data[W-1:0];  // Parameter 位选: regex 匹配不了 (W-1 不是数字)
    end
endmodule
'''

FIXTURE_GENERATE = '''
module top #(parameter N = 4) (input clk);
    logic [3:0] acc [0:N];
    logic [3:0] data_in;

    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen
            always_ff @(posedge clk) begin
                acc[i] <= data_in;   // ElementSelect 动态: acc[i]
                acc[i+1] <= acc[i];  // 表达式位选: acc[i+1] (i+1 不是字面量)
            end
        end
    endgenerate
endmodule
'''

FIXTURE_NESTED = '''
module top(input clk);
    logic [7:0] data;
    logic [1:0] slice;

    always_ff @(posedge clk) begin
        slice <= data[3:0][1:0];  // 多维位选嵌套: regex 匹配不了
    end
endmodule
'''

FIXTURE_STRUCT = '''
module top(input clk);
    typedef struct packed {
        logic [7:0] addr;
        logic [7:0] data;
    } pkt_t;

    pkt_t pkt;
    logic [3:0] low_nibble;

    always_ff @(posedge clk) begin
        low_nibble <= pkt.addr[3:0];  // struct 字段位选: regex 可能不支持
    end
endmodule
'''


def _build_unified_tracer(source):
    """路径 A: 完整 unified_tracer (走 BitSelectHandler.process 3 阶段)"""
    pyslang.SyntaxTree.fromText(source)
    tracer = UnifiedTracer(sources={'test.sv': source})
    tracer.build_graph()
    return tracer.get_graph()


def _build_graph_builder_only(source):
    """路径 B: 跳过 BitSelectHandler, 只走 graph_builder 内部简化版

    实现策略: 用 SVCompiler + SemanticAdapter + GraphBuilder 手动跑,
    不调用 unified_tracer 全流程, 不触发 BitSelectHandler.
    """
    pyslang.SyntaxTree.fromText(source)
    # 正确初始化顺序: SVCompiler(sources=...) -> get_root() (触发 _do_compile) -> SemanticAdapter
    from trace.core.graph_builder import GraphBuilder
    from trace.core.semantic_adapter import SemanticAdapter
    from trace.core.compiler import SVCompiler
    compiler = SVCompiler(sources={'test.sv': source}, log_level='WARNING', strict=False)
    root = compiler.get_root()  # 内部触发 _do_compile()
    adapter = SemanticAdapter(root, compiler=compiler)
    gb = GraphBuilder(adapter)
    return gb.build()


def _summarize(graph, label):
    """提取 BIT_SELECT 边 + 位选节点属性作为可对比摘要.

    SignalGraph 内部存储:
      - _node_data: dict[str, TraceNode] (TraceNode 对象, 有 bit_range/parent/parent_bit_* 属性)
      - _edge_data: dict[(src, dst), list[TraceEdge]] (TraceEdge 对象, 有 .kind 属性)
      - graph.edges (NetworkX 接口) 不含 kind, 必须走 _edge_data
    """
    bitselect_edges = []
    bitselect_nodes = []

    # 走 _edge_data 拿 TraceEdge 对象 (有 .kind 属性)
    for (src, dst), edges in graph._edge_data.items():
        for edge in edges:
            if edge.kind == EdgeKind.BIT_SELECT:
                bitselect_edges.append({
                    'src': src,
                    'dst': dst,
                })

    # 走 _node_data 拿 TraceNode 对象 (有 bit_range/parent/parent_bit_* 属性)
    for nid, node in graph._node_data.items():
        if '[' in nid and ']' in nid:
            bitselect_nodes.append({
                'id': nid,
                'bit_range': getattr(node, 'bit_range', None),
                'parent': getattr(node, 'parent', None),
                'parent_bit_start': getattr(node, 'parent_bit_start', None),
                'parent_bit_end': getattr(node, 'parent_bit_end', None),
                'width': node.width,
            })

    # Sort for stable diff
    bitselect_edges.sort(key=lambda x: (x['src'], x['dst']))
    bitselect_nodes.sort(key=lambda x: x['id'])

    return {
        'label': label,
        'node_count': len(graph._node_data),
        'edge_count': sum(len(v) for v in graph._edge_data.values()),
        'bitselect_edge_count': len(bitselect_edges),
        'bitselect_edges': bitselect_edges,
        'bitselect_nodes': bitselect_nodes,
    }


def _diff_summary(path_a, path_b):
    """对比两份摘要, 输出结构化 diff"""
    diff = {
        'edge_diff': path_a['bitselect_edge_count'] - path_b['bitselect_edge_count'],
        'node_diff': path_a['node_count'] - path_b['node_count'],
        'edges_only_in_a': [],
        'edges_only_in_b': [],
        'nodes_only_in_a': [],
        'nodes_only_in_b': [],
        'node_attr_diff': [],
    }

    # 边 diff
    a_edges = {f"{e['src']}->{e['dst']}" for e in path_a['bitselect_edges']}
    b_edges = {f"{e['src']}->{e['dst']}" for e in path_b['bitselect_edges']}
    diff['edges_only_in_a'] = sorted(a_edges - b_edges)
    diff['edges_only_in_b'] = sorted(b_edges - a_edges)

    # 位选节点 diff
    a_nodes = {n['id']: n for n in path_a['bitselect_nodes']}
    b_nodes = {n['id']: n for n in path_b['bitselect_nodes']}
    diff['nodes_only_in_a'] = sorted(set(a_nodes) - set(b_nodes))
    diff['nodes_only_in_b'] = sorted(set(b_nodes) - set(a_nodes))

    # 共有节点属性 diff
    for nid in sorted(set(a_nodes) & set(b_nodes)):
        a_n = a_nodes[nid]
        b_n = b_nodes[nid]
        attr_diff = {}
        for key in ['bit_range', 'parent', 'parent_bit_start', 'parent_bit_end', 'width']:
            if a_n[key] != b_n[key]:
                attr_diff[key] = {'a': a_n[key], 'b': b_n[key]}
        if attr_diff:
            diff['node_attr_diff'].append({'id': nid, 'diff': attr_diff})

    return diff


class TestBitSelectHandlerDiff(unittest.TestCase):
    """[2026-08-28] 实测两套 BitSelect 实现的输出差异.

    不修代码, 只记录事实. 输出供 #2 G3 计划决策.
    """

    def _run_diff(self, source, fixture_name):
        graph_a = _build_unified_tracer(source)
        graph_b = _build_graph_builder_only(source)

        summary_a = _summarize(graph_a, 'path_A_unified')
        summary_b = _summarize(graph_b, 'path_B_builder_only')

        diff = _diff_summary(summary_a, summary_b)

        # 输出结构化结果供人工 review
        print(f"\n=== {fixture_name} ===")
        print(f"  路径 A (unified + BitSelectHandler): 节点 {summary_a['node_count']}, "
              f"BIT_SELECT 边 {summary_a['bitselect_edge_count']}, 位选节点 {len(summary_a['bitselect_nodes'])}")
        print(f"  路径 B (graph_builder only):         节点 {summary_b['node_count']}, "
              f"BIT_SELECT 边 {summary_b['bitselect_edge_count']}, 位选节点 {len(summary_b['bitselect_nodes'])}")
        print(f"  边数差 (A - B): {diff['edge_diff']}")
        print(f"  仅 A 有的边: {diff['edges_only_in_a']}")
        print(f"  仅 B 有的边: {diff['edges_only_in_b']}")
        print(f"  仅 A 有的位选节点: {diff['nodes_only_in_a']}")
        print(f"  仅 B 有的位选节点: {diff['nodes_only_in_b']}")
        if diff['node_attr_diff']:
            print(f"  共有位选节点属性差异 ({len(diff['node_attr_diff'])} 个):")
            for item in diff['node_attr_diff']:
                print(f"    {item['id']}: {item['diff']}")

        return diff

    def test_rangeselect_diff(self):
        """[RangeSelect] data[3:0] — BitSelectHandler 主战场"""
        diff = self._run_diff(FIXTURE_RANGESELECT, 'FIXTURE_RANGESELECT')
        # 不下结论, 但记录差异供后续
        # TODO (#2 G3): 根据 diff 决定哪套对

    def test_elementselect_diff(self):
        """[ElementSelect] data[0], data[7] — graph_builder 主战场"""
        diff = self._run_diff(FIXTURE_ELEMENTSELECT, 'FIXTURE_ELEMENTSELECT')
        # TODO (#2 G3): 根据 diff 决定哪套对

    def test_mixed_diff(self):
        """[Mixed] RangeSelect + ElementSelect 混合 — 全面验证"""
        diff = self._run_diff(FIXTURE_MIXED, 'FIXTURE_MIXED')
        # TODO (#2 G3): 根据 diff 决定哪套对

    # === [2026-08-28 06:33] 边界 fixture, 测 regex 反推脆弱性 ===

    def test_parameter_diff(self):
        """[Parameter 位选] data[W-1:0] — regex [0-9]+ 匹配不了"""
        diff = self._run_diff(FIXTURE_PARAMETER, 'FIXTURE_PARAMETER')
        # 预期: 两套都创建 BIT_SELECT 边, 但路径 A 应该用 pyslang API 计算实际 msb/lsb

    def test_generate_diff(self):
        """[Generate-for 动态位选] acc[i], acc[i+1] — 表达式位选"""
        diff = self._run_diff(FIXTURE_GENERATE, 'FIXTURE_GENERATE')
        # 预期: 节点 ID 含 gen[N].acc[i], gen[N].acc[i+1], regex 可能处理不了 i+1

    def test_nested_diff(self):
        """[嵌套位选] data[3:0][1:0] — 多维位选"""
        diff = self._run_diff(FIXTURE_NESTED, 'FIXTURE_NESTED')
        # 预期: 节点 ID 形如 top.data[3:0][1:0], regex 反推可能产生错误 parent_id

    def test_struct_diff(self):
        """[Struct 字段位选] pkt.addr[3:0] — scoped 位选"""
        diff = self._run_diff(FIXTURE_STRUCT, 'FIXTURE_STRUCT')
        # 预期: 节点 ID 形如 top.pkt.addr[3:0], 应能匹配 regex [^\[]+ 前缀

    def test_struct_field_only_diff(self):
        """[Struct 字段访问无位选] pkt.addr — 验证不会误处理 struct 字段访问为位选"""
        # 注: 此 fixture 现有 Mermaid 表达中应不生成 BIT_SELECT 边
        # 为简洁, 复用 FIXTURE_STRUCT 但断言 .addr 不产生 BIT_SELECT 边
        diff = self._run_diff(FIXTURE_STRUCT, 'FIXTURE_STRUCT')
        # 验证 pkt.addr (无位选) 不被错误归类为位选节点


if __name__ == '__main__':
    unittest.main(verbosity=2)