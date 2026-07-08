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


# ==============================================================================
# [Plan B+ 2026-07-08] visualize chain — 从 input 到 output 画 data path,
#                                            强制方形 layout (neato + LR).
# ==============================================================================
@vis_app.command(name="chain")
def chain(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    target: str = typer.Option(None, "--target", "-t", help="Target module (focus scope)"),
    from_signals: list[str] = typer.Option([], "--from", help="Source signal(s) (e.g. dot11_tx.phy_tx_start). Can pass multiple."),
    to_signals: list[str] = typer.Option([], "--to", help="Target signal(s) (e.g. dot11_tx.result_i). Can pass multiple."),
    auto: bool = typer.Option(False, "--auto", help="Auto-detect all input ports → output ports paths in --target module"),
    max_edges: int = typer.Option(30, "--max-edges", help="Max edges to render (default 30, prevents huge graphs)"),
    layout: str = typer.Option("LR", "--layout", "-l", help="Layout: LR (left-right, default) or TB (top-bottom)"),
    layout_engine: str = typer.Option("neato", "--layout-engine", help="Layout engine: neato (square, default) / dot / fdp"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),
    png_output: str = typer.Option(None, "--png", help="Output PNG file (auto-call <engine> -Tpng)"),
    svg_output: str = typer.Option(None, "--svg", help="Output SVG file (auto-call <engine> -Tsvg)"),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default: --no-strict)"),
) -> None:
    """[Plan B+ 2026-07-08] 从 input 到 output 画 data path, 方形 layout.

    Use case: 方豆反馈 "深入到具体 module, 完整 input → output 图, 尽可能方形".

    例子:
      # 手动指定 from/to
      sv_query visualize chain -f dot11_tx.v --no-strict \\
        --from dot11_tx.phy_tx_start --to dot11_tx.result_i \\
        --layout LR --layout-engine neato --png /tmp/chain.png

      # Auto mode: 自动从 target module 的所有 input ports 找 path 到所有 output ports
      sv_query visualize chain -f dot11_tx.v --no-strict \\
        --target dot11_tx --auto --max-edges 20 \\
        --layout LR --layout-engine neato --png /tmp/chain.png
    """
    from trace.core.compiler import CompilationError
    from cli._common import _build_tracer, handle_compilation_error

    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    if not auto and (not from_signals or not to_signals):
        typer.echo("Error: need --from and --to, OR --auto with --target", err=True)
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

    # 决定 from/to signals
    if auto:
        if not target:
            typer.echo("Error: --auto requires --target <module>", err=True)
            raise typer.Exit(code=1)
        from_sigs, to_sigs = _auto_detect_io_ports(graph, target)
        if not from_sigs or not to_sigs:
            typer.echo(
                f"Error: --auto could not find input/output ports for target={target}",
                err=True,
            )
            typer.echo(f"  found {len(from_sigs)} input ports, {len(to_sigs)} output ports", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"  --auto detected {len(from_sigs)} input ports and {len(to_sigs)} output ports", err=True)
    else:
        from_sigs = from_signals
        to_sigs = to_signals

    # 对每对 (from, to) 找 shortest path
    all_paths = []
    for src in from_sigs:
        for dst in to_sigs:
            if src == dst:
                continue
            path = graph.find_path(src, dst)
            if path and len(path) > 1:
                all_paths.append(path)

    typer.echo(f"  Found {len(all_paths)} data paths from inputs to outputs", err=True)

    # 合并所有 paths 形成 set of edges + nodes
    chain_edges = set()
    chain_nodes = set()
    for path in all_paths:
        for node in path:
            chain_nodes.add(node)
        for i in range(len(path) - 1):
            edge = (path[i], path[i + 1])
            chain_edges.add(edge)

    if not chain_nodes:
        typer.echo("  Warning: no chain nodes found, output empty DOT", err=True)
        if dot_output:
            Path(dot_output).write_text(
                f'digraph chain {{ label="No data paths from {",".join(from_sigs)} to {",".join(to_sigs)}"; }}'
            )
        return

    # 如果 edges 太多, 截断 (--max-edges)
    if len(chain_edges) > max_edges:
        typer.echo(
            f"  Truncating {len(chain_edges)} edges to {max_edges} (use --max-edges to change)",
            err=True,
        )
        chain_edges = set(list(chain_edges)[:max_edges])
        chain_nodes = set()
        for s, d in chain_edges:
            chain_nodes.add(s)
            chain_nodes.add(d)

    # 生成 DOT
    dot = _generate_chain_dot(
        chain_nodes, chain_edges, from_sigs, to_sigs,
        target or (Path(file).stem if file else "chain"),
        layout=layout, layout_engine=layout_engine,
    )

    # 输出
    if dot_output:
        Path(dot_output).write_text(dot)
        typer.echo(f"✓ DOT: {dot_output}", err=True)

    if png_output:
        _render_with_engine(dot, png_output, layout_engine, fmt="png")
        typer.echo(f"✓ PNG: {png_output}", err=True)

    if svg_output:
        _render_with_engine(dot, svg_output, layout_engine, fmt="svg")
        typer.echo(f"✓ SVG: {svg_output}", err=True)

    if not dot_output and not png_output and not svg_output:
        typer.echo(dot)


def _auto_detect_io_ports(graph, target: str) -> tuple[list[str], list[str]]:
    """[铁律1] 用 semantic AST (semantic_adapter.get_port_declarations) 拿 target module 的 input/output ports.

    Returns (input_signal_ids, output_signal_ids) — signal IDs 形如 "{target}.{port_name}".
    """
    from trace.core.semantic_adapter import SemanticAdapter

    # 找 compilation 入口
    # tracer is in graph._tracer or similar; 用 graph._tracer 拿
    tracer = getattr(graph, "_tracer", None)
    if tracer is None:
        # 退而求其次: scan all nodes for {target}.<name> pattern
        # 假设 signals with depth=0 (top module) 是 ports
        from_sigs = []
        to_sigs = []
        for node_id in graph.nodes():
            if node_id.startswith(f"{target}."):
                # heuristic: 如果 node 既被驱动又被引用, 可能是 wire (跳过)
                # 如果只被驱动 (=port_in) 或只被引用 (=port_out)
                in_deg = graph.in_degree(node_id)
                out_deg = graph.out_degree(node_id)
                if in_deg == 0 and out_deg > 0:
                    from_sigs.append(node_id)
                elif out_deg == 0 and in_deg > 0:
                    to_sigs.append(node_id)
        return from_sigs, to_sigs

    # [铁律1] 用 semantic API
    compiler = tracer._get_compiler() if hasattr(tracer, "_get_compiler") else None
    if compiler is None:
        return [], []
    adapter = SemanticAdapter(compiler.get_root())

    target_module = None
    for mod in adapter.get_modules():
        if adapter.get_module_name(mod) == target:
            target_module = mod
            break

    if target_module is None:
        return [], []

    from_sigs = []
    to_sigs = []
    for port_decl in adapter.get_port_declarations(target_module):
        name, direction = adapter.get_port_name_and_direction(port_decl)
        if not name or name == "unknown":
            continue
        signal_id = f"{target}.{name}"
        if direction == "input":
            from_sigs.append(signal_id)
        elif direction == "output":
            to_sigs.append(signal_id)
    return from_sigs, to_sigs


def _generate_chain_dot(
    nodes: set, edges: set, from_sigs: list, to_sigs: list,
    title: str, layout: str = "LR", layout_engine: str = "neato",
) -> str:
    """生成 chain 专用的 DOT 图, 强制方形 layout (neato + LR)."""
    lines = ["digraph chain {"]
    lines.append(f'  label="Data Chain: {title}\\n({len(edges)} edges, {len(nodes)} nodes)";')
    lines.append("  labelloc=t;")
    lines.append("  fontsize=14;")
    lines.append(f"  rankdir={layout};")
    if layout_engine in ("neato", "fdp"):
        lines.append("  ratio=1.0;")  # 强制 1:1 (方形)
        lines.append("  overlap=false;")
    else:
        lines.append("  ratio=auto;")
    lines.append("  splines=true;")
    lines.append("  bgcolor=white;")
    lines.append("")

    # 节点定义
    from_set = set(from_sigs)
    to_set = set(to_sigs)
    for node in sorted(nodes):
        safe_id = _sanitize_dot_id_chain(node)
        if node in from_set:
            color = "#22aa55"  # green for inputs
            shape = "invhouse"
        elif node in to_set:
            color = "#aa5522"  # red for outputs
            shape = "invhouse"
        else:
            color = "#5599cc"  # blue for intermediate
            shape = "box"
        label = node
        if len(label) > 30:
            label = "..." + label[-27:]
        lines.append(
            f'  "{safe_id}" [label="{label}" shape={shape} style="filled,rounded" '
            f'fillcolor="{color}" fontcolor="white" fontsize=10];'
        )
    lines.append("")

    for src, dst in sorted(edges):
        src_safe = _sanitize_dot_id_chain(src)
        dst_safe = _sanitize_dot_id_chain(dst)
        lines.append(f'  "{src_safe}" -> "{dst_safe}" [color="#666666" penwidth=1.0 arrowhead=normal];')

    lines.append("}")
    return "\n".join(lines)


def _sanitize_dot_id_chain(s: str) -> str:
    """Sanitize signal ID for DOT (chain version)."""
    return s.replace(".", "_").replace("[", "_").replace("]", "_").replace(" ", "_")


def _render_with_engine(dot_text: str, output_path: str, engine: str, fmt: str = "png") -> int:
    """调用 graphviz engine 渲染 DOT → PNG/SVG."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".dot", mode="w", delete=False) as f:
        f.write(dot_text)
        tmp_dot = f.name

    try:
        cmd = [engine, f"-T{fmt}", tmp_dot, "-o", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode
    finally:
        Path(tmp_dot).unlink(missing_ok=True)


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
    use_mig: bool = typer.Option(
        True, "--mig/--no-mig",
        help="[PR4] Use ModuleInstanceGraph for cross-instance port edges (default ON). "
             "Disable for PR1 L1-only behavior.",
    ),
    show_edges: bool = typer.Option(
        True, "--edges/--no-edges",
        help="[PR4] Show instance-to-instance port connections (default ON)",
    ),
    max_edges: int = typer.Option(
        500, "--max-edges",
        help="[PR4] Maximum cross-instance edges to show",
    ),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default non-strict)"),
) -> None:
    """[PR1+PR4 2026-06-15] L1 module-level + L2 cross-instance port visualization.

    1 box = 1 sub-module instance. PR4 加 instance-to-instance port 边 (MIG).
    用于项目架构 review.
    """
    from trace.core.module_extractor import (
        extract_module_from_graph,
        extract_module_edges_from_mig,
    )

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
        # [FIX 2026-06-26] safe print: e may contain binary garbage from pyslang
        try:
            msg = f"Error building tracer: {e}"
        except (UnicodeDecodeError, TypeError):
            msg = "Error building tracer: <message contains binary garbage>"
        typer.echo(msg, err=True)
        raise typer.Exit(1)

    graph = tracer.build_graph()
    result = extract_module_from_graph(
        graph, target_module=target, max_depth=depth,
    )

    # [PR1 2026-06-14] AST 优先: AST 路径比 graph 更准确 (直接走 pyslang
    # Semantic AST, 不经过 graph builder 的中间层).
    ast_result = None
    try:
        from trace.core.module_extractor import extract_module
        from trace.core.semantic_adapter import SemanticAdapter
        semantic_adapter = SemanticAdapter(tracer._get_compiler().get_root())
        ast_result = extract_module(semantic_adapter, target, max_depth=depth)
    except Exception:
        pass

    # 如果 AST 有结果, 优先用 AST. 否则用 graph.
    if ast_result and len(ast_result.instances) > 0:
        result = ast_result

    # [PR4 2026-06-15] L2 边: 从 MIG 抽 instance-to-instance port 连接.
    # 0 改动 graph_builder, 复用 PR3 已用 MIG fallback 的架构.
    edges: list[dict] = []
    if show_edges and use_mig:
        mig = getattr(tracer, "_module_graph", None)
        if mig is not None:
            edges = extract_module_edges_from_mig(
                mig, result.instances, max_edges=max_edges,
            )

    typer.echo(f"Target: {result.top_module}")
    typer.echo(f"Depth: {depth}")
    typer.echo(f"Instances: {len(result.instances)}")
    typer.echo(f"Edges: {len(edges)}")
    for inst in result.instances:
        depth_mark = "  " * (inst.depth - 1) + "└─"
        typer.echo(f"  {depth_mark} {inst.name}  (def={inst.def_name}, depth={inst.depth})")

    if output_json:
        import json
        out = {
            "module": result.top_module,
            "view": "module",
            "level": 2 if edges else 1,  # [PR4] L2 if has edges
            "depth": depth,
            "nodes": [
                {
                    "id": inst.id,
                    "name": inst.name,
                    "kind": "module",
                    "def_name": inst.def_name,
                    "module_path": inst.id,  # alias for golden compat
                    "cluster": _module_def_cluster(inst.id, result.top_module),  # [PR4] cluster by module_type
                    "depth": inst.depth,
                    "array_name": inst.array_name,
                    "array_index": inst.array_index,
                }
                for inst in result.instances
            ],
            # [PR4] L2 edges: instance-to-instance port connections
            "edges": [
                {
                    "src": e["src"],
                    "dst": e["dst"],
                    "internal": e["internal"],
                    "port_src": e["port_src"],
                    "port_dst": e["port_dst"],
                    "width": e["width"],
                }
                for e in edges
            ],
        }
        with open(output_json, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        typer.echo(f"\n✓ Wrote JSON: {output_json}")

    if dot_output:
        _write_module_dot(result, edges, dot_output)
        typer.echo(f"✓ Wrote DOT: {dot_output}")


def _module_def_cluster(instance_id: str, top_module: str) -> str:
    """[PR4] 按 instance 所在模块类型划分 cluster.

    例子:
      'axi_xbar_dp_ram.i_xbar_intf' → 'axi_xbar_intf'
      'axi_xbar_dp_ram.i_xbar_intf.i_xbar' → 'axi_xbar'
    """
    parts = instance_id.split(".")
    # 去掉 top_module 部分 (cluster 跟它平级)
    if parts[0] == top_module and len(parts) >= 2:
        # 顶级 wrapper: cluster 是第二部分 (i_xbar_intf 等)
        # 子 instance: cluster 是对应 def_name (这里用 path 第二段近似)
        return parts[1] if len(parts) >= 2 else "default"
    return parts[0] if parts else "default"


def _write_module_dot(result, edges: list[dict], path: str) -> None:
    """[PR1+PR4] 写 module-level DOT 图. 1 box = 1 instance, cluster 按 instance path 分组, 边走 MIG.

    [PR4] 加 L2 边: instance-to-instance port connection (边标 port 名).
    """
    lines = ["digraph module {"]
    lines.append('  rankdir=TB;')
    lines.append('  splines=polyline;')
    lines.append('  nodesep=0.4;')
    lines.append('  ranksep=0.6;')
    lines.append('  compound=true;  // [PR4] 允许 cluster 之间的边')
    lines.append('')

    # Group by depth
    from collections import defaultdict
    by_depth = defaultdict(list)
    for inst in result.instances:
        by_depth[inst.depth].append(inst)

    # [PR4] 按 instance 所在 wrapper 划分 cluster.
    # 例: 'axi_xbar_dp_ram.i_xbar_intf' 和 'axi_xbar_dp_ram.i_xbar_intf.i_xbar'
    #     都在 'i_xbar_intf' 这个 cluster 里.
    def _cluster_of(inst_id: str) -> str:
        parts = inst_id.split(".")
        if len(parts) >= 3:
            return parts[1]  # wrapper 下的子 instance: 顶级 wrapper 名字
        return parts[1] if len(parts) >= 2 else "top"

    inst_ids = {inst.id for inst in result.instances}

    # 渲染 nodes (按 cluster 分组)
    clusters_used = set()
    for depth in sorted(by_depth.keys()):
        lines.append(f'  // Depth {depth}')
        for inst in by_depth[depth]:
            cluster = _cluster_of(inst.id)
            clusters_used.add(cluster)
            label = f"{inst.name}\\n({inst.def_name})"
            color = "#4488cc" if depth == 1 else "#88bbdd"
            lines.append(
                f'  "{inst.id}" [label="{label}" shape=box '
                f'style="rounded,filled" fillcolor="{color}" fontcolor="white" penwidth=1.5];'
            )
        lines.append('')

    # [PR4] 渲染 cluster 块 (DOT subgraph cluster_X 语法)
    if clusters_used:
        for cluster in sorted(clusters_used):
            lines.append(f'  subgraph "cluster_{cluster}" {{')
            lines.append(f'    label="{cluster}";')
            lines.append('    style="dashed,rounded";')
            lines.append('    color="#999999";')
            lines.append('    fontcolor="#666666";')
            lines.append('    fontsize=10;')
            # 加上该 cluster 里的所有 instances
            cluster_insts = [iid for iid in inst_ids if _cluster_of(iid) == cluster]
            for iid in cluster_insts:
                lines.append(f'    "{iid}";')
            lines.append('  }')
            lines.append('')

    # 边
    if edges:
        lines.append('  // [PR4] L2 instance-to-instance port connections')
        for e in edges:
            src, dst = e["src"], e["dst"]
            if src not in inst_ids or dst not in inst_ids:
                continue
            label = e.get("port_src", "") or ""
            if e.get("port_src") and e.get("port_src") != e.get("port_dst"):
                label = f"{e['port_src']}~{e['port_dst']}"
            width = e.get("width")
            if width and width > 1:
                label = f"{label}\\n[{width}b]"
            lines.append(
                f'  "{src}" -> "{dst}" [label="{label}" fontsize=8 color="#888888" '
                f'arrowhead=none penwidth=0.7];'
            )
        lines.append('')

    lines.append('}')
    with open(path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    typer.run(vis_app)
