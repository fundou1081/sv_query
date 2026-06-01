#==============================================================================
# visualize.py - 信号图可视化命令
#==============================================================================
"""
强大的信号图可视化功能

Usage:
  python run_cli.py visualize graph -f top.sv --dot /tmp/graph.dot --html /tmp/graph.html
  python run_cli.py visualize gap -f top.sv --html /tmp/gap.html
  python run_cli.py visualize graph -f top.sv --layout LR --no-edges
"""
import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
_project_root = _src_dir.parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import typer
import warnings
warnings.filterwarnings("ignore")

from trace.unified_tracer import UnifiedTracer
from trace.core.sva_extractor import SVAExtractor
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.signal_graph_viewer import SignalGraphViewer, create_gap_viewer

vis_app = typer.Typer(help="Signal graph visualization: DOT, Mermaid, HTML with data flow edges")


@vis_app.command(name="graph")
def graph(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),
    mmd_output: str = typer.Option(None, "--mmd", "-m", help="Output Mermaid file"),
    html_output: str = typer.Option(None, "--html", help="Output HTML file"),
    layout: str = typer.Option("TB", "--layout", "-l", help="Layout: TB (top-bottom) or LR (left-right)"),
    no_edges: bool = typer.Option(False, "--no-edges", help="Hide edges"),
    show_labels: bool = typer.Option(False, "--show-labels", help="Show edge labels (type)"),
    show_conditions: bool = typer.Option(False, "--show-conditions", help="Show driver conditions on edges"),
    max_edges: int = typer.Option(200, "--max-edges", help="Max edges to display"),
    exclude_clock: bool = typer.Option(False, "--exclude-clock", help="Exclude clock edges"),
    exclude_reset: bool = typer.Option(False, "--exclude-reset", help="Exclude reset edges"),
    cluster_modules: bool = typer.Option(False, "--cluster-modules", help="Cluster nodes by module"),
    layout_engine: str = typer.Option("dot", "--layout-engine", help="Layout engine: dot, neato, fdp"),
    cache: bool = typer.Option(False, "--cache", help="Use cache for faster loading (skip re-parsing if file unchanged)"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
) -> None:
    """可视化信号图（包含数据流关系）"""
    include_dirs = include.split(',') if include else None
    sources = None if filelist else {file: open(file).read()}
    _run_graph_visualization(file, dot_output, mmd_output, html_output, layout, no_edges, show_labels, show_conditions, max_edges, exclude_clock, exclude_reset, cluster_modules, layout_engine, cache, include_dirs, filelist, sources)


@vis_app.command(name="gap")
def gap(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),
    html_output: str = typer.Option(None, "--html", help="Output HTML file"),
    min_risk: float = typer.Option(20.0, "--min-risk", "-r", help="Minimum risk threshold"),
    cache: bool = typer.Option(False, "--cache", help="Use cache for faster loading"),
) -> None:
    """可视化验证缺口（高亮无覆盖的高风险信号及其数据流关系）"""
    _run_gap_visualization(file, dot_output, html_output, min_risk, cache)


def _run_graph_visualization(file, dot_output, mmd_output, html_output, layout, no_edges, show_labels, show_conditions, max_edges, exclude_clock, exclude_reset, cluster_modules=False, layout_engine='dot', cache=False, include_dirs=None, filelist=None, sources=None):
    """可视化信号图（包含数据流关系）

    Args:
        cache: 使用缓存加速（基于文件 hash）
        include_dirs: include 搜索路径列表
        filelist: 文件列表路径
        sources: 源代码字典（如果提供 filelist 则设为 None）
    """
    if sources is None:
        with open(file) as f:
            sources = {file: f.read()}

    tracer = UnifiedTracer(sources=sources, include_dirs=include_dirs, filelist=filelist)
    graph = tracer.build_graph(use_cache=cache)
    sva = SVAExtractor(sources).extract()
    cov_list = CovergroupExtractor(sources).extract()

    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)

    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)

    viewer = SignalGraphViewer(graph, sva_signals, cov_signals)

    edge_filter = set()
    if exclude_clock:
        edge_filter.add('exclude_clock')
    if exclude_reset:
        edge_filter.add('exclude_reset')

    viewer.configure(
        layout=layout,
        show_edges=not no_edges,
        edge_labels=show_labels,
        edge_conditions=show_conditions,
        max_edges=max_edges,
        edge_filter=edge_filter,
        cluster_modules=cluster_modules,
        layout_engine=layout_engine,
        node_style={'risk_color': True, 'cover_marker': True, 'show_fan': True, 'show_type': True},
    )

    if dot_output:
        viewer.render_dot(dot_output, f"Signal Graph: {file}")
        print(f"✓ DOT: {dot_output}")

    if mmd_output:
        viewer.render_mermaid(mmd_output)
        print(f"✓ Mermaid: {mmd_output}")

    if html_output:
        viewer.render_html(html_output)
        print(f"✓ HTML: {html_output}")

    if not (dot_output or mmd_output or html_output):
        print("No output specified. Use --dot, --mmd, or --html")


def _run_gap_visualization(file, dot_output, html_output, min_risk, cache=False):
    with open(file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={file: source})
    graph = tracer.build_graph(use_cache=cache)
    sva = SVAExtractor({file: source}).extract()
    cov_list = CovergroupExtractor({file: source}).extract()

    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)

    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)

    # 找出高风险缺口
    gap_signals = []
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue

        fan_in = graph.in_degree(node_id)
        fan_out = graph.out_degree(node_id)
        func = fan_in * 3 + fan_out * 2
        func += 15 if fan_in >= 3 else 0

        if func >= min_risk:
            name = node_id.split('.')[-1]
            has_sva = name in sva_signals
            has_cov = name in cov_signals
            if not (has_sva or has_cov):
                gap_signals.append({
                    'name': name,
                    'node_id': node_id,
                    'risk_score': func,
                })

    gap_signals.sort(key=lambda x: x['risk_score'], reverse=True)

    if dot_output:
        viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
        viewer.configure(
            layout='TB',
            show_edges=True,
            edge_filter={'exclude_clock', 'exclude_reset'},
            max_edges=200,
            node_style={'risk_color': True, 'cover_marker': True, 'show_fan': True},
            highlight_gaps=True,
            min_risk_for_highlight=min_risk,
        )
        viewer.render_dot(dot_output, f"Verification Gap: {file}")
        print(f"✓ DOT: {dot_output}")

        # 渲染为 PNG (正方形比例)
        png_output = dot_output.replace('.dot', '.png')
        import subprocess
        try:
            # 使用 -G 指定图形属性，确保正方形输出（不裁剪）
            subprocess.run(['dot', '-Tpng', '-Gsize=10', '-Gratio=compress',
                           dot_output, '-o', png_output], check=True, capture_output=True)
            print(f"✓ PNG: {png_output}")
        except Exception as e:
            # fallback: 不带额外参数
            try:
                subprocess.run(['dot', '-Tpng', dot_output, '-o', png_output],
                             check=True, capture_output=True)
                print(f"✓ PNG: {png_output}")
            except Exception as e2:
                print(f"  (PNG渲染失败: {e2})")

    if html_output:
        viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
        viewer.configure(
            layout='TB',
            show_edges=True,
            edge_filter={'exclude_clock', 'exclude_reset'},
            max_edges=200,
            node_style={'risk_color': True, 'cover_marker': True, 'show_fan': True},
            highlight_gaps=True,
            min_risk_for_highlight=min_risk,
        )
        viewer.render_html(html_output)
        print(f"✓ HTML: {html_output}")

    print(f"\n  📊 Gap signals: {len(gap_signals)} (risk >= {min_risk})")


if __name__ == "__main__":
    typer.run(vis_app)