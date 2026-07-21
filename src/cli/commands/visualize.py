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
from collections import defaultdict
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

# [Phase B 2026-07-17] 共享 viz 子命令的 typer options + build_viz_tracer helper
from cli._viz_common import (
    FILE_OPTION, FILELIST_OPTION, INCLUDE_OPTION, STRICT_OPTION, SHOW_SOURCE_OPTION,
    build_viz_tracer, get_viz_sources,
)

# [Phase B 2026-07-17] 共享 DOT helpers (从 _dot_common 移过来)
from trace.core.graph.analyzer._dot_common import (
    escape_dot_label,
    format_node_label_chain,
    sanitize_dot_id,
    sanitize_dot_id_inner,
    render_with_engine,
)

vis_app = typer.Typer(help="Signal graph visualization: DOT, Mermaid, HTML with data flow edges")


def _emit_split_by_module(graph, classification, module_name, dot_output, include_clk_rst, Path):
    """[Phase 6.1 2026-07-12] Generate per-instance DOT files.

    Groups nodes by their top-level instance path (e.g. 'darksocv.bridge0.core0')
    and emits one DOT per group, plus a master overview.

    Output naming:
      <prefix>_overview.dot           - lists all sub-modules + node counts
      <prefix>_<sub_module>.dot       - one DOT per sub-module
    """
    from collections import defaultdict
    from trace.core.graph.analyzer.dataflow_viz import generate_dataflow_dot

    # Group nodes by instance path.
    # [Phase 6.1 2026-07-12] Strategy (FINAL):
    # - 1-segment paths (e.g. 'XRES')           → group 'XRES' (lone module)
    # - 2-segment paths (e.g. 'darksocv.XRES') → group 'darksocv' (top-level signal)
    # - 3+ segment paths                       → group by first 2 segments
    #                                            (e.g. 'darksocv.bridge0.XRES' → 'darksocv.bridge0')
    # This way 'darksocv.XRES' and 'darksocv.bridge0.XRES' go to DIFFERENT groups.
    from collections import defaultdict
    groups = defaultdict(set)
    for nid in graph.nodes():
        if not isinstance(nid, str) or not nid or nid[0].isdigit() or nid.startswith("__"):
            continue
        parts = nid.split('.')
        # 2-segment node → group by first 1 part (top-level module)
        # 3+ segment node → group by first 2 parts (sub-instance)
        if len(parts) >= 3:
            key = f"{parts[0]}.{parts[1]}"
        else:
            key = parts[0]
        groups[key].add(nid)

    # [Phase 6.1] Warn if any group is too big, recommend --module
    MAX_RECOMMENDED = 100
    for key, nodes in sorted(groups.items()):
        if len(nodes) > MAX_RECOMMENDED:
            typer.echo(
                f"  ⚠️  {key} has {len(nodes)} nodes (>{MAX_RECOMMENDED}). "
                f"Consider: --module={key}",
                err=True,
            )

    if not groups:
        typer.echo("Error: --split-by-module requires target_module with instances", err=True)
        return

    base = Path(dot_output)
    # Use a directory or strip .dot suffix to create prefix
    if str(base).endswith(".dot"):
        prefix = str(base)[:-4]
    else:
        prefix = str(base)
    base_dir = Path(prefix)
    base_dir.mkdir(parents=True, exist_ok=True)

    # Master overview DOT (lists sub-modules, node counts)
    overview = ['digraph dataflow_overview {']
    overview.append('  rankdir=TB;')
    overview.append(f'  label="Data Flow Overview: {module_name}\\n({len(groups)} sub-modules, {sum(len(s) for s in groups.values())} nodes)";')
    overview.append('  labelloc=t;')
    overview.append('  fontsize=14;')
    overview.append('')
    # TL;DR
    overview.append(f'  // TL;DR: {len(groups)} sub-modules · {sum(len(s) for s in groups.values())} nodes')
    overview.append('')
    overview.append('  // === Sub-module summary ===')
    for sub in sorted(groups.keys()):
        n = len(groups[sub])
        safe = sub.replace('.', '_')
        overview.append(
            f'  "{safe}_anchor" [label="{sub}\\n({n} nodes)" shape=box '
            f'style="rounded,filled" fillcolor="#88bbdd" fontcolor="white" fontsize=11];'
        )
        overview.append(f'  "{safe}_anchor" -> "{sub.replace(".", "_")}.dot" [style=invis];')
    overview.append('}')
    (Path(f"{prefix}_overview.dot")).write_text("\n".join(overview))
    typer.echo(f"✓ Overview: {prefix}_overview.dot ({len(groups)} sub-modules)", err=True)

    # Per-sub-module DOT
    for sub in sorted(groups.keys()):
        sub_nodes = groups[sub]
        # Build sub-classification: only edges where BOTH src/dst are in sub_nodes
        from trace.core.graph.analyzer.signal_classifier import SignalClassification, SignalClass
        from trace.core.graph.models import EdgeKind
        sub_class = SignalClassification()
        for nid in sub_nodes:
            cn = classification.nodes.get(nid)
            if cn is not None:
                sub_class.nodes[nid] = cn
        # Classify into buckets
        for nid, cn in sub_class.nodes.items():
            if cn.signal_class == SignalClass.DATA:
                sub_class.data_nodes.append(nid)
            elif cn.signal_class == SignalClass.CONTROL:
                sub_class.control_nodes.append(nid)
            elif cn.signal_class == SignalClass.CLOCK:
                sub_class.clock_nodes.append(nid)
            elif cn.signal_class == SignalClass.RESET:
                sub_class.reset_nodes.append(nid)
        # Re-classify edges (only those where both src/dst are in sub_nodes)
        for key, ce in classification.edges.items():
            src, dst, kind_str = key
            if src in sub_nodes and dst in sub_nodes:
                sub_class.edges[key] = ce

        # Build a small SignalGraph view (sub nodes only + edges within sub)
        # Note: SignalGraph extends DiGraph, so we can use a fresh subgraph
        sub_graph = graph.__class__()
        for nid in sub_nodes:
            n = graph.get_node(nid)
            if n is not None:
                sub_graph.add_trace_node(n)
        for u, v in graph.edges():
            if u in sub_nodes and v in sub_nodes:
                e = graph.get_edge(u, v)
                if e is not None:
                    sub_graph.add_trace_edge(e)

        # Generate DOT
        dot = generate_dataflow_dot(
            sub_graph,
            sub,
            classification=sub_class,
            include_clk_rst=include_clk_rst,
        )
        safe = sub.replace('.', '_')
        out_path = Path(f"{prefix}_{safe}.dot")
        out_path.write_text(dot)
        typer.echo(f"✓ {sub}: {out_path} ({len(sub_nodes)} nodes)", err=True)
@vis_app.command(name="graph")
def graph(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    strict: bool = STRICT_OPTION,
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
    module_only: bool = typer.Option(False, "--module-only", help="Show only top-module signals (skip sub-module internals, show only port/instantiation level)"),
    show_source: bool = SHOW_SOURCE_OPTION,
) -> None:
    """可视化信号图（包含数据流关系）

    [ADD 2026-06-11 Req-9] --file 或 --filelist 二选一, 走 _build_tracer 统一 helper.

    [Phase B 2026-07-17] --file/--filelist/--include/--strict via shared FILE_OPTION etc.
    """
    from trace.core.compiler import CompilationError
    from cli._common import handle_compilation_error
    from cli._viz_common import build_viz_tracer, get_viz_sources

    try:
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            strict=strict, use_cache=cache,
        )
        sources_for_extractors = get_viz_sources(tracer, file, filelist)
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
        node_style={"risk_color": True, "cover_marker": True, "show_fan": True, "show_type": True, "show_source": show_source},
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
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    module: str = typer.Option(None, "--module", "-m", help="Focus on specific module (filter edges to this module's signals)"),
    strict: bool = STRICT_OPTION,
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file (or prefix when --split-by-module)"),
    include_clk_rst: bool = typer.Option(False, "--with-clk-rst", help="Include clock/reset nodes"),
    split_by_module: bool = typer.Option(False, "--split-by-module", help="[Phase 6.1 2026-07-12] Generate one DOT per sub-instance (e.g. darksocv.bridge0). Output: <prefix>_<sub>.dot"),
    show_source: bool = SHOW_SOURCE_OPTION,
) -> None:
    """数据流图: 显示 data path (运算表达式) + 关键 control 边 (enable/valid/mux sel)

    基于 SignalGraph 自动分类 clock/reset/control/data, 生成 DOT 图:
    - 数据边: 蓝色实线,标注运算表达式 (a+b, {rx, sreg[10:1]})
    - 控制边: 橙色虚线 (valid/ready/enable → 数据目标)
    - MUX 目标: 加粗边 (多源数据汇聚)
    - 寄存器: 粗边框

    [Phase 6.1] Use --split-by-module to split into per-instance DOTs when graph is large.

    [Phase B 2026-07-17] --file/--filelist/--include/--strict via shared options.
    """
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    from trace.core.graph.analyzer.dataflow_viz import generate_dataflow_dot
    from trace.core.compiler import CompilationError
    from cli._common import handle_compilation_error
    from cli._viz_common import build_viz_tracer

    try:
        # [Phase 3 2026-07-11] Pass --module as target_module so SignalGraph uses user namespace
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            strict=strict, target_module=module,
        )
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    classification = classify_graph(graph)
    typer.echo(f"  Data nodes: {len(classification.data_nodes)}", err=True)
    typer.echo(f"  Control nodes: {len(classification.control_nodes)}", err=True)
    typer.echo(f"  Clock nodes: {len(classification.clock_nodes)}", err=True)

    dot = generate_dataflow_dot(graph, module or file or filelist or "", classification, include_clk_rst=include_clk_rst, show_source=show_source)

    if dot_output:
        Path(dot_output).write_text(dot)

    # [Phase 6.1 2026-07-12] Split by module: generate per-instance DOTs
    if split_by_module:
        from collections import defaultdict
        _emit_split_by_module(graph, classification, module or file or filelist or "", dot_output, include_clk_rst, Path)
        typer.echo(f"✓ DOT: {dot_output}")
    else:
        typer.echo(dot)


@vis_app.command(name="pipeline")
def pipeline(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    module: str = typer.Option(None, "--module", "-m", help="Focus on specific module"),
    strict: bool = STRICT_OPTION,
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),
    max_comb_per_stage: int = typer.Option(8, "--max-comb-per-stage", help="[P0 fix 2026-07-10] Max combinational nodes per stage (default 8)"),
    max_control_nodes: int = typer.Option(12, "--max-control-nodes", help="[P0 fix 2026-07-17] Max control signals in header row (default 12, was 8). 0 = hide all."),
    unfold: bool = typer.Option(False, "--unfold", help="[Phase 6.2 2026-07-12] Disable stage folding, show all stages individually"),
    fold_every: int = typer.Option(5, "--fold-every", help="[Phase 6.2] Number of stages per fold group when total > 30 (default 5)"),
    timing: bool = typer.Option(False, "--timing", help="[Phase 7 2026-07-13] Render as parallel pipeline timing diagram (lanes × cycles) instead of folded/unfolded stage flow"),
    load_path: bool = typer.Option(False, "--load-path", help="[Phase 7.2 2026-07-13] Render segments grouped by load path (input port) instead of control signal target"),
) -> None:
    """Pipeline 流图: 检测 register chain → 划分 time cycle/stage

    从 SignalGraph 自动检测 pipeline 结构:
    - 识别 pipeline registers (排除 clock/reset/state-machine regs)
    - 每个 stage 一个 subgraph: 含 registers + 组合逻辑
    - 控制信号 (valid/stall) 标记为跨 stage 虚线
    - 左→右布局 = 时间流方向

    [P0 fix 2026-07-10] 控制节点不再堆成 31k PNG, 默认限制每 stage 8 个组合节点 +
    控制信号区最多 30 个节点。用 --max-control-nodes 0 隐藏控制信号区。

    [Phase B 2026-07-17] --file/--filelist/--include/--strict via shared options.
    """
    from trace.core.graph.analyzer.signal_classifier import classify_graph
    from trace.core.graph.analyzer.pipeline_viz import detect_pipeline, generate_pipeline_dot, generate_pipeline_timing_dot, generate_pipeline_load_dot
    from trace.core.compiler import CompilationError
    from cli._common import handle_compilation_error
    from cli._viz_common import build_viz_tracer

    try:
        # [Phase 3 2026-07-11] Pass --module as target_module for correct namespace
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            strict=strict, target_module=module,
        )
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

    dot = generate_pipeline_dot(
        graph, info, classification,
        max_comb_per_stage=max_comb_per_stage,
        max_control_nodes=max_control_nodes,
        fold_threshold=999 if unfold else 30,  # unfold = disable folding
        fold_every=fold_every,
    ) if not (timing or load_path) else (
        generate_pipeline_load_dot(graph, info, classification) if load_path
        else generate_pipeline_timing_dot(graph, info, classification, max_segments=8, max_stages_per_segment=15)
    )

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
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    target: str = typer.Option(None, "--target", "-t", help="Target module (focus scope)"),
    strict: bool = STRICT_OPTION,
    from_signals: list[str] = typer.Option([], "--from", help="Source signal(s) (e.g. dot11_tx.phy_tx_start). Can pass multiple."),
    to_signals: list[str] = typer.Option([], "--to", help="Target signal(s) (e.g. dot11_tx.result_i). Can pass multiple."),
    auto: bool = typer.Option(False, "--auto", help="Auto-detect all input ports → output ports paths in --target module"),
    max_edges: int = typer.Option(30, "--max-edges", help="Max edges to render (default 30, prevents huge graphs)"),
    max_depth: int = typer.Option(0, "--max-depth", help="[ADD 2026-07-10] Max path depth (default 0=unlimited, 方豆 feedback '不限制depth')"),
    layout: str = typer.Option("LR", "--layout", "-l", help="Layout: LR (left-right, default) or TB (top-bottom)"),
    layout_engine: str = typer.Option("neato", "--layout-engine", help="Layout engine: neato (square, default) / dot / fdp"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file"),
    png_output: str = typer.Option(None, "--png", help="Output PNG file (auto-call <engine> -Tpng)"),
    svg_output: str = typer.Option(None, "--svg", help="Output SVG file (auto-call <engine> -Tsvg)"),
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

    [Phase B 2026-07-17] --file/--filelist/--include/--strict via shared options.
    """
    from trace.core.compiler import CompilationError
    from cli._common import handle_compilation_error
    from cli._viz_common import build_viz_tracer

    if not auto and (not from_signals or not to_signals):
        typer.echo("Error: need --from and --to, OR --auto with --target", err=True)
        raise typer.Exit(code=1)

    try:
        # [FIX 2026-07-17] Pass target_module to build_graph if provided.
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            strict=strict, target_module=target if target else None,
        )
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    # 决定 from/to signals
    if auto:
        if not target:
            typer.echo("Error: --auto requires --target <module>", err=True)
            raise typer.Exit(code=1)
        from_sigs, to_sigs = _auto_detect_io_ports(graph, target, tracer=tracer)
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

    # [FIX 2026-07-08] 用 MIG (module_instance_graph) 重写 flat signal ID
    # 到完整 hierarchy path. e.g. "bitreverse.i_clk" → "openofdm_tx.dot11_tx.ifft64.revstage.i_clk"
    # 这样 chain 图能正确显示 sub-module 边界.
    mig = getattr(tracer, "_module_graph", None)
    hierarchy_map: dict[str, str] = {}  # flat_id → full_hierarchy_id
    if mig is not None:
        # [FIX 2026-07-08] 2-level remap:
        # Level 1: port signals (inst_type.port_name) → inst_path.port_name
        # Level 2: internal signals (inst_type.signal_name) → inst_path.signal_name
        #   (e.g. "bitreverse.brmem" 是 bitreverse module 内部 wire, 不是 port)
        #   我们用 inst_type 模糊匹配: 任何 "<inst_type>.<signal_name>"
        #   重写到 "<inst_path>.<signal_name>"

        # Collect (module_type) → [instance_id] for module-type → instance mapping
        module_type_to_instances: dict[str, list[str]] = {}
        for inst_id, inst in mig.instances.items():
            module_type_to_instances.setdefault(inst.module_type, []).append(inst_id)

        # Walk all graph nodes to find flat signals
        for node_id in list(graph.nodes()):
            # node_id 形如 "bitreverse.brmem" (flat, 2+ parts, 第一段是 module type)
            if node_id in hierarchy_map:
                continue  # already mapped
            parts = node_id.split(".")
            if len(parts) < 2:
                continue
            first_seg = parts[0]
            if first_seg not in module_type_to_instances:
                continue
            # 找到 instance list — 选第一个 (TODO: 智能选)
            inst_path = module_type_to_instances[first_seg][0]
            # 重写 node_id: 把第一段 (module type) 替换成 inst_path
            full_id = f"{inst_path}." + ".".join(parts[1:])
            hierarchy_map[node_id] = full_id

    def _remap_to_hierarchy(node_id: str) -> str:
        """如果 node_id 是 flat signal, 重写到完整 hierarchy path."""
        if node_id in hierarchy_map:
            return hierarchy_map[node_id]
        return node_id

    # 对每对 (from, to) 找 shortest path
    all_paths = []
    for src in from_sigs:
        for dst in to_sigs:
            if src == dst:
                continue
            # Remap flat signal IDs to hierarchy
            src_h = _remap_to_hierarchy(src)
            dst_h = _remap_to_hierarchy(dst)
            path = graph.find_path(src_h, dst_h)
            if not path:
                # Fall back to original (in case remap failed)
                path = graph.find_path(src, dst)
            if path and len(path) > 1:
                # Remap path nodes too
                path = [_remap_to_hierarchy(n) for n in path]
                # Dedup consecutive (in case remap creates cycles)
                deduped = [path[0]]
                for n in path[1:]:
                    if n != deduped[-1]:
                        deduped.append(n)
                if len(deduped) > 1:
                    all_paths.append(deduped)

    typer.echo(f"  Found {len(all_paths)} data paths from inputs to outputs", err=True)
    if hierarchy_map:
        typer.echo(
            f"  Hierarchy remap: {len(hierarchy_map)} flat signals → full path "
            f"(e.g. bitreverse.i_clk → openofdm_tx.dot11_tx.ifft64.revstage.i_clk)",
            err=True,
        )

    # [FIX 2026-07-08] Path-aware truncation: 选择完整 paths (不是 random edges),
    # 避免 intermediate node 变孤儿 (无任何 edge 连接).
    # 策略: 按 path length 排序 (**LONGEST first** 优先选有 intermediate 的 path),
    # 贪婪选择, 直到 max_edges 达上限.
    # 这样保留的 node 都有 edge 相连, 而且能看到 deep data path.
    #
    # [FIX 2026-07-10] Post-process: 移除 orphan nodes
    # 方豆反馈 "为什么看到有的节点只进不出?"
    # 根因: greedy 截断路径后, 有些中间 node 丢失了 incoming 或 outgoing edge,
    #       看起来 “只进不出” 或 “只出不进”.
    # 修法: 在 dot 生成前, 删掉任何没有 incoming 或 outgoing edge 的 chain_node
    #       (IO 端口除外, INPUT 没 incoming 是正常的, OUTPUT 没 outgoing 是正常的).
    if not all_paths:
        chain_edges = set()
        chain_nodes = set()
    else:
        # [FIX 2026-07-08] Sort paths by length DESCENDING (LONGEST first)
        # 这样优先选 multi-hop paths (有 intermediate nodes),
        # 不是 1-edge paths (只 input → output, no intermediate).
        sorted_paths = sorted(all_paths, key=len, reverse=True)

        chain_edges: set = set()
        chain_nodes: set = set()

        # Greedy select: add path by path until max_edges reached
        for path in sorted_paths:
            # 计算这条 path 的 edges
            path_edges = set()
            for i in range(len(path) - 1):
                path_edges.add((path[i], path[i + 1]))

            # 如果加上这条 path 会超过 max_edges, 跳过 (除非还是空)
            if chain_edges and len(chain_edges) + len(path_edges) > max_edges:
                continue

            chain_edges |= path_edges
            chain_nodes |= set(path)

            # 如果已经达到 max_edges, 停止
            if len(chain_edges) >= max_edges:
                break

        # If still under max_edges, fill with shorter paths
        if len(chain_edges) < max_edges:
            for path in sorted_paths:
                path_edges = set()
                for i in range(len(path) - 1):
                    path_edges.add((path[i], path[i + 1]))
                new_edges = path_edges - chain_edges
                if not new_edges:
                    continue
                if len(chain_edges) + len(new_edges) > max_edges:
                    break
                chain_edges |= new_edges
                chain_nodes |= set(path)

        # [FIX 2026-07-10 方豆 feedback] 不再静默移除 orphan nodes, 改为检查 RTL 语义:
        # - PORT_IN (input): 应该只有 out (没被内部驱动, 来自外部)
        # - PORT_OUT (output): 应该只有 in (没内部 load, 去外部)
        # - REG/WIRE: 必须同时 in & out
        #   * in=0 out>0 = 悬空驱动 (X 值/未定值)
        #   * in>0 out=0 = 悬空负载 (未被使用/死代码)
        #   * in=0 out=0 = 真正孤儿 (两边都没接上)
        # 例外: SUB_INSTANCE 包装节点 (如 SourceA_dut) 可以 in>0 out=0 (路径终点)
        #      或 in=0 out>0 (路径起点)。
        # 报告 anomalies 但保留节点, 在 DOT 里用不同颜色标出。
        from_set = set(from_sigs)
        to_set = set(to_sigs)

        # Compute in/out degree for each chain node
        in_deg: dict[str, int] = defaultdict(int)
        out_deg: dict[str, int] = defaultdict(int)
        for src, dst in chain_edges:
            if src in chain_nodes and dst in chain_nodes:
                out_deg[src] += 1
                in_deg[dst] += 1

        anomalies_extra: dict[str, str] = {}  # for full-module scan (signals not in chain)
        anomalies: dict[str, str] = {}  # node_id -> anomaly type
        for n in chain_nodes:
            # Get node kind from graph (fallback to flat ID lookup if hierarchy remap)
            graph_node = graph.get_node(n)
            if graph_node is None:
                flat_id = n.split(".")[-1] if "." in n else n
                graph_node = graph.get_node(flat_id)
            kind = getattr(getattr(graph_node, "kind", None), "name", "UNKNOWN") if graph_node else "UNKNOWN"

            is_port_in = n in from_set
            is_port_out = n in to_set
            # [FIX 2026-07-10 方豆 feedback] OUTPUT 端口在 graph 里可能 kind=WIRE/REG/SIGNAL
            # (因为 semantic port list 权威但 graph node kind 可能不准)。
            # INPUT 端口 才需要检查 misclassification (内部 wire 可能被 heuristic 误判为 input)。
            is_misclassified = False
            if is_port_in and kind in ("WIRE", "REG", "SIGNAL"):
                is_misclassified = True
                is_port_in = False
                is_port_out = False
            # Sub-instance wrapper: e.g. "SourceA.sourceA_req_source_i" — contains a sub-module signal but
            # the node IS the sub-instance entry point. We treat it as a kind=PORT_IN/OUT inside the chain.

            if is_port_in:
                # INPUT 端口: 期望 out>0
                if in_deg[n] > 0 and out_deg[n] == 0:
                    # 路径跨模块边界: 这是子模块输入被某输出驱动, 正常
                    pass  # OK
                elif out_deg[n] == 0:
                    anomalies[n] = "DANGLING_INPUT"  # INPUT 端口在 chain 里完全没下游
            elif is_port_out:
                # OUTPUT 端口: 期望 in>0
                if out_deg[n] > 0 and in_deg[n] == 0:
                    pass  # 路径起点, OK
                elif in_deg[n] == 0:
                    anomalies[n] = "DANGLING_OUTPUT"
            else:
                # Intermediate node (REG/WIRE/SIGNAL/UNKNOWN) or misclassified-port:
                # 方豆 feedback: 寄存器只进不出 = 悬空, 只出不进 = X 驱动
                if is_misclassified:
                    anomalies[n] = "X_DRIVER"  # internal signal classified as port (X-driver pattern)
                elif in_deg[n] == 0 and out_deg[n] == 0:
                    anomalies[n] = "ORPHAN"  # 两边都没接上 (真实孤点)
                elif in_deg[n] == 0:
                    anomalies[n] = "X_DRIVER"  # 只出不进 = 寄存器没被写, 输出 X
                elif out_deg[n] == 0:
                    anomalies[n] = "DANGLING"  # 只进不出 = 寄存器写了未被读

        # [FIX 2026-07-10 方豆 feedback] Full-module anomaly scan.
        # 除了 chain 里的节点, 还需扫描整个 target module 的信号.
        # 原因: orphan_wire / isolated_wire 这种 RTL bug, 可能根本不在任何 data path 上
        #       (因为没 driver, 不能从 input 走到). 但它们仍是真实 RTL 问题.
        # 补上 full-graph anomaly scan.
        target_prefix = f"{target}."
        for node_id in graph.nodes():
            if not node_id.startswith(target_prefix):
                continue
            if node_id in anomalies:
                continue  # already in chain-based scan
            # Skip ports (they have a different rule)
            gn = graph.get_node(node_id)
            n_kind = str(getattr(getattr(gn, "kind", None), "name", "UNKNOWN")) if gn else "UNKNOWN"
            if n_kind in ("PORT_IN", "PORT_OUT"):
                continue
            if n_kind not in ("REG", "WIRE", "SIGNAL", "UNKNOWN"):
                continue
            n_in = graph.in_degree(node_id)
            n_out = graph.out_degree(node_id)
            if n_in == 0 and n_out == 0:
                anomalies[node_id] = "ORPHAN"
            elif n_in == 0:
                anomalies[node_id] = "X_DRIVER"
            elif n_out == 0:
                anomalies[node_id] = "DANGLING"

        if anomalies:
            from collections import Counter
            counts = Counter(anomalies.values())
            # [FIX 2026-07-10 方豆 feedback] 如果 elaboration 不完整 (内存压力),
            # 报告 anomaly 时加 "low confidence" 警告, 避免误报。
            from trace.core.compiler import is_elaboration_incomplete
            confidence = "low confidence (pyslang elaboration incomplete)" if is_elaboration_incomplete() else "high confidence"
            typer.echo(
                f"  ⚠️  RTL anomalies detected ({confidence}): {dict(counts)}",
                err=True,
            )
            if is_elaboration_incomplete():
                typer.echo(
                    "     ⚠️  WARNING: SWAP > 2GB during elaboration — graph may be incomplete.",
                    err=True,
                )
                typer.echo(
                    "     ⚠️  Anomalies above may be false positives from missing edges.",
                    err=True,
                )
            typer.echo(
                f"     ORPHAN=两端无连接 (悬空) | X_DRIVER=只出不进 (未定值) | DANGLING=只进不出 (死代码)",
                err=True,
            )
            for n, kind in list(anomalies.items())[:5]:
                short = n.split(".")[-1]
                typer.echo(f"     - {short}: {kind}", err=True)
            if len(anomalies) > 5:
                typer.echo(f"     ... and {len(anomalies) - 5} more", err=True)

        typer.echo(
            f"  Selected {len(chain_edges)} edges from {len(all_paths)} paths "
            f"({len(chain_nodes)} nodes, max={max_edges})",
            err=True,
        )

    if not chain_nodes:
        typer.echo("  Warning: no chain nodes found, output empty DOT", err=True)
        if dot_output:
            Path(dot_output).write_text(
                f'digraph chain {{ label="No data paths from {",".join(from_sigs)} to {",".join(to_sigs)}"; }}'
            )
        return

    # [FIX 2026-07-08] Truncation 已在 path-aware loop 中处理
    # (sorted_paths + greedy select) — 不再这里重复 truncate

    # 生成 DOT
    # [Phase 1 2026-07-09] 传路径 + node kinds 进去, 算每个 node 的 cycle 数 (latency)
    node_kinds = {}
    for node_id in chain_nodes:
        n = graph.get_node(node_id)
        if n is not None:
            node_kinds[node_id] = str(getattr(getattr(n, "kind", None), "name", "SIGNAL"))

    # [FIX 2026-07-10] Pass anomalies 进去, 让 DOT 用不同颜色高亮 RTL 问题
    chain_anomalies = anomalies if 'anomalies' in dir() else {}

    dot = _generate_chain_dot(
        chain_nodes, chain_edges, from_sigs, to_sigs,
        target or (Path(file).stem if file else "chain"),
        layout=layout, layout_engine=layout_engine,
        paths=sorted_paths if all_paths else None,
        node_kinds=node_kinds,
        anomalies=chain_anomalies,
        graph=graph,  # [FIX 2026-07-10] for anomaly connection lookup
    )

    # 输出
    if dot_output:
        Path(dot_output).write_text(dot)
        typer.echo(f"✓ DOT: {dot_output}", err=True)

    if png_output:
        render_with_engine(dot, png_output, layout_engine, fmt="png")
        typer.echo(f"✓ PNG: {png_output}", err=True)

    if svg_output:
        render_with_engine(dot, svg_output, layout_engine, fmt="svg")
        typer.echo(f"✓ SVG: {svg_output}", err=True)

    if not dot_output and not png_output and not svg_output:
        typer.echo(dot)


def _auto_detect_io_ports(graph, target: str, tracer=None) -> tuple[list[str], list[str]]:
    """[铁律1] 用 semantic AST (semantic_adapter.get_port_declarations) 拿 target module 的 input/output ports.

    Returns (input_signal_ids, output_signal_ids) — signal IDs 形如 "{target}.{port_name}".

    [FIX 2026-07-10] 接受 tracer 参数 (从 chain() 传入), 避免走 fallback heuristic 误报.
    Fallback heuristic 不区分 port 和 internal reg/wire, 会把 "reg 被写但未读" 误判为 output port.
    """
    from trace.core.semantic_adapter import SemanticAdapter

    # tracer from parameter, fallback to graph._tracer
    if tracer is None:
        tracer = getattr(graph, "_tracer", None)

    if tracer is None:
        # 退而求其次: scan all nodes for {target}.<name> pattern
        # [FIX 2026-07-10] 仅用 kind=PORT_IN/PORT_OUT 过滤, 避免把 dangling reg 误判为 output
        from_sigs = []
        to_sigs = []
        for node_id in graph.nodes():
            if node_id.startswith(f"{target}."):
                n = graph.get_node(node_id)
                kind_name = str(getattr(getattr(n, "kind", None), "name", "SIGNAL")) if n else "SIGNAL"
                if kind_name == "PORT_IN":
                    from_sigs.append(node_id)
                elif kind_name == "PORT_OUT":
                    to_sigs.append(node_id)
                # Skip SIGNALS/REGS/WIRES
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
    paths: list | None = None,
    node_kinds: dict | None = None,
    anomalies: dict | None = None,
    graph=None,  # [FIX 2026-07-10] for finding connections to anomaly nodes
) -> str:
    """生成 chain 专用的 DOT 图, 强制方形 layout (neato + LR).

    [Plan B+2 2026-07-08] 按 sub-module cluster 划分节点. Signal ID
    形如 "{top}.{submodule}.{signal}" (e.g. "openofdm_tx.dot11_tx.ifft64.i_clk")
    按倒数第二个 segment 划分 cluster.

    [Phase 1 2026-07-09] 新增 latency / cycle 标:
    - 每个 node 标 [cycle=N] (从 from_sigs 算起, 路径上遇到几个 reg)
    - 每条边标 [+M cycle] (src→dst 之间经过几个 reg)
    - to_sigs (路径终点) 标 'total: N cycles'
    - critical path (最长的 path) 上的节点 标红色 (highlight critical path)
    """
    lines = ["digraph chain {"]
    lines.append(f'  label="Data Chain: {title}\\n({len(edges)} edges, {len(nodes)} nodes)";')
    lines.append("  labelloc=t;")
    lines.append("  fontsize=16;")
    lines.append('  fontname="Helvetica-Bold";')
    lines.append(f"  rankdir={layout};")

    # [Phase 6.4 2026-07-12] TL;DR as visible box
    from trace.core.graph.analyzer.viz_legend import render_tldr_box
    lines.extend(render_tldr_box(f'{len(edges)} edges · {len(nodes)} nodes'))
    if layout_engine in ("neato", "fdp"):
        lines.append("  ratio=1.0;")
        lines.append("  overlap=false;")
    else:
        lines.append("  ratio=auto;")
    lines.append("  splines=true;")
    lines.append("  bgcolor=white;")
    lines.append("  pad=0.5;")
    lines.append("  nodesep=0.7;")  # 加大 node 间距
    lines.append("  ranksep=1.2;")  # 加大 rank 间距
    lines.append("")

    # [Plan B+2 2026-07-08] 按 sub-module 分组 nodes
    from_set = set(from_sigs)
    to_set = set(to_sigs)

    # [Phase 1 2026-07-09] 计算每个 node 的 cycle 数 + critical path
    # Algorithm:
    #   - cycle[node] = number of REG hops from from_sig (counted along path)
    #   - fallback: if no REG in path, cycle = path position (max 1 cycle per hop)
    #   - critical path = longest path (max cycle count)
    #   - each edge = +1 cycle (if next node is REG) or 0 (combinational)
    #   - total cycles = cycle count at path endpoint
    node_cycles: dict[str, int] = {}
    edge_cycles: dict[tuple[str, str], int] = {}
    critical_nodes: set[str] = set()
    output_total_cycles: dict[str, int] = {}
    if paths:
        # 查找最长路径 (critical path) — longest in terms of REG hops, ties break by length
        def path_score(p):
            """计算路径 'latency' score (越深 越 critical)."""
            reg_count = 0
            for n in p:
                kind = node_kinds.get(n, "") if node_kinds else ""
                if kind == "REG":
                    reg_count += 1
            return (reg_count, len(p))

        max_score = max(path_score(p) for p in paths)
        for path in paths:
            if path_score(path) == max_score:
                critical_nodes.update(path)

        for path in paths:
            # 为这个 path 计算每个 node 的 cycle 数
            reg_counts: list[int] = []
            running = 0
            for node in path:
                reg_counts.append(running)
                kind = node_kinds.get(node, "") if node_kinds else ""
                if kind == "REG":
                    running += 1
            # total cycles 该路径的: 最后 running (但加 fallback 如 node 为纯 path position)
            # 使用 max(reg counts 末值, len(path)-1) 估计下行 latency
            total_reg_in_path = max(running, len(path) - 1)
            # Track whether this path has at least one REG (for edge cycle label fallback)
            has_reg_in_path = running > 0

            for i, node in enumerate(path):
                # 计算 cycle[node] across paths (取最深的)
                cur = node_cycles.get(node, 0)
                # 用 path position 作 fallback (确保从 start 到 node 至少 i cycle 跳)
                # 取 max(reg_counts[i], i) — 这个是“从 src 到 node 经历的 cycle 下界”
                cycle_at = max(reg_counts[i], i)
                node_cycles[node] = max(cur, cycle_at)
                # output_total_cycles: 每个 node 都记一个该 path 的 total cycle
                # max across paths (即 max latency that leads to this node)
                # 但只在 to_set 或 path 终点才在最终 label 里标 total cycles
                output_total_cycles[node] = max(
                    output_total_cycles.get(node, 0), total_reg_in_path
                )
            # 边 cycle: 该 edge 贡献 +1 cycle if dst is REG else +0 (combinational same cycle)
            # fallback: 如果该 path 无 REG, 用 path position 作 cycle 估计
            for i in range(len(path) - 1):
                src, dst = path[i], path[i + 1]
                dst_kind = node_kinds.get(dst, "") if node_kinds else ""
                src_kind = node_kinds.get(src, "") if node_kinds else ""
                if dst_kind == "REG":
                    inc = 1
                elif src_kind == "REG":
                    inc = 0  # reg -> combinational, no new cycle
                elif not has_reg_in_path:
                    # 无 REG 路径: 以 path position 作 cycle (每跳 = +1, lower bound estimate)
                    inc = 1
                else:
                    # 仅 combinational: 粗估 +0 (同 cycle 内)
                    inc = 0
                cur = edge_cycles.get((src, dst), 0)
                edge_cycles[(src, dst)] = max(cur, inc)
    else:
        for node in nodes:
            node_cycles[node] = 0

    def extract_submodule(node_id: str, top: str) -> str | None:
        """提取 node 所属 sub-module. 顶层信号归属 top.
        Returns None if signal ID doesn't belong to top (external sub-module)."""
        if not node_id.startswith(f"{top}."):
            return None  # [FIX 2026-07-08] 不跳过, 归为 external
        rest = node_id[len(top) + 1:]  # strip "top."
        parts = rest.split(".")
        if len(parts) <= 1:
            return top  # top-level signal
        return f"{top}.{parts[0]}"

    # Group by submodule
    nodes_by_submodule: dict[str, set[str]] = {}
    external_nodes: set[str] = set()  # [FIX 2026-07-08] sub-module signals 没 target prefix
    for node in nodes:
        sub = extract_submodule(node, title)
        if sub is None:
            # 收集没 target prefix 的 node — 它们是 sub-module internal signals
            # (e.g. "bitreverse.i_clk" 实际是 "openofdm_tx.dot11_tx.ifft64.bitreverse.i_clk")
            # 取第一段作为 module name
            first_seg = node.split(".", 1)[0] if "." in node else node
            external_nodes.add(node)
        else:
            nodes_by_submodule.setdefault(sub, set()).add(node)

    # Generate subgraph cluster (不填背景, 只用深色虚线边框)
    cluster_borders = [
        "#cc3333",  # red
        "#3366cc",  # blue
        "#33aa33",  # green
        "#cc8833",  # orange
        "#aa33aa",  # purple
        "#33aaaa",  # cyan
        "#999933",  # olive
        "#663399",  # indigo
    ]
    for i, (sub, sub_nodes) in enumerate(sorted(nodes_by_submodule.items())):
        if sub == title:
            sub_label = f"{sub} (top)"
        else:
            short = sub.split(".")[-1] if "." in sub else sub
            sub_label = f"{short}"
        border_color = cluster_borders[i % len(cluster_borders)]
        lines.append(f'  subgraph "cluster_{sanitize_dot_id_inner(sub)}" {{')
        lines.append(f'    label="{sub_label}";')
        lines.append(f'    style="rounded,dashed";')  # [FIX] 虚线边框, 不填背景
        lines.append(f'    color="{border_color}";')
        lines.append(f'    penwidth=2.5;')
        lines.append(f'    fontsize=14;')
        lines.append(f'    fontcolor="{border_color}";')  # [FIX] 跟边框同色
        lines.append(f'    fontname="Helvetica-Bold";')  # [FIX] 加粗 (必须 quote)
        for node in sorted(sub_nodes):
            safe_id = sanitize_dot_id_inner(node)
            # [FIX 2026-07-10] Anomaly 高亮 (RTL 语义检查)
            anomaly = (anomalies or {}).get(node)
            if anomaly == "ORPHAN":
                color = "#888888"  # 灰色 — 两边无连接
                shape = "diamond"
            elif anomaly == "X_DRIVER":
                color = "#cc8800"  # 橙色 — 只出不进 (X 驱动)
                shape = "diamond"
            elif anomaly == "DANGLING":
                color = "#cc0000"  # 鲜红 — 只进不出 (死代码)
                shape = "diamond"
            elif anomaly in ("DANGLING_INPUT", "DANGLING_OUTPUT"):
                color = "#cc6600"  # 深橙 — 端口两端问题
                shape = "diamond"
            elif node in from_set:
                color = "#22aa55"  # green for inputs
                shape = "invhouse"
            elif node in to_set:
                color = "#cc3333"  # [FIX] 更鲜明的红
                shape = "invhouse"
            elif node in critical_nodes:
                # [Phase 1 2026-07-09] critical path 标鲜红色
                color = "#dd2222"
                shape = "box"
            else:
                color = "#3366cc"  # [FIX] 更鲜明的蓝
                shape = "box"
            # [FIX] 改进 label: 短 label + 换行
            label = format_node_label_chain(node, title)
            cycle = node_cycles.get(node, 0)
            # [Phase 1 2026-07-09] 输出节点加 total cycles, 中间节点按 fall-back 加 cycle label
            # to_set 终点 加 Total cycles (流水线总延迟)
            if node in to_set and node in output_total_cycles:
                total = output_total_cycles[node]
                label = f"{label}\\nTotal cycles: {total}"
            elif cycle > 0:
                label = f"{label}\\n[cycle={cycle}]"
            lines.append(
                f'    "{safe_id}" [label="{label}" shape={shape} style="filled,rounded" '
                f'fillcolor="{color}" fontcolor="white" fontsize=11 fontname="Helvetica"];'
            )
        lines.append(f'  }}')

    # [FIX 2026-07-08] External sub-module cluster (e.g. bitreverse.i_clk 没 target prefix)
    # 放在独立 cluster 里, 用灰色虚线边框 + 灰色填充 (不跟正常 cluster 混淆)
    if external_nodes:
        lines.append(f'  subgraph "cluster_external" {{')
        lines.append(f'    label="External sub-modules";')
        lines.append(f'    style="rounded,dashed";')
        lines.append(f'    color="#999999";')
        lines.append(f'    penwidth=2.0;')
        lines.append(f'    fontsize=12;')
        lines.append(f'    fontcolor="#666666";')
        lines.append(f'    fontname="Helvetica-Bold";')
        lines.append(f'    bgcolor="#f5f5f5";')  # 极浅灰背景区分
        for node in sorted(external_nodes):
            safe_id = sanitize_dot_id_inner(node)
            if node in from_set:
                color = "#22aa55"
                shape = "invhouse"
            elif node in to_set:
                color = "#cc3333"
                shape = "invhouse"
            elif node in critical_nodes:
                # [Phase 1 2026-07-09] critical path 红色
                color = "#dd2222"
                shape = "box"
            else:
                color = "#3366cc"
                shape = "box"
            label = format_node_label_chain(node, title)
            cycle = node_cycles.get(node, 0)
            if cycle > 0:
                label = f"{label}\\n[cycle={cycle}]"
            lines.append(
                f'    "{safe_id}" [label="{label}" shape={shape} style="filled,rounded" '
                f'fillcolor="{color}" fontcolor="white" fontsize=10 fontname="Helvetica"];'
            )
        lines.append(f'  }}')

    lines.append("")

    # 边定义 (深色加粗)
    for src, dst in sorted(edges):
        src_safe = sanitize_dot_id_inner(src)
        dst_safe = sanitize_dot_id_inner(dst)
        # [Phase 1 2026-07-09] 加 cycle label 到边上
        edge_cyc = edge_cycles.get((src, dst), 0)
        if edge_cyc > 0:
            # critical path 红边, 普通黑边
            if src in critical_nodes and dst in critical_nodes:
                color = "#dd2222"
                penwidth = 2.5
                edge_label = f' label="+{edge_cyc} cycle" fontcolor="#dd2222" fontsize=10'
            else:
                color = "#222222"
                penwidth = 1.5
                edge_label = f' label="+{edge_cyc} cycle" fontcolor="#666666" fontsize=9'
            lines.append(
                f'  "{src_safe}" -> "{dst_safe}" [color="{color}" penwidth={penwidth}{edge_label} arrowhead=normal];'
            )
        else:
            lines.append(f'  "{src_safe}" -> "{dst_safe}" [color="#222222" penwidth=1.5 arrowhead=normal];')

    # [FIX 2026-07-10 方豆 feedback 14:20] 加 "Anomalies" cluster, 展示未在 data path 上的异常信号
    # 背景: chain 报告 X_DRIVER/DANGLING/ORPHAN 但这些信号可能不在 data path 上 (如 orphan_wire)。
    #       用户看不到图里这个 bug — 只能从 stderr 读出来。
    # 修法: 把 anomalies 画到独立 cluster, 用虚线箭头表示“该走的连接”, 让用户能肉眼看到问题。
    if anomalies:
        anomaly_nodes_in_path = {n for n in anomalies if n in nodes}
        anomaly_nodes_outside = {n for n in anomalies if n not in nodes}
        if anomaly_nodes_outside:
            lines.append("")
            lines.append('  // === RTL Anomalies (out-of-path X_DRIVER / DANGLING / ORPHAN) ===')
            lines.append('  subgraph "cluster_anomalies" {')
            lines.append(f'    label="RTL Anomalies ({len(anomaly_nodes_outside)} signals, NOT on data path)";')
            lines.append('    style="rounded,dashed";')
            lines.append('    color="#cc6600";')
            lines.append('    penwidth=2.5;')
            lines.append('    fontsize=12;')
            lines.append('    fontcolor="#cc6600";')
            lines.append('    fontname="Helvetica-Bold";')
            lines.append('    bgcolor="#fff5e6";')
            for n in sorted(anomaly_nodes_outside):
                kind = anomalies[n]
                safe_id = sanitize_dot_id_inner(n)
                # Color by anomaly type
                if kind == "X_DRIVER":
                    color = "#cc8800"
                elif kind == "DANGLING":
                    color = "#cc0000"
                elif kind == "ORPHAN":
                    color = "#888888"
                else:
                    color = "#cc6600"
                label = format_node_label_chain(n, title)
                # Add anomaly type to label
                label = f"{label}\\n[{kind}]"
                lines.append(
                    f'    "{safe_id}" [label="{label}" shape=diamond style="filled,rounded" '
                    f'fillcolor="{color}" fontcolor="white" fontsize=10 fontname="Helvetica-Bold"];'
                )
            lines.append('  }')
            # Add dashed "ghost" edges to show the broken connection:
            # For X_DRIVER: dashed edge to consumers (showing the unwired path)
            # For DANGLING: dashed edge from drivers (showing the unwired path)
            # [FIX 2026-07-11] 限制 ghost edges 数量, 不让 max-edges 限制失效
            # (之前不加限制 → 100+ anomalies 时 DOT 有 40+ 边, 违反 max-edges=5 的预期)
            MAX_GHOST_EDGES = 20
            ghost_count = 0
            for n in anomaly_nodes_outside:
                if ghost_count >= MAX_GHOST_EDGES:
                    break
                safe_id = sanitize_dot_id_inner(n)
                kind = anomalies[n]
                if graph is None:
                    continue
                # Find connections in full graph
                if kind == "X_DRIVER":
                    # Dashed edges to consumers
                    for succ in graph.successors(n):
                        succ_safe = sanitize_dot_id_inner(succ)
                        # If successor is in chain, draw dashed connection
                        if succ in nodes:
                            if ghost_count >= MAX_GHOST_EDGES:
                                break
                            lines.append(
                                f'  "{safe_id}" -> "{succ_safe}" [color="#cc8800" style=dashed penwidth=1.5 '
                                f'label="X-driver path" fontcolor="#cc8800" fontsize=8 arrowhead=normal];'
                            )
                            ghost_count += 1
                elif kind == "DANGLING":
                    # Dashed edges from drivers
                    for pred in graph.predecessors(n):
                        pred_safe = sanitize_dot_id_inner(pred)
                        if pred in nodes:
                            if ghost_count >= MAX_GHOST_EDGES:
                                break
                            lines.append(
                                f'  "{pred_safe}" -> "{safe_id}" [color="#cc0000" style=dashed penwidth=1.5 '
                                f'label="unread path" fontcolor="#cc0000" fontsize=8 arrowhead=normal];'
                            )
                            ghost_count += 1
            if ghost_count >= MAX_GHOST_EDGES:
                lines.append(
                    f'  // Ghost edges capped at {MAX_GHOST_EDGES} (use higher max-edges to see more)'
                )

    lines.append("}")
    return "\n".join(lines)


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
    show_source=False,
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
        node_style={"risk_color": True, "cover_marker": True, "show_fan": True, "show_type": True, "show_source": show_source},
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
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    strict: bool = STRICT_OPTION,
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
) -> None:
    """[PR1+PR4 2026-06-15] L1 module-level + L2 cross-instance port visualization.

    1 box = 1 sub-module instance. PR4 加 instance-to-instance port 边 (MIG).
    用于项目架构 review.

    [Phase B 2026-07-17] --file/--filelist/--include/--strict via shared options.
    [Phase B] Module 命令不走 build_viz_tracer 因为它需要 AST path (semantic_adapter)
    不是单纯 graph. 直接用 UnifiedTracer 构造, 保留原有的二进制垃圾-safe except.
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

    # [Phase 6.3 2026-07-12] Shared legend
    from trace.core.graph.analyzer.viz_legend import render_legend
    lines.extend(render_legend('chain'))

    lines.append('}')
    with open(path, "w") as f:
        f.write("\n".join(lines))


# =============================================================================
# V6 2026-07-19: 用户反馈 "我想要对理解有帮助的图"
#   4 个 use cases (a/b/c/d) 全都实现为 unified `teach` subcommand:
#
#   a) 速懂陌生模块    → 默认行为: 生成结构化 "教学页" (HTML)
#                      包含 ports + FSM + pipeline + coverage summary
#   b) 查 1 条信号路径 → --focus SIGNAL + --depth N (BFS 后继)
#                      或 --upstream (寻找前驱)
#   c) 看控制关系      → --focus SIGNAL + --show-drives 印记边
#                      （驱动其他 signal 的边被标亮）
#   d) 看覆盖缺口      → --show-coverage: 点了 SVA/Coverage 才标
#
#   输出: /tmp/teach.html (interactive) 或 DOT.
# =============================================================================
@vis_app.command(name="teach")
def teach(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    strict: bool = STRICT_OPTION,
    target: str = typer.Option(
        "top", "--target", "-t",
        help="Target module to teach (e.g. uart_top, fifo, scheduler_minimal)",
    ),
    focus: str = typer.Option(
        None, "--focus", "-F",
        help="[B/C] Focus on a specific signal; show its N-hop neighborhood",
    ),
    depth: int = typer.Option(
        2, "--depth", "-d",
        help="[B/C] Number of BFS hops from focus signal (default 2)",
    ),
    upstream: bool = typer.Option(
        False, "--upstream",
        help="[B] BFS upward (find what drives --focus signal) instead of downstream",
    ),
    show_coverage: bool = typer.Option(
        False, "--show-coverage",
        help="[D] Highlight signals NOT covered by SVA/Covergroup",
    ),
    show_drives: bool = typer.Option(
        False, "--show-drives",
        help="[C] Highlight edges driven by --focus signal "
             "(limitations: combinational deps via `always @*` are NOT in graph; "
             "if focus has 0 outgoing edges you'll see a comment in the DOT)",
    ),
    show_source: bool = typer.Option(
        False, "--show-source",
        help="[V6.2 2026-07-20] Annotate each node label with 'file:line' "
             "so you can jump to that line in your editor (use the URL in HTML output)",
    ),
    output_html: str = typer.Option(
        None, "--html", help="Output interactive HTML teaching page",
    ),
    output_dot: str = typer.Option(
        None, "--dot", "-d", help="Output focused DOT",
    ),
) -> None:
    """[V6 2026-07-19] Teaching-level view of a module.

    Default: produce an HTML summary page with ports + structure + coverage
    overview — aimed at "5 分钟读懂一个陌生模块" (use case A).

    With --focus SIGNAL: zoom in on a single signal's reachability
    graph for understanding its dataflow impact (use case B and C).

    With --show-coverage: highlight signals without SVA/Coverage (use case D).

    Example:
        sv_query visualize teach -f uart.sv --target uart_top --html /tmp/u.html
        sv_query visualize teach --filelist f.f --target uart_top \\
            --focus phy_tx_start --depth 3 --html /tmp/u.html
        sv_query visualize teach --filelist f.f --target uart_top \\
            --focus state_q --depth 1 --show-drives --html /tmp/u.html
        sv_query visualize teach --filelist f.f --target uart_top \\
            --show-coverage --html /tmp/u.html
    """
    from trace.core.compiler import CompilationError
    from cli._common import handle_compilation_error
    from cli._viz_common import build_viz_tracer, get_viz_sources
    from trace.core.graph.analyzer.pipeline_viz import detect_pipeline
    from trace.core.graph.analyzer.signal_classifier import classify_graph

    try:
        tracer, graph_obj = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            strict=strict, target_module=target,
        )
        sources = get_viz_sources(tracer, file, filelist)
        sva = SVAExtractor(sources).extract()
        cov_list = CovergroupExtractor(sources).extract()
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    # Coverage + SVA -> signal sets (for D)
    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)
    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)
    covered = sva_signals | cov_signals

    # [B/C] BFS to compute focus subgraph
    focus_id = None
    neighborhood: set[str] = set()
    if focus:
        focus_id = _resolve_signal_id(graph_obj, focus)
        if focus_id is None:
            typer.echo(f"Error: signal '{focus}' not found in graph", err=True)
            typer.echo(f"  Hint: use 'sv_query graph dump --file F' to list all signals", err=True)
            raise typer.Exit(1)
        # BFS in chosen direction
        bfs_direction = "predecessors" if upstream else "successors"
        bfs_fn = getattr(graph_obj, bfs_direction)
        from collections import deque
        # focus node IS in neighborhood
        neighborhood.add(focus_id)
        seen = {focus_id}
        queue = deque([(focus_id, 0)])
        while queue:
            nid, d = queue.popleft()
            if d >= depth:
                continue
            for nbr in bfs_fn(nid):
                if nbr not in seen:
                    seen.add(nbr)
                    neighborhood.add(nbr)
                    queue.append((nbr, d + 1))

    # Build DOT
    dot_lines = _render_teach_dot(
        graph_obj, target, focus_id, neighborhood,
        show_coverage=show_coverage, covered=covered,
        show_drives=show_drives,
        show_source=show_source,
        direction_label="upstream" if upstream else "downstream",
    )
    dot_text = "\n".join(dot_lines)

    # Summary (printed always)
    if focus:
        typer.echo(f"Focus signal: {focus_id}")
        typer.echo(f"  direction: {'upstream' if upstream else 'downstream'}, depth: {depth}")
        typer.echo(f"  neighborhood nodes: {len(neighborhood)}")
    classification = classify_graph(graph_obj)
    if not focus:
        # Print summary when not in focus mode
        info = detect_pipeline(graph_obj, classification)
        # [FIX 2026-07-19] classification.data_nodes 等可能是 list, 转成 set
        data_nodes_set = set(classification.data_nodes)
        control_nodes_set = set(classification.control_nodes)
        clock_nodes_set = set(classification.clock_nodes)
        typer.echo(f"\n=== Teach Summary: {target} ===")
        typer.echo(f"  Pipeline regs:   {len(info.pipeline_regs)}")
        typer.echo(f"  State regs:      {len(info.state_regs)}")
        typer.echo(f"  Pipeline stages: {info.total_latency}")
        typer.echo(f"  Data nodes:      {len(data_nodes_set)}")
        typer.echo(f"  Control nodes:   {len(control_nodes_set)}")
        typer.echo(f"  Clock nodes:     {len(clock_nodes_set)}")
        typer.echo(f"  SVA signals:     {len(sva_signals)}")
        typer.echo(f"  Coverpoints:     {len(cov_signals)}")
        typer.echo(f"  Total covered:   {len(covered)} signals")
        typer.echo(f"  All nodes:       {graph_obj.number_of_nodes()}")
        typer.echo(f"  All edges:       {graph_obj.number_of_edges()}")
        typer.echo("")

    if output_dot:
        Path(output_dot).write_text(dot_text)
        typer.echo(f"✓ DOT: {output_dot}")
    if output_html:
        Path(output_html).write_text(_render_teach_html(
            target=target,
            focus=focus_id,
            neighborhood_size=len(neighborhood),
            dot_text=dot_text,
            show_coverage=show_coverage,
            covered_count=len(covered),
            graph_obj=graph_obj,
        ))
        typer.echo(f"✓ HTML: {output_html}")
    if not output_dot and not output_html:
        typer.echo(dot_text)


def _resolve_signal_id(graph_obj, hint: str) -> str | None:
    """[V6] Resolve a user-provided signal name to a graph node id.

    Tries:
      1. Exact match
      2. Suffix match (e.g. `phy_tx_start` -> `top.dut.phy_tx_start`)
    Returns first suffix match if unique, otherwise None.
    """
    if hint in graph_obj:
        return hint
    suffix_matches = [n for n in graph_obj.nodes() if n == hint or n.endswith("." + hint)]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    if len(suffix_matches) > 1:
        # Prefer shortest (closest to top)
        suffix_matches.sort(key=len)
        return suffix_matches[0]
    return None


def _render_teach_dot(
    graph_obj, target: str, focus_id: str | None, neighborhood: set[str],
    show_coverage: bool, covered: set[str], show_drives: bool,
    show_source: bool = False,
    direction_label: str = "downstream",
) -> list[str]:
    """[V6] Render a focused / coverage-aware DOT for the teach command."""
    lines: list[str] = []
    if focus_id:
        lines.append(f'digraph teach_focus {{')
        lines.append(f'  label="Focused Graph: {focus_id} ({direction_label})";')
    else:
        lines.append(f'digraph teach {{')
        lines.append(f'  label="Teach View: {target}";')
    lines.append('  rankdir=LR;')
    lines.append('  splines=polyline;')
    lines.append('  nodesep=0.4;')
    lines.append('  ranksep=0.6;')
    lines.append('  node [shape=box style="rounded,filled" fontname=Helvetica fontsize=10];')

    # Decide node set:
    # - If focus: only neighborhood (+ focus_id)
    # - Else: top 100 by some heuristic (alphabetical first)
    if focus_id:
        node_set = neighborhood
    else:
        node_set = set(list(graph_obj.nodes())[:100])  # crude cap

    # Render nodes
    for nid in sorted(node_set):
        if not nid:
            continue
        node = graph_obj.get_node(nid)
        if not node:
            continue
        name = node.name or nid.split(".")[-1]
        safe_name = sanitize_dot_id(name).replace('"', '')
        kind = node.kind.name if node.kind else ""
        # [FIX V6.1 2026-07-20] Drop width display: node.width is unreliable
        # for inferred register widths (clk declared 1-bit showed [2b]).
        # Width labelling was Bug-3 root cause. Focus on kind+name only.
        label = f"{safe_name}\\n{kind}"
        # [V6.2 2026-07-20] Annotate with source location if requested.
        # Makes the graph a "where to look next" tool — click a node,
        # editor jumps to that file:line.
        if show_source:
            f = getattr(node, 'file', '') or ''
            ln = getattr(node, 'line', 0) or 0
            if f and ln > 0:
                # Use short filename for readability
                short_f = f.split("/")[-1]
                label += f"\\n{short_f}:{ln}"
        # Default fill
        fillcolor = "#88bbdd"
        # Coverage overlay (D)
        # [FIX V6.1 2026-07-20] covered set has short names ('state_q', 'sel')
        # but nids are full hierarchy ('coverage_demo.state_q'). Match
        # either the full nid or the suffix after last '.'.
        if show_coverage:
            short_name = nid.rsplit(".", 1)[-1]
            if nid not in covered and short_name not in covered:
                fillcolor = "#ffaa88"  # uncovered: salmon
                label += "\\n🚨"
        # Focus highlight
        penwidth = 1
        if nid == focus_id:
            fillcolor = "#ffcc00"  # focus: bright yellow
            penwidth = 3
        lines.append(
            f'  "{nid}" [label="{label}" fillcolor="{fillcolor}" '
            f'penwidth={penwidth}'
            + (f' tooltip="{getattr(node, "file", "")}:{getattr(node, "line", 0)}" URL="{getattr(node, "file", "")}#{getattr(node, "line", 0)}"' if show_source else '')
            + '];'
        )
    # Render edges
    edges_drawn = 0
    edges_skipped_outside = 0
    MAX_EDGES = 200
    for u, v in graph_obj.edges():
        if u not in node_set or v not in node_set:
            # Bug-1 fix: Tell user when their focus signal *should* have
            # edges (outgoing) but they fall outside the depth window.
            edges_skipped_outside += 1
            continue
        if edges_drawn >= MAX_EDGES:
            break
        edges_drawn += 1
        # Default edge style
        color = "#226699"
        penwidth = 1
        style = "solid"
        # Drives highlight (C) - focus signal as driver
        if show_drives and focus_id and u == focus_id:
            color = "#ff9900"
            penwidth = 2.5
            style = "bold"
        lines.append(
            f'  "{u}" -> "{v}" [color="{color}" penwidth={penwidth} style={style}];'
        )
    if edges_drawn >= MAX_EDGES:
        lines.append('  // truncated at max edges')

    # [FIX V6.1 2026-07-20] Bug-1 root cause acknowledgement: when a focus
    # signal has NO outgoing edges (because combinational deps in `always @*`
    # are not tracked by graph), print a comment in the DOT so user understands.
    if focus_id and show_drives and edges_drawn == 0:
        focus_node = graph_obj.get_node(focus_id)
        if focus_node and graph_obj.out_degree(focus_id) == 0:
            lines.append(
                f'  // Note: {focus_id} has no graph successors.\n'
                f'  // Combinational dependencies from this signal (via always @* blocks)\n'
                f'  // are not captured in the dataflow graph. Use pipeline/ for state machines.'
            )

    lines.append('}')
    return lines


def _render_teach_html(
    target: str, focus: str | None, neighborhood_size: int,
    dot_text: str, show_coverage: bool, covered_count: int, graph_obj,
) -> str:
    """[V6] Wrap teach DOT in a minimal interactive HTML viewer.

    This is intentionally simple — a self-contained page with:
    - Summary header
    - Embedded DOT (rendered via viz.js CDN)
    - Color legend
    """
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Teach View: {target}</title>
<script src="https://unpkg.com/viz.js@2.1.2/viz.js"></script>
<script src="https://unpkg.com/viz.js@2.1.2/full.render.js"></script>
<style>
body {{ font-family: -apple-system, Helvetica, sans-serif; margin: 20px; max-width: 1200px; }}
.summary {{ background: #f4f4f4; padding: 16px; border-radius: 8px; margin-bottom: 16px; }}
.summary h2 {{ margin-top: 0; color: #226699; }}
.summary dl {{ display: grid; grid-template-columns: 180px 1fr; gap: 4px; }}
.summary dt {{ font-weight: bold; }}
.dd-colored {{ display: inline-block; padding: 2px 8px; border-radius: 3px; color: white; margin-right: 8px; }}
#graph {{ border: 1px solid #ccc; min-height: 400px; padding: 8px; }}
</style>
</head>
<body>
<div class="summary">
<h2>Teach View: <code>{target}</code></h2>
{'<p><b>Focus:</b> <code>' + focus + '</code>, neighborhood: ' + str(neighborhood_size) + ' nodes</p>' if focus else ''}
{'<p><b>Coverage overlay:</b> enabled — uncovered signals marked 🚨</p>' if show_coverage else ''}
<p><b>Total covered signals in module:</b> {covered_count}</p>
<h3>Legend</h3>
<p>
<span class="dd-colored" style="background:#ffcc00">focus signal</span>
<span class="dd-colored" style="background:#88bbdd">regular signal</span>
{'<span class="dd-colored" style="background:#ffaa88">uncovered</span>' if show_coverage else ''}
</p>
</div>

<h3>Graph</h3>
<div id="graph"></div>
<script>
const dotSource = {dot_text!r};
const params = {{ engine: 'dot', format: 'svg' }};
Viz.svg(dotSource).then(svg => {{
    document.getElementById('graph').innerHTML = svg;
}}).catch(err => {{
    document.getElementById('graph').innerText = 'render error: ' + err;
}});
</script>

</body>
</html>"""


if __name__ == "__main__":
    typer.run(vis_app)
