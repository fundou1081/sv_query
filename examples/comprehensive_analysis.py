#!/usr/bin/env python3
"""
综合实战案例2：信号图 + SVA + Coverage 一体化分析和可视化
输出：JSON + DOT + Mermaid
"""
import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent

sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

import json
import warnings
warnings.filterwarnings("ignore")

from trace.unified_tracer import UnifiedTracer
from trace.core.sva_extractor import SVAExtractor
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.models import NodeKind

def analyze_file(sv_file, output_prefix="/tmp/data_path_analysis"):
    """一体化分析：信号图 + SVA + Coverage"""
    with open(sv_file) as f:
        source = f.read()

    # 构建信号图
    tracer = UnifiedTracer(sources={sv_file: source})
    graph = tracer.build_graph()

    # 提取 SVA
    sva = SVAExtractor({sv_file: source}).extract()

    # 提取 Coverage
    cov_list = CovergroupExtractor({sv_file: source}).extract()

    # ===== 1. 信号分类 =====
    clocks = []
    resets = []
    data_nodes = []

    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        name = node_id.split('.')[-1]
        if node.is_clock or name in ('clk', 'clock'):
            clocks.append(node_id)
        elif node.is_reset or name in ('rst_n', 'rst', 'reset', 'resetn'):
            resets.append(node_id)
        else:
            data_nodes.append(node_id)

    # ===== 2. SVA/Coverage 覆盖信号 =====
    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)
    for seq in sva.sequences.values():
        sva_signals.update(seq.signals)

    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)

    # ===== 3. 风险评分 =====
    def risk_score(node_id):
        node = graph.get_node(node_id)
        if node is None:
            return 0, 0
        fan_in = graph.in_degree(node_id)
        fan_out = graph.out_degree(node_id)
        width_bits = max(1, node.width[1] - node.width[0] + 1) if node.width else 1
        is_reg = node.kind == NodeKind.REG
        name = node_id.split('.')[-1]

        func = fan_in * 3 + fan_out * 2 + width_bits * 0.3
        func += 15 if fan_in >= 3 else 0  # 汇聚
        func += 10 if fan_out >= 3 else 0  # 发散
        func += 12 if name not in sva_signals else 0  # 无 SVA
        func += 8 if name not in cov_signals else 0  # 无 Cov

        timing = 15 if is_reg else 0
        timing += fan_in * 2

        return round(func, 1), round(timing, 1)

    # ===== 4. 构建节点和边的 JSON =====
    nodes_json = []
    edges_json = []
    signal_to_node = {}

    for nid in graph.nodes():
        node = graph.get_node(nid)
        if node is None:
            continue
        name = nid.split('.')[-1]
        func_s, timing_s = risk_score(nid)
        func_level = 'CRITICAL' if func_s >= 40 else 'HIGH' if func_s >= 25 else 'MEDIUM' if func_s >= 15 else 'LOW'
        timing_level = 'CRITICAL' if timing_s >= 40 else 'HIGH' if timing_s >= 25 else 'MEDIUM' if timing_s >= 15 else 'LOW'

        n = {
            'id': nid,
            'name': name,
            'kind': str(node.kind),
            'width': node.width,
            'fan_in': graph.in_degree(nid),
            'fan_out': graph.out_degree(nid),
            'func_score': func_s,
            'func_level': func_level,
            'timing_score': timing_s,
            'timing_level': timing_level,
            'has_sva': name in sva_signals,
            'has_cov': name in cov_signals,
        }
        nodes_json.append(n)
        signal_to_node[name] = nid

    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        ek = edge.kind.name if hasattr(edge.kind, 'kind') else str(edge.kind)
        edges_json.append({'from': src, 'to': dst, 'kind': ek})

    # ===== 5. SVA/ Coverage 结构 =====
    sva_json = {
        'sequences': [{'id': k, 'signals': v.signals, 'timing_ops': v.timing_ops, 'clock': v.clock}
                      for k, v in sva.sequences.items()],
        'properties': [{'id': k, 'signals': v.signals, 'operators': v.operators, 'clock': v.clock,
                       'disable_iff': v.disable_iff}
                      for k, v in sva.properties.items()],
        'assertions': [{'id': a.id, 'kind': a.kind, 'property_ref': a.property_ref, 'signals': a.signals}
                       for a in sva.assertions],
    }

    cov_json = []
    for cg in cov_list:
        cg_data = {
            'name': cg.name,
            'coverpoints': []
        }
        for cp in cg.coverpoints:
            cp_data = {
                'signal': cp.signal,
                'bins': [{'name': b.name, 'kind': b.kind, 'values': b.values} for b in cp.bins]
            }
            cg_data['coverpoints'].append(cp_data)
        cov_json.append(cg_data)

    # ===== 6. 输出 JSON =====
    result = {
        'module': sv_file,
        'summary': {
            'total_nodes': len(graph.nodes()),
            'total_edges': len(graph.edges()),
            'clocks': len(clocks),
            'resets': len(resets),
            'data_signals': len(data_nodes),
            'sva_properties': len(sva.properties),
            'sva_assertions': len(sva.assertions),
            'covergroups': len(cov_list),
            'sva_coverage': len(sva_signals),
            'cov_coverage': len(cov_signals),
        },
        'nodes': nodes_json,
        'edges': edges_json,
        'sva': sva_json,
        'coverage': cov_json,
        'signal_refs': dict(sva.signal_refs),
    }

    json_path = f"{output_prefix}.json"
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"✓ JSON: {json_path}")

    # ===== 7. 输出 DOT =====
    dot_lines = ['digraph signal_graph {', '  rankdir=LR;', '  node [shape=box];']

    # 颜色映射
    level_colors = {'CRITICAL': '#ff0000', 'HIGH': '#ff8800', 'MEDIUM': '#ffcc00', 'LOW': '#00cc00'}
    kind_shapes = {'REG': 'box', 'PORT_IN': 'ellipse', 'PORT_OUT': 'ellipse', 'SIGNAL': 'diamond'}

    for n in nodes_json:
        color = level_colors.get(n['func_level'], '#888888')
        shape = kind_shapes.get(n['kind'], 'box')
        sva_mark = '✓' if n['has_sva'] else ''
        cov_mark = '🟡' if n['has_cov'] else ''
        label = f"{n['name']}\\nF={n['func_score']} T={n['timing_score']}{sva_mark}{cov_mark}"
        dot_lines.append(f'  "{n["id"]}" [label="{label}" shape={shape} color={color}];')

    for e in edges_json:
        dot_lines.append(f'  "{e["from"]}" -> "{e["to"]}" [label="{e["kind"]}"];')

    dot_lines.append('}')
    dot_path = f"{output_prefix}.dot"
    with open(dot_path, 'w') as f:
        f.write('\n'.join(dot_lines))
    print(f"✓ DOT: {dot_path}")

    # ===== 8. 输出 Mermaid =====
    mmd_lines = ['flowchart LR', '    direction LR', '    subgraph sig[Signal Graph]']
    style_lines = []

    for n in nodes_json:
        color = level_colors.get(n['func_level'], '#888888')
        shape = 'box' if n['kind'] == 'REG' else 'oval'
        mmd_lines.append(f'    {n["id"].replace(".","_").replace("[","_").replace("]","_")}[{n["name"]}]')

    for e in edges_json:
        fid = e['from'].replace(".","_").replace("[","_").replace("]","_")
        tid = e['to'].replace(".","_").replace("[","_").replace("]","_")
        mmd_lines.append(f'    {fid} -->{e["kind"]}-- {tid}')

    mmd_lines.append('    end')

    # 图例
    mmd_lines.append('    subgraph legend[Risk Level]')
    mmd_lines.append('    L_CRIT[🔴 CRITICAL]')
    mmd_lines.append('    L_HIGH[🟠 HIGH]')
    mmd_lines.append('    L_MED[🟡 MEDIUM]')
    mmd_lines.append('    L_LOW[🟢 LOW]')
    mmd_lines.append('    end')

    mmd_path = f"{output_prefix}.mmd"
    with open(mmd_path, 'w') as f:
        f.write('\n'.join(mmd_lines))
    print(f"✓ Mermaid: {mmd_path}")

    # ===== 9. 打印摘要 =====
    print(f"\n{'='*60}")
    print(f"综合分析: {sv_file}")
    print(f"{'='*60}")
    print(f"  节点: {len(graph.nodes())} | 边: {len(graph.edges())}")
    print(f"  时钟: {len(clocks)} | 复位: {len(resets)} | 数据: {len(data_nodes)}")
    print(f"  SVA 属性: {len(sva.properties)} | 断言: {len(sva.assertions)}")
    print(f"  Covergroup: {len(cov_list)}")
    print(f"\n  覆盖统计:")
    print(f"    SVA 覆盖信号: {len(sva_signals)}")
    print(f"    Coverage 覆盖信号: {len(cov_signals)}")

    return result


if __name__ == "__main__":
    sv_file = sys.argv[1] if len(sys.argv) > 1 else "sim/tests/regression/test_data_path.sv"
    output_prefix = sys.argv[2] if len(sys.argv) > 2 else "/tmp/data_path_analysis"
    analyze_file(sv_file, output_prefix)