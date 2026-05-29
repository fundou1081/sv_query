#==============================================================================
# signal_graph_viewer.py - 信号图可视化器
#==============================================================================
"""
强大的信号图可视化功能：
- 支持分层布局、风险热力图、覆盖状态标记
- 边表示数据流关系（驱动/时钟/复位）
- 可配置过滤、聚类、样式
- 输出 DOT / Mermaid / HTML
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import re


class SignalGraphViewer:
    """
    强大的信号图可视化器

    使用示例:
        viewer = SignalGraphViewer(graph)
        viewer.configure(
            layout='TB',
            show_edges=True,
            edge_filter={'exclude_clock', 'exclude_reset'},
            node_style={'risk_color': True, 'cover_marker': True},
            cluster_by='risk_level'
        )
        viewer.render_dot('/tmp/output.dot')
        viewer.render_mermaid('/tmp/output.mmd')
        viewer.render_html('/tmp/output.html')
    """

    # 颜色常量
    RISK_COLORS = {
        'CRITICAL': '#ff0000',
        'HIGH': '#ff8800',
        'MEDIUM': '#ffcc00',
        'LOW': '#00cc00',
    }

    COVER_COLORS = {
        'BOTH': '#00aa00',
        'SVA': '#0088ff',
        'COV': '#ffaa00',
        'NONE': '#ff6666',
    }

    NODE_KIND_SHAPES = {
        'REG': 'box',
        'PORT_IN': 'ellipse',
        'PORT_OUT': 'ellipse',
        'SIGNAL': 'diamond',
        'CONST': 'parallelogram',
        'INSTANTIATED_MODULE': 'folder',
    }

    EDGE_COLORS = {
        'DRIVER': '#333333',
        'CLOCK': '#8888ff',
        'RESET': '#ff8888',
        'CONNECTION': '#aaaaaa',
        'BIT_SELECT': '#aaaaaa',
        'DATA': '#666666',
    }

    def __init__(self, graph, sva_signals=None, cov_signals=None):
        """
        初始化可视化器

        Args:
            graph: SignalGraph 对象
            sva_signals: SVA 覆盖的信号名集合
            cov_signals: Coverage 覆盖的信号名集合
        """
        self.graph = graph
        self.sva_signals = sva_signals or set()
        self.cov_signals = cov_signals or set()

        # 默认配置
        self.config = {
            'layout': 'TB',           # TB (top-bottom) / LR (left-right)
            'show_edges': True,       # 是否显示边
            'edge_filter': set(),     # 'exclude_clock', 'exclude_reset', 'exclude_constant'
            'max_edges': 500,         # 边的最大数量（防止过于密集）
            'node_style': {
                'risk_color': True,   # 风险等级着色
                'cover_marker': True, # 覆盖状态标记
                'show_type': True,    # 显示节点类型
                'show_fan': True,     # 显示 fan-in/fan-out
            },
            'cluster_by': None,       # 'module', 'risk_level', 'cover_status', None
            'highlight_gaps': True,   # 高亮高风险无覆盖信号
            'min_risk_for_highlight': 20.0,
            'edge_labels': False,     # 显示边类型标签 (CLOCK/RESET/DRIVER)
            'edge_conditions': False, # 显示驱动条件 (如 if (cond) 才驱动)
            'rank_separation': 0.5,  # 层级间距
            'node_spacing': 0.3,      # 节点间距
        }

        self._risk_cache = {}

    def configure(self, **kwargs):
        """配置可视化参数"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
            elif key == 'node_style' and isinstance(value, dict):
                self.config['node_style'].update(value)
            elif key == 'edge_filter' and isinstance(value, (set, list)):
                self.config['edge_filter'] = set(value)
        return self

    def _compute_risk(self, node_id: str) -> Tuple[float, str]:
        """计算节点风险分数和等级"""
        if node_id in self._risk_cache:
            return self._risk_cache[node_id]

        node = self.graph.get_node(node_id)
        if node is None:
            return 0.0, 'LOW'

        fan_in = self.graph.in_degree(node_id)
        fan_out = self.graph.out_degree(node_id)

        func = fan_in * 3 + fan_out * 2
        func += 15 if fan_in >= 3 else 0
        func += 10 if fan_out >= 3 else 0

        timing = 15 if node.kind.name == 'REG' else 0
        timing += fan_in * 2

        total = func + timing
        if total >= 40:
            level = 'CRITICAL'
        elif total >= 25:
            level = 'HIGH'
        elif total >= 15:
            level = 'MEDIUM'
        else:
            level = 'LOW'

        self._risk_cache[node_id] = (total, level)
        return total, level

    def _get_cover_status(self, name: str) -> str:
        """获取覆盖状态"""
        has_sva = name in self.sva_signals
        has_cov = name in self.cov_signals
        if has_sva and has_cov:
            return 'BOTH'
        elif has_sva:
            return 'SVA'
        elif has_cov:
            return 'COV'
        return 'NONE'

    def _should_show_edge(self, src: str, dst: str, edge) -> bool:
        """判断边是否应该显示"""
        ek = edge.kind.name if hasattr(edge.kind, 'name') else str(edge.kind)

        if 'exclude_clock' in self.config['edge_filter'] and ek in ('CLOCK', 'PosEdge'):
            return False
        if 'exclude_reset' in self.config['edge_filter'] and ek in ('RESET', 'NegEdge'):
            return False
        if 'exclude_constant' in self.config['edge_filter']:
            if src.startswith("1'b") or dst.startswith("1'"):
                return False

        return True

    def _filter_edges(self, edges: List[Tuple]) -> List[Tuple]:
        """过滤边，防止过于密集"""
        result = []
        for src, dst in edges:
            edge = self.graph.get_edge(src, dst)
            if edge is None:
                continue
            if not self._should_show_edge(src, dst, edge):
                continue
            result.append((src, dst, edge))

        # 如果边太多，按风险排序，只保留高风险路径的边
        if len(result) > self.config['max_edges']:
            # 计算每条边的风险分（两端节点的风险分之和）
            edge_risks = []
            for src, dst, edge in result:
                r_src, _ = self._compute_risk(src)
                r_dst, _ = self._compute_risk(dst)
                edge_risks.append((src, dst, edge, r_src + r_dst))

            # 按风险排序，保留最高的
            edge_risks.sort(key=lambda x: x[3], reverse=True)
            result = [(s, d, e) for s, d, e, _ in edge_risks[:self.config['max_edges']]]

        return result

    def render_dot(self, output_path: str, title: str = "Signal Graph") -> str:
        """渲染为 DOT 格式"""
        dot_lines = [
            f'digraph signal_graph {{',
            f'  rankdir={self.config["layout"]};',
            '  node [shape=box style="rounded,filled" fontname="Helvetica"];',
            f'  label="{title}";',
            '  splines=ortho;',
            '  nodesep=0.3;',
            '  ranksep=0.5;',
            '',
        ]

        # 节点
        for node_id in self.graph.nodes():
            node = self.graph.get_node(node_id)
            if node is None:
                continue

            name = node_id.split('.')[-1]
            risk_score, risk_level = self._compute_risk(node_id)
            cover_status = self._get_cover_status(name)

            # 颜色
            if self.config['node_style']['risk_color']:
                fillcolor = self.RISK_COLORS.get(risk_level, '#cccccc') + '22'
            else:
                fillcolor = '#f0f0f0'

            shape = self.NODE_KIND_SHAPES.get(str(node.kind), 'box')

            # 标签
            labels = [name]
            if self.config['node_style']['show_type']:
                labels.append(str(node.kind).split('.')[-1])
            if self.config['node_style']['show_fan']:
                labels.append(f'In:{self.graph.in_degree(node_id)} Out:{self.graph.out_degree(node_id)}')

            # 覆盖标记
            if self.config['node_style']['cover_marker']:
                if cover_status == 'BOTH':
                    labels.append('✓🟡')
                elif cover_status == 'SVA':
                    labels.append('✓')
                elif cover_status == 'COV':
                    labels.append('🟡')
                elif risk_score >= self.config['min_risk_for_highlight']:
                    labels.append('🚨')

            # 标签中的换行符在 DOT 中需要用 \\n
            label_str = '\\n'.join(labels)

            color = self.COVER_COLORS.get(cover_status, '#888888') if self.config['node_style']['cover_marker'] else self.RISK_COLORS.get(risk_level, '#888888')

            # 聚类
            if self.config['cluster_by'] == 'risk_level':
                subgraph = f'cluster_{risk_level.lower()}'
            elif self.config['cluster_by'] == 'cover_status':
                subgraph = f'cluster_{cover_status.lower()}'
            else:
                subgraph = 'cluster_main'

            # 处理特殊字符 - node ID 中有单引号等必须用引号包裹
            name_escaped = name.replace('"', '\"').replace('[', '_').replace(']', '_').replace('-', '_')
            # 如果名字包含单引号或点号，用引号包裹 node ID
            if "'" in name or '.' in name:
                node_id = f'"{name_escaped}"'
            else:
                node_id = name_escaped
            dot_lines.append(f'  {subgraph}_{node_id}[label="{label_str}" shape={shape} fillcolor="{fillcolor}" color="{color}"];')

        dot_lines.append('')

        # 边
        if self.config['show_edges']:
            edges = list(self.graph.edges())
            filtered_edges = self._filter_edges(edges)

            for src, dst, edge in filtered_edges:
                ek = edge.kind.name if hasattr(edge.kind, 'name') else str(edge.kind)
                ek_short = ek.replace('EdgeKind.', '').replace('"', '\\"')

                # 处理单引号等特殊字符
                src_name_raw = src.split('.')[-1]
                dst_name_raw = dst.split('.')[-1]
                src_name_escaped = src_name_raw.replace('"', '\"').replace('[', '_').replace(']', '_').replace('-', '_')
                dst_name_escaped = dst_name_raw.replace('"', '\"').replace('[', '_').replace(']', '_').replace('-', '_')
                # 如果包含单引号，用引号包裹
                if "'" in src_name_raw:
                    src_name = f'"{src_name_escaped}"'
                else:
                    src_name = src_name_escaped
                if "'" in dst_name_raw:
                    dst_name = f'"{dst_name_escaped}"'
                else:
                    dst_name = dst_name_escaped

                # 边样式
                if ek in ('CLOCK', 'PosEdge'):
                    style = 'dashed'
                    color = self.EDGE_COLORS['CLOCK']
                elif ek in ('RESET', 'NegEdge'):
                    style = 'dashed'
                    color = self.EDGE_COLORS['RESET']
                else:
                    style = 'solid'
                    color = self.EDGE_COLORS.get(ek, '#666666')

                # 边标签
                label_parts = []
                if self.config['edge_labels']:
                    label_parts.append(ek_short)
                if self.config['edge_conditions'] and edge.condition:
                    # 简化条件：去掉 !! 前缀，缩短显示
                    cond = edge.condition.replace('!!', '').replace('&&', '&')
                    if len(cond) > 30:
                        cond = cond[:30] + '...'
                    label_parts.append(cond)
                
                if label_parts:
                    # 边用 xlabel 而非 label（ortho 模式不支持 edge labels）
                    label_attr = f' xlabel="{chr(10).join(label_parts)}"'
                else:
                    label_attr = ''

                dot_lines.append(f'  {src_name} -> {dst_name}[color="{color}" style={style}{label_attr}];')

        dot_lines.append('}')

        dot_content = '\n'.join(dot_lines)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(dot_content)

        return dot_content

    def render_mermaid(self, output_path: str = None) -> str:
        """渲染为 Mermaid 格式"""
        mmd_lines = [
            'flowchart ' + self.config['layout'],
        ]

        # 统计信息
        total = len(list(self.graph.nodes()))
        mmd_lines.append(f'    %% Total nodes: {total}')

        # 节点
        for node_id in self.graph.nodes():
            node = self.graph.get_node(node_id)
            if node is None:
                continue

            name = node_id.split('.')[-1]
            risk_score, risk_level = self._compute_risk(node_id)
            cover_status = self._get_cover_status(name)

            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)

            # 图标
            if risk_level == 'CRITICAL':
                icon = '🔴'
            elif risk_level == 'HIGH':
                icon = '🟠'
            elif risk_level == 'MEDIUM':
                icon = '🟡'
            else:
                icon = '🟢'

            # 覆盖标记
            if cover_status == 'BOTH':
                cover_icon = ' ✓🟡'
            elif cover_status == 'SVA':
                cover_icon = ' ✓'
            elif cover_status == 'COV':
                cover_icon = ' 🟡'
            elif risk_score >= self.config['min_risk_for_highlight']:
                cover_icon = ' 🚨'
            else:
                cover_icon = ''

            kind_short = str(node.kind).split('.')[-1][:3]

            mmd_lines.append(f'    N_{safe_name}["{icon} {name} ({kind_short}){cover_icon}"]')

        mmd_lines.append('')

        # 边
        if self.config['show_edges']:
            edges = list(self.graph.edges())
            filtered_edges = self._filter_edges(edges)

            for src, dst, edge in filtered_edges:
                ek = edge.kind.name if hasattr(edge.kind, 'name') else str(edge.kind)
                ek_short = ek.replace('EdgeKind.', '')

                src_name = re.sub(r'[^a-zA-Z0-9_]', '_', src.split('.')[-1])
                dst_name = re.sub(r'[^a-zA-Z0-9_]', '_', dst.split('.')[-1])

                # 边样式
                if ek in ('CLOCK', 'PosEdge'):
                    arrow = '-->'  # 虚线用 --
                elif ek in ('RESET', 'NegEdge'):
                    arrow = '-->'
                else:
                    arrow = '-->'

                # 边标签
                label_parts = []
                if self.config['edge_labels']:
                    label_parts.append(ek_short)
                if self.config['edge_conditions'] and edge.condition:
                    cond = edge.condition.replace('!!', '').replace('&&', '&')
                    if len(cond) > 25:
                        cond = cond[:25] + '...'
                    label_parts.append(cond)
                
                if label_parts:
                    label = '|'.join(label_parts)
                    mmd_lines.append(f'    N_{src_name} {arrow}|{label}| N_{dst_name}')
                else:
                    mmd_lines.append(f'    N_{src_name} {arrow} N_{dst_name}')

        mmd_content = '\n'.join(mmd_lines)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(mermaid_content)

        return mmd_content

    def render_html(self, output_path: str) -> str:
        """渲染为交互式 HTML"""
        # 先获取 DOT 和 Mermaid
        dot_content = self.render_dot(None)

        html_template = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Signal Graph Viewer</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { display: flex; gap: 20px; }
        .panel { flex: 1; border: 1px solid #ccc; padding: 15px; border-radius: 8px; }
        .panel h3 { margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        .controls { margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 5px; }
        .controls label { margin-right: 15px; }
        .mermaid { background: white; padding: 20px; border-radius: 5px; }
        .stats { display: flex; gap: 20px; margin-bottom: 15px; }
        .stat-box { background: #f0f8ff; padding: 10px 15px; border-radius: 5px; }
        .stat-box strong { font-size: 1.2em; color: #333; }
    </style>
</head>
<body>
    <h1>📊 Signal Graph Visualization</h1>

    <div class="controls">
        <label><input type="checkbox" id="showEdges" checked onchange="location.reload()"> Show Edges</label>
        <label><input type="checkbox" id="showLabels" onchange="location.reload()"> Show Edge Labels</label>
        <label>Layout: <select id="layout" onchange="location.reload()">
            <option value="TB">Top-Bottom</option>
            <option value="LR">Left-Right</option>
        </select></label>
    </div>

    <div class="stats">
        <div class="stat-box"><strong>{{TOTAL_NODES}}</strong><br>Total Nodes</div>
        <div class="stat-box"><strong>{{TOTAL_EDGES}}</strong><br>Total Edges</div>
        <div class="stat-box"><strong>{{HIGH_RISK}}</strong><br>High Risk</div>
    </div>

    <div class="container">
        <div class="panel" style="flex:2">
            <h3>🗺️ Graph View (Mermaid)</h3>
            <div class="mermaid">
{{MERMAID_CONTENT}}
            </div>
        </div>
        <div class="panel">
            <h3>📋 Legend</h3>
            <pre>
🔴 CRITICAL (≥40)
🟠 HIGH (≥25)
🟡 MEDIUM (≥15)
🟢 LOW (<15)

Edge Colors:
─ Black: Data/Driver
─ Blue: Clock
─ Red: Reset

Cover Status:
✓ = SVA covered
🟡 = Coverage covered
✓🟡 = Both
🚨 = Gap (high risk, no cover)
            </pre>
        </div>
    </div>

    <script>
        mermaid.initialize({
            startOnLoad: true,
            theme: 'base',
            flowchart: { useMaxWidth: true, htmlLabels: true }
        });
    </script>
</body>
</html>'''

        # 计算统计
        total_nodes = len(list(self.graph.nodes()))
        total_edges = len(list(self.graph.edges()))
        high_risk = sum(1 for n in self.graph.nodes() if self._compute_risk(n)[0] >= 25)

        # 渲染 Mermaid
        mermaid_content = self.render_mermaid(None)

        # 替换占位符
        html = html_template.replace('{{TOTAL_NODES}}', str(total_nodes))
        html = html.replace('{{TOTAL_EDGES}}', str(total_edges))
        html = html.replace('{{HIGH_RISK}}', str(high_risk))
        html = html.replace('{{MERMAID_CONTENT}}', mermaid_content)

        with open(output_path, 'w') as f:
            f.write(html)

        return html


def create_gap_viewer(graph, sva_signals, cov_signals, gap_signals, output_prefix):
    """
    创建验证缺口可视化（带数据流边）

    Args:
        graph: SignalGraph
        sva_signals: SVA 覆盖信号集合
        cov_signals: Coverage 覆盖信号集合
        gap_signals: 高风险缺口信号列表
        output_prefix: 输出文件前缀
    """
    gap_names = {g['name'] for g in gap_signals}

    viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
    viewer.configure(
        layout='TB',
        show_edges=True,
        edge_filter={'exclude_clock', 'exclude_reset'},
        max_edges=200,
        node_style={'risk_color': True, 'cover_marker': True, 'show_fan': True},
        highlight_gaps=True,
        min_risk_for_highlight=20.0,
    )

    # 渲染 DOT
    dot_path = f"{output_prefix}_gap.dot"
    dot_content = viewer.render_dot(dot_path, "Verification Gap Analysis")

    # 渲染 HTML
    html_path = f"{output_prefix}_gap.html"
    html_content = viewer.render_html(html_path)

    return dot_path, html_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Signal Graph Visualization')
    parser.add_argument('-f', '--file', required=True, help='SystemVerilog file')
    parser.add_argument('--dot', help='Output DOT file')
    parser.add_argument('--mmd', help='Output Mermaid file')
    parser.add_argument('--html', help='Output HTML file')
    parser.add_argument('--no-edges', action='store_true', help='Hide edges')
    parser.add_argument('--layout', default='TB', choices=['TB', 'LR'], help='Layout direction')
    parser.add_argument('--show-labels', action='store_true', help='Show edge labels')
    args = parser.parse_args()

    from trace.unified_tracer import UnifiedTracer
    from trace.core.sva_extractor import SVAExtractor
    from trace.core.covergroup_extractor import CovergroupExtractor

    with open(args.file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={args.file: source})
    graph = tracer.build_graph()
    sva = SVAExtractor({args.file: source}).extract()
    cov_list = CovergroupExtractor({args.file: source}).extract()

    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)

    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)

    viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
    viewer.configure(
        layout=args.layout,
        show_edges=not args.no_edges,
        edge_labels=args.show_labels,
        node_style={'risk_color': True, 'cover_marker': True, 'show_fan': True},
    )

    if args.dot:
        viewer.render_dot(args.dot, f"Signal Graph: {args.file}")
        print(f"DOT saved: {args.dot}")

    if args.html:
        viewer.render_html(args.html)
        print(f"HTML saved: {args.html}")

    if args.mmd:
        viewer.render_mermaid(args.mmd)
        print(f"Mermaid saved: {args.mmd}")