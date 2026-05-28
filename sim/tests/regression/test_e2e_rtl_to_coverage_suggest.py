# test_e2e_rtl_to_coverage_suggest.py - 端到端测试：RTL → 自动 Coverage 建议
#
# 场景: 给定 RTL 层次结构，自动分析信号类型，
#       生成 control path 和 data path 的 coverage 建议。
#
# 核心能力:
#   1. 识别信号类型 (data/control/addr)
#   2. 追溯信号的驱动链和约束
#   3. 根据信号特性生成 coverage bins 建议
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind, EdgeKind


def _build_graph(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    return tracer.build_graph(), tracer


def _classify_signal(graph, signal_id):
    """根据信号名称和位宽分类"""
    node = graph.get_node(signal_id)
    if node is None:
        return 'unknown'

    name = signal_id.split('.')[-1].lower()

    # Control signals
    if any(k in name for k in ['valid', 'ready', 'enable', 'en', 'req', 'ack']):
        return 'control'
    # Address signals
    if 'addr' in name:
        return 'addr'
    # Data signals (default)
    return 'data'


def _suggest_coverage(signal_id, sig_type, graph):
    """根据信号类型生成 coverage 建议"""
    node = graph.get_node(signal_id)
    if node is None:
        return None

    name = signal_id.split('.')[-1]
    width = node.width if hasattr(node, 'width') else (0, 0)

    suggestions = {
        'signal': signal_id,
        'type': sig_type,
        'width': width,
        'coverpoint': name,
        'bins': [],
        'cross_with': [],
    }

    if sig_type == 'control':
        suggestions['bins'] = [
            {'name': f'{name}_idle', 'values': '0', 'desc': 'inactive state'},
            {'name': f'{name}_active', 'values': '1', 'desc': 'active state'},
        ]
        # Control signals should cross with data
        data_signals = _find_related_data_signals(graph, signal_id)
        suggestions['cross_with'] = data_signals

    elif sig_type == 'data':
        # Data signals: range bins + extremes
        if width and isinstance(width, tuple) and len(width) >= 2:
            msb, lsb = width[0], width[1]
            try:
                bits = abs(int(msb) - int(lsb)) + 1
                max_val = (1 << bits) - 1
                mid = max_val // 2
                suggestions['bins'] = [
                    {'name': f'{name}_zero', 'values': '0', 'desc': 'minimum value'},
                    {'name': f'{name}_low', 'values': f'[1:{mid-1}]', 'desc': 'low range'},
                    {'name': f'{name}_mid', 'values': f'[{mid}:{max_val-1}]', 'desc': 'mid range'},
                    {'name': f'{name}_max', 'values': f'{max_val}', 'desc': 'maximum value'},
                ]
            except (ValueError, TypeError):
                pass

        # Data signals should cross with control
        control_signals = _find_related_control_signals(graph, signal_id)
        suggestions['cross_with'] = control_signals

    elif sig_type == 'addr':
        # Address signals: aligned boundaries
        suggestions['bins'] = [
            {'name': f'{name}_zero', 'values': '0', 'desc': 'base address'},
            {'name': f'{name}_low', 'values': '[1:63]', 'desc': 'low range'},
            {'name': f'{name}_mid', 'values': '[64:191]', 'desc': 'mid range'},
            {'name': f'{name}_high', 'values': '[192:254]', 'desc': 'high range'},
            {'name': f'{name}_max', 'values': '255', 'desc': 'top address'},
        ]

    return suggestions


def _find_related_data_signals(graph, control_signal):
    """找与 control 信号相关的 data 信号"""
    # 同模块的 data 信号
    module = control_signal.split('.')[0] if '.' in control_signal else ''
    related = []
    for n in graph.nodes():
        if n.startswith(module + '.') and n != control_signal:
            name = n.split('.')[-1].lower()
            if any(k in name for k in ['data', 'payload', 'value']):
                related.append(n)
    return related


def _find_related_control_signals(graph, data_signal):
    """找与 data 信号相关的 control 信号"""
    module = data_signal.split('.')[0] if '.' in data_signal else ''
    related = []
    for n in graph.nodes():
        if n.startswith(module + '.') and n != data_signal:
            name = n.split('.')[-1].lower()
            if any(k in name for k in ['valid', 'ready', 'enable', 'en']):
                related.append(n)
    return related


def _find_signals_by_driver(graph, signal_id):
    """通过驱动链找相关信号"""
    related = []
    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if edge.kind == EdgeKind.DRIVER and dst == signal_id:
            related.append(src)
    return related


def generate_coverage_report(graph):
    """生成完整的 coverage 建议报告"""
    report = {
        'control_path': [],
        'data_path': [],
        'cross_coverage': [],
    }

    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        # 只处理模块级信号
        if node.kind not in (NodeKind.SIGNAL, NodeKind.PORT_IN, NodeKind.PORT_OUT,
                             NodeKind.REG, NodeKind.CLASS_INSTANCE_PROPERTY,
                             NodeKind.CLASS_PROPERTY):
            continue
        
        # 跳过 clk/rst 信号
        name_lower = node_id.split('.')[-1].lower()
        if name_lower in ('clk', 'clk_i', 'rst', 'rst_n', 'rst_ni'):
            continue

        sig_type = _classify_signal(graph, node_id)
        suggestion = _suggest_coverage(node_id, sig_type, graph)

        if suggestion is None:
            continue

        if sig_type == 'control':
            report['control_path'].append(suggestion)
        elif sig_type == 'data':
            report['data_path'].append(suggestion)
        elif sig_type == 'addr':
            report['data_path'].append(suggestion)

        if suggestion['cross_with']:
            for related in suggestion['cross_with']:
                report['cross_coverage'].append({
                    'signal_a': node_id,
                    'signal_b': related,
                    'reason': f'{sig_type} signal should cross with related signal',
                })

    return report


class TestRTLCoverageSuggest(unittest.TestCase):
    """RTL → Coverage 建议"""

    def test_control_path_coverage(self):
        """[端到端] Control Path Coverage

        RTL:
        module arbiter(input clk, valid, ready, output logic grant);
            logic state;
            always_ff @(posedge clk) begin
                if (valid && ready) grant <= 1;
                else grant <= 0;
            end
        endmodule

        期望生成:
        - coverpoint valid: bins idle/active
        - coverpoint ready: bins idle/active
        - cross valid x ready
        """
        source = '''module arbiter(input clk, input valid, input ready, output logic grant);
    logic state;
    always_ff @(posedge clk) begin
        if (valid && ready) grant <= 1;
        else grant <= 0;
    end
endmodule'''
        graph, _ = _build_graph(source)
        report = generate_coverage_report(graph)

        print("\n=== Control Path ===")
        for cp in report['control_path']:
            print(f"  {cp['signal']} ({cp['type']}):")
            for b in cp['bins']:
                print(f"    {b['name']} = {b['values']}")

        # 验证
        control_signals = [cp['signal'] for cp in report['control_path']]
        self.assertTrue(any('valid' in s for s in control_signals),
            "valid 应被识别为 control 信号")
        self.assertTrue(any('ready' in s for s in control_signals),
            "ready 应被识别为 control 信号")

        # 验证 cross
        print(f"\n=== Cross Coverage ===")
        for cross in report['cross_coverage']:
            print(f"  {cross['signal_a']} x {cross['signal_b']}")

    def test_data_path_coverage(self):
        """[端到端] Data Path Coverage

        RTL:
        module datapath(input clk, input [7:0] data_in, output logic [7:0] data_out);
            always_ff @(posedge clk) data_out <= data_in + 1;
        endmodule

        期望生成:
        - coverpoint data_in: bins zero/low/mid/max
        - coverpoint data_out: bins zero/low/mid/max
        """
        source = '''module datapath(input clk, input [7:0] data_in, output logic [7:0] data_out);
    always_ff @(posedge clk) data_out <= data_in + 1;
endmodule'''
        graph, _ = _build_graph(source)
        report = generate_coverage_report(graph)

        print("\n=== Data Path ===")
        for dp in report['data_path']:
            print(f"  {dp['signal']} ({dp['type']}, {dp['width']}):")
            for b in dp['bins']:
                print(f"    {b['name']} = {b['values']}")

        # 验证
        data_signals = [dp['signal'] for dp in report['data_path']]
        self.assertTrue(any('data_in' in s for s in data_signals),
            "data_in 应被识别为 data 信号")
        self.assertTrue(any('data_out' in s for s in data_signals),
            "data_out 应被识别为 data 信号")

    def test_mixed_control_data(self):
        """[端到端] 混合 Control + Data

        RTL: AXI-like 握手接口
        module axi_lite(input clk,
            input awvalid, output awready,
            input [31:0] awaddr,
            input wvalid, output wready,
            input [31:0] wdata,
            output bvalid, input bready
        );
        """
        source = '''module axi_lite(input clk,
    input awvalid, output awready,
    input [31:0] awaddr,
    input wvalid, output wready,
    input [31:0] wdata,
    output bvalid, input bready
);
    assign awready = 1;
    assign wready = 1;
    assign bvalid = 1;
endmodule'''
        graph, _ = _build_graph(source)
        report = generate_coverage_report(graph)

        print("\n=== AXI-Lite Coverage Report ===")
        print(f"  Control signals: {len(report['control_path'])}")
        for cp in report['control_path']:
            print(f"    {cp['signal']}")
        print(f"  Data signals: {len(report['data_path'])}")
        for dp in report['data_path']:
            print(f"    {dp['signal']}: {len(dp['bins'])} bins")
        print(f"  Cross coverage: {len(report['cross_coverage'])}")

        # 验证
        self.assertGreater(len(report['control_path']), 0, "应有 control 信号")
        self.assertGreater(len(report['data_path']), 0, "应有 data 信号")

    def test_class_with_constraint_coverage_suggest(self):
        """[端到端] Class + Constraint → Coverage 建议

        class my_transaction;
            rand bit [7:0] addr;
            rand bit [31:0] data;
            rand bit [1:0] burst_type;

            constraint c_burst {
                burst_type inside {0, 1, 2};
            }
        endclass

        期望:
        - addr: addr 类型 coverage (aligned boundaries)
        - data: data 类型 coverage (range bins)
        - burst_type: control 类型 coverage (special values)
        """
        source = '''class my_transaction;
    rand bit [7:0] addr;
    rand bit [31:0] data;
    rand bit [1:0] burst_type;

    constraint c_burst {
        burst_type inside {0, 1, 2};
    }

    covergroup cg;
        coverpoint addr;
        coverpoint data;
        coverpoint burst_type;
    endgroup

    function new();
        cg = new();
    endfunction
endclass

module top; endmodule'''
        graph, _ = _build_graph(source)
        report = generate_coverage_report(graph)

        print("\n=== Transaction Coverage Suggestions ===")
        for dp in report['data_path']:
            print(f"  {dp['signal']} ({dp['type']}): {len(dp['bins'])} bins suggested")
            for b in dp['bins'][:3]:
                print(f"    {b['name']} = {b['values']}")

        # 验证
        self.assertGreater(len(report['data_path']), 0, "应有 data path 建议")


if __name__ == '__main__':
    unittest.main()
