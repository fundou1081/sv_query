# ==============================================================================
# visualize.py - 信号图可视化命令
# ==============================================================================
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
import warnings

import typer

warnings.filterwarnings("ignore")

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.signal_graph_viewer import SignalGraphViewer
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer

vis_app = typer.Typer(help="Signal graph visualization: DOT, Mermaid, HTML with data flow edges")


@vis_app.command(name="graph")
def graph(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
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
    cache: bool = typer.Option(
        False, "--cache", help="Use cache for faster loading (skip re-parsing if file unchanged)"
    ),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    module_only: bool = typer.Option(False, "--module-only", help="Show only top-module signals (skip sub-module internals, show only port/instantiation level)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): raise on elaboration error. Use --no-strict 优雅降级存部分图 (供分析不完整项目如 NaplesPU/OpenTitan)"),
) -> None:
    """可视化信号图（包含数据流关系）

    [ADD 2026-06-11 Req-9] --file 或 --filelist 二选一, 走 _build_tracer 统一 helper.
    """
    from cli._common import _build_tracer, handle_compilation_error
    from trace.core.compiler import CompilationError

    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    try:
        include_dirs = include.split(",") if include else None
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
            include_dirs=include_dirs,
        )
        graph = tracer.build_graph(use_cache=cache)
        # SVA/Covergroup 提取
        sources_for_extractors = tracer._sources
        sva = SVAExtractor(sources_for_extractors).extract()
        cov_list = CovergroupExtractor(sources_for_extractors).extract()
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

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
        edge_filter.add("exclude_clock")
    if exclude_reset:
        edge_filter.add("exclude_reset")

    viewer.configure(
        layout=layout,
        show_edges=not no_edges,
        edge_labels=show_labels,
        edge_conditions=show_conditions,
        max_edges=max_edges,
        edge_filter=edge_filter,
        cluster_modules=cluster_modules,
        layout_engine=layout_engine,
        module_only=module_only,
    )

    if dot_output:
        viewer.render_dot(output_path=dot_output)
        typer.echo(f"✓ DOT: {dot_output}")
    elif mmd_output:
        viewer.render_mermaid(output_path=mmd_output)
        typer.echo(f"✓ Mermaid: {mmd_output}")
    elif html_output:
        viewer.render_html(output_path=html_output)
        typer.echo(f"✓ HTML: {html_output}")
    else:
        # 默认输出到 stdout (DOT 格式)
        typer.echo(viewer.render_dot(output_path=None))


@vis_app.command(name="dataflow")
def dataflow(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    module: str = typer.Option(None, "--module", "-m", help="Focus on specific module (filter edges to this module's signals)"),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default False, use --strict for partial AST)"),
    include_clk_rst: bool = typer.Option(False, "--with-clk-rst", help="Include clock/reset nodes"),
) -> None:
    """数据流图: 显示 data path (运算表达式) + 关键 control 边 (enable/valid/mux sel)

    基于 SignalGraph 自动分类 clock/reset/control/data, 生成 DOT 图:
    - 数据边: 蓝色实线,标注运算表达式 (a+b, {rx, sreg[10:1]})
    - 控制边: 橙色虚线 (valid/ready/enable → 数据目标)
    - MUX 目标: 加粗边 (多源数据汇聚)
    - 寄存器: 粗边框
    """
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    from trace.core.graph.analyzer.dataflow_viz import generate_dataflow_dot
    from trace.core.compiler import CompilationError
    from cli._common import _build_tracer, handle_compilation_error

    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    include_dirs = include.split(",") if include else None
    try:
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
            include_dirs=include_dirs,
        )
        graph = tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    classification = classify_graph(graph)
    typer.echo(f"  Data nodes: {len(classification.data_nodes)}", err=True)
    typer.echo(f"  Control nodes: {len(classification.control_nodes)}", err=True)
    typer.echo(f"  Clock nodes: {len(classification.clock_nodes)}", err=True)

    dot = generate_dataflow_dot(graph, module or file or filelist or "", classification, include_clk_rst=include_clk_rst)

    if dot_output:
        Path(dot_output).write_text(dot)
        typer.echo(f"✓ DOT: {dot_output}")
    else:
        typer.echo(dot)


@vis_app.command(name="pipeline")
def pipeline(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    module: str = typer.Option(None, "--module", "-m", help="Focus on specific module"),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default False, use --strict for partial AST)"),
) -> None:
    """Pipeline 流图: 检测 register chain → 划分 time cycle/stage

    从 SignalGraph 自动检测 pipeline 结构:
    - 识别 pipeline registers (排除 clock/reset/state-machine regs)
    - 每个 stage 一个 subgraph: 含 registers + 组合逻辑
    - 控制信号 (valid/stall) 标记为跨 stage 虚线
    - 左→右布局 = 时间流方向
    """
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    from trace.core.graph.analyzer.pipeline_viz import detect_pipeline, generate_pipeline_dot
    from trace.core.compiler import CompilationError
    from cli._common import _build_tracer, handle_compilation_error

    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    include_dirs = include.split(",") if include else None
    try:
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
            include_dirs=include_dirs,
        )
        graph = tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    classification = classify_graph(graph)
    info = detect_pipeline(graph, classification)
    info.module_name = module or file or filelist or ""

    typer.echo(f"  Pipeline regs: {len(info.pipeline_regs)}", err=True)
    typer.echo(f"  Control regs: {len(info.control_regs)}", err=True)
    typer.echo(f"  State regs: {len(info.state_regs)}", err=True)
    typer.echo(f"  Stages: {info.total_latency}", err=True)

    dot = generate_pipeline_dot(graph, info, classification)

    if dot_output:
        Path(dot_output).write_text(dot)
        typer.echo(f"✓ DOT: {dot_output}")
    else:
        typer.echo(dot)


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


def _run_graph_visualization(
    file,
    dot_output,
    mmd_output,
    html_output,
    layout,
    no_edges,
    show_labels,
    show_conditions,
    max_edges,
    exclude_clock,
    exclude_reset,
    cluster_modules=False,
    layout_engine="dot",
    cache=False,
    include_dirs=None,
    filelist=None,
    sources=None,
    module_only=False,
    strict=True,
):
    """可视化信号图（包含数据流关系）

    Args:
        cache: 使用缓存加速（基于文件 hash）
        include_dirs: include 搜索路径列表
        filelist: 文件列表路径
        sources: 源代码字典（如果提供 filelist 则设为 None）
        module_only: 只显示顶层模块信号（跳过子模块内部信号）
    """
    if sources is None and file:
        # 没提供 filelist 时读 file
        with open(file) as f:
            sources = {file: f.read()}

    tracer = UnifiedTracer(sources=sources, include_dirs=include_dirs, filelist=filelist, strict=strict)
    graph = tracer.build_graph(use_cache=cache)

    # SVA/Covergroup 提取需要源码
    # 使用 filelist 时，源码已在 tracer 的 compiler 里，重复编译会导致 redefinition
    if sources is None and filelist:
        # 从 tracer 的 compiler 复用已加载的 sources
        sources_for_extractors = tracer._get_compiler()._sources
        sva = SVAExtractor(sources_for_extractors).extract()
        cov_list = CovergroupExtractor(sources_for_extractors).extract()
    elif sources:
        sva = SVAExtractor(sources, strict=strict).extract()
        cov_list = CovergroupExtractor(sources, strict=strict).extract()
    else:
        sva = None
        cov_list = []

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
        edge_filter.add("exclude_clock")
    if exclude_reset:
        edge_filter.add("exclude_reset")

    viewer.configure(
        layout=layout,
        show_edges=not no_edges,
        edge_labels=show_labels,
        edge_conditions=show_conditions,
        max_edges=max_edges,
        edge_filter=edge_filter,
        cluster_modules=cluster_modules,
        layout_engine=layout_engine,
        module_only=module_only,
        node_style={"risk_color": True, "cover_marker": True, "show_fan": True, "show_type": True},
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
            name = node_id.split(".")[-1]
            has_sva = name in sva_signals
            has_cov = name in cov_signals
            if not (has_sva or has_cov):
                gap_signals.append(
                    {
                        "name": name,
                        "node_id": node_id,
                        "risk_score": func,
                    }
                )

    gap_signals.sort(key=lambda x: x["risk_score"], reverse=True)

    if dot_output:
        viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
        viewer.configure(
            layout="TB",
            show_edges=True,
            edge_filter={"exclude_clock", "exclude_reset"},
            max_edges=200,
            node_style={"risk_color": True, "cover_marker": True, "show_fan": True},
            highlight_gaps=True,
            min_risk_for_highlight=min_risk,
        )
        viewer.render_dot(dot_output, f"Verification Gap: {file}")
        print(f"✓ DOT: {dot_output}")

        # 渲染为 PNG (正方形比例)
        png_output = dot_output.replace(".dot", ".png")
        import subprocess

        try:
            # 使用 -G 指定图形属性，确保正方形输出（不裁剪）
            subprocess.run(
                ["dot", "-Tpng", "-Gsize=10", "-Gratio=compress", dot_output, "-o", png_output],
                check=True,
                capture_output=True,
            )
            print(f"✓ PNG: {png_output}")
        except Exception:
            # fallback: 不带额外参数
            try:
                subprocess.run(["dot", "-Tpng", dot_output, "-o", png_output], check=True, capture_output=True)
                print(f"✓ PNG: {png_output}")
            except Exception as e2:
                print(f"  (PNG渲染失败: {e2})")

    if html_output:
        viewer = SignalGraphViewer(graph, sva_signals, cov_signals)
        viewer.configure(
            layout="TB",
            show_edges=True,
            edge_filter={"exclude_clock", "exclude_reset"},
            max_edges=200,
            node_style={"risk_color": True, "cover_marker": True, "show_fan": True},
            highlight_gaps=True,
            min_risk_for_highlight=min_risk,
        )
        viewer.render_html(html_output)
        print(f"✓ HTML: {html_output}")

    print(f"\n  📊 Gap signals: {len(gap_signals)} (risk >= {min_risk})")


# ==============================================================================
# [PR1 2026-06-13] visualize module — 1 box = 1 sub-module instance
# ==============================================================================

@vis_app.command(name="module")
def module(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist for multi-file projects"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    target: str = typer.Option(
        "top", "--target", "-t",
        help="Target module name to visualize (e.g. axi_xbar_intf)",
    ),
    depth: int = typer.Option(
        1, "--depth", "-d",
        help="Instance hierarchy depth to include (1 = direct children only)",
    ),
    output_json: str = typer.Option(
        None, "--output-json", "-j",
        help="Write module extraction to JSON (for golden diff)",
    ),
    dot_output: str = typer.Option(
        None, "--dot", help="Write DOT graph to file",
    ),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default non-strict)"),
) -> None:
    """[PR1 2026-06-13] L1 module-level visualization. 1 box = 1 sub-module instance.

    从 SignalGraph 提取所有 INSTANTIATED_MODULE 节点, 按 instance hierarchy
    截断名字, 折叠 array instance. 用于项目架构 review.
    """
    from trace.core.module_extractor import extract_module_from_graph

    if not file and not filelist:
        typer.echo("Error: need --file or --filelist", err=True)
        raise typer.Exit(1)

    include_dirs = include.split(",") if include else None
    try:
        if filelist:
            tracer = UnifiedTracer(
                filelist=filelist, include_dirs=include_dirs, strict=strict,
            )
        else:
            with open(file) as f:
                sources = {file: f.read()}
            tracer = UnifiedTracer(
                sources=sources, include_dirs=include_dirs, strict=strict,
            )
    except Exception as e:
        typer.echo(f"Error building tracer: {e}", err=True)
        raise typer.Exit(1)

    graph = tracer.build_graph()
    result = extract_module_from_graph(
        graph, target_module=target, max_depth=depth,
    )

    # [PR1 2026-06-14] AST 优先: graph builder 在复杂项目上不稳定 (pyslang
    # 预 elabor 会 drop module, 导致 graph 不完整). AST 路径是 ground truth.
    # 如果 graph 抽取为空, 走 AST. 优先用 AST.
    # 注: pyslang 顶 elabor 也 flaky (topInstances 偶发为空), 最多重试 3 次.
    ast_result = None
    ast_attempts = 0
    while ast_attempts < 3:
        ast_attempts += 1
        try:
            from trace.core.module_extractor import extract_module
            from trace.core.semantic_adapter import SemanticAdapter
            semantic_adapter = SemanticAdapter(tracer._get_compiler().get_root())
            ast_result = extract_module(semantic_adapter, target, max_depth=depth)
            if len(ast_result.instances) > 0:
                break
            # AST 空, 重试 (重设 compiler)
            tracer._compiler = None
            tracer._graph = None
            tracer._adapter = None
            tracer.build_graph(force=True)
        except Exception as e:
            break

    # 如果 AST 路径有结果, 优先用 AST. 否则用 graph.
    if ast_result and len(ast_result.instances) > 0:
        result = ast_result
    # 如果 graph 有结果且 AST 为空, 用 graph (回退)

    typer.echo(f"Target: {result.top_module}")
    typer.echo(f"Depth: {depth}")
    typer.echo(f"Instances: {len(result.instances)}")
    for inst in result.instances:
        depth_mark = "  " * (inst.depth - 1) + "└─"
        typer.echo(f"  {depth_mark} {inst.name}  (def={inst.def_name}, depth={inst.depth})")

    if output_json:
        import json
        from dataclasses import asdict
        out = {
            "module": result.top_module,
            "view": "module",
            "level": 1,
            "depth": depth,
            "nodes": [
                {
                    "id": inst.id,
                    "name": inst.name,
                    "kind": "module",
                    "def_name": inst.def_name,
                    "module_path": inst.id,  # alias for golden compat
                    "cluster": "default",  # L1 不分 cluster, 给个默认值
                    "depth": inst.depth,
                    "array_name": inst.array_name,
                    "array_index": inst.array_index,
                }
                for inst in result.instances
            ],
            "edges": [],  # L1 不画内部边
        }
        with open(output_json, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        typer.echo(f"\n✓ Wrote JSON: {output_json}")

    if dot_output:
        _write_module_dot(result, dot_output)
        typer.echo(f"✓ Wrote DOT: {dot_output}")


def _write_module_dot(result, path: str) -> None:
    """[PR1] 写 module-level DOT 图. 1 box = 1 instance."""
    lines = ["digraph module {"]
    lines.append('  rankdir=TB;')
    lines.append('  splines=polyline;')
    lines.append('  nodesep=0.4;')
    lines.append('  ranksep=0.6;')
    lines.append('')

    # Group by depth
    from collections import defaultdict
    by_depth = defaultdict(list)
    for inst in result.instances:
        by_depth[inst.depth].append(inst)

    for depth in sorted(by_depth.keys()):
        lines.append(f'  // Depth {depth}')
        for inst in by_depth[depth]:
            label = f"{inst.name}\\n({inst.def_name})"
            color = "#4488cc" if depth == 1 else "#88bbdd"
            lines.append(
                f'  "{inst.id}" [label="{label}" shape=box '
                f'style="rounded,filled" fillcolor="{color}" fontcolor="white" penwidth=1.5];'
            )
        lines.append('')

    # Add invisible edges for same-depth ordering
    for depth in sorted(by_depth.keys()):
        items = by_depth[depth]
        for i in range(len(items) - 1):
            lines.append(f'  "{items[i].id}" -> "{items[i+1].id}" [style=invis];')

    lines.append('}')
    with open(path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    typer.run(vis_app)
