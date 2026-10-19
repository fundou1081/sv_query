# ==============================================================================
# visualize_common.py — visualize 子命令: 共享 helper (拆分模块/IO 端口探测/图与 gap 可视化执行)
# ==============================================================================
"""[iter_254 T3-3] 从 `view/visualize.py` (2,376 行 / 10 个命令) 拆出: 共享 helper (拆分模块/IO 端口探测/图与 gap 可视化执行)。
命令注册仍在 `visualize.py` (避免循环 import); 本模块只含实现。
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from cli._paths import ensure_on_path, SRC_DIR  # noqa: E402
ensure_on_path(SRC_DIR)
import warnings

import typer

warnings.filterwarnings("ignore")

from cli._viz_common import (  # noqa: E402
    FILE_OPTION,
    FILELIST_OPTION,
    INCLUDE_OPTION,
    SHOW_SOURCE_OPTION,
    build_viz_tracer,
    get_viz_sources,
)
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.analyzer._dot_common import (  # noqa: E402
    format_node_label_chain,
    render_with_engine,
    sanitize_dot_id,
    sanitize_dot_id_inner,
)
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer
import logging

logger = logging.getLogger(__name__)

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
    # - 1-segment paths (e.g. 'XRES')           -> group 'XRES' (lone module)
    # - 2-segment paths (e.g. 'darksocv.XRES') -> group 'darksocv' (top-level signal)
    # - 3+ segment paths                       -> group by first 2 segments
    #                                            (e.g. 'darksocv.bridge0.XRES' -> 'darksocv.bridge0')
    # This way 'darksocv.XRES' and 'darksocv.bridge0.XRES' go to DIFFERENT groups.
    groups = defaultdict(set)
    for nid in graph.nodes():
        if not isinstance(nid, str) or not nid or nid[0].isdigit() or nid.startswith("__"):
            continue
        parts = nid.split('.')
        # 2-segment node -> group by first 1 part (top-level module)
        # 3+ segment node -> group by first 2 parts (sub-instance)
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
        from trace.core.graph.analyzer.signal_classifier import SignalClass, SignalClassification
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

    tracer = UnifiedTracer(sources=sources, include_dirs=include_dirs, filelist=filelist)
    graph = tracer.build_graph(use_cache=cache)

    # SVA/Covergroup 提取需要源码
    # 使用 filelist 时，源码已在 tracer 的 compiler 里，重复编译会导致 redefinition
    if sources is None and filelist:
        # 从 tracer 的 compiler 复用已加载的 sources
        sources_for_extractors = tracer._get_compiler()._sources
        sva = SVAExtractor(sources_for_extractors).extract()
        cov_list = CovergroupExtractor(sources_for_extractors).extract()
    elif sources:
        sva = SVAExtractor(sources).extract()
        cov_list = CovergroupExtractor(sources).extract()
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

    # [V12] ELK.js 渲染路径
    from trace.core.graph.analyzer.signal_classifier import classify_graph as _cls
    from trace.core.graph.viz import VizBuildOptions, build_viz_data
    from trace.core.graph.viz.viz_engine import render_dataflow

    classification = _cls(graph)
    viz = build_viz_data(graph, VizBuildOptions(
        target_module=file or "Signal Graph",
        max_edges=max_edges,
        include_node_class=True,
        classification=classification,
        include_edge_condition=show_conditions,
        include_edge_expression=True,
    ))

    if dot_output:
        svg_text = render_dataflow(viz, {"title": f"Signal Graph: {file}"})
        Path(dot_output).write_text(svg_text)
        print(f"✓ SVG: {dot_output}")

    if mmd_output:
        print(f"  (Mermaid output deprecated, use --dot for SVG)")

    if html_output:
        print(f"  (HTML output deprecated, use --dot for SVG)")

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
        # [V12] ELK.js SVG 输出
        from trace.core.graph.viz import VizBuildOptions, build_viz_data
        from trace.core.graph.viz.viz_engine import render_dataflow
        from trace.core.graph.analyzer.signal_classifier import classify_graph as _cls
        classification = _cls(graph)
        viz = build_viz_data(graph, VizBuildOptions(
            target_module=file,
            include_node_class=True,
            classification=classification,
            include_edge_condition=True,
            include_edge_expression=True,
            max_edges=200,
        ))
        svg_text = render_dataflow(viz, {"title": f"Verification Gap: {file}"})
        Path(dot_output).write_text(svg_text)
        print(f"✓ SVG: {dot_output}")

        # 渲染为 PNG
        png_output = dot_output.replace(".dot", ".png").replace(".svg", ".png")
        import subprocess
        try:
            rc = subprocess.run(
                ["cairosvg", dot_output, "-o", png_output],
                check=True, capture_output=True,
            ).returncode
            print(f"✓ PNG: {png_output}")
        except Exception as e:
            print(f"  (PNG渲染失败: {e})")

    if html_output:
        # [V12] HTML 暂不支持, 输出 SVG
        print(f"  (HTML output deprecated, use --dot for SVG)")

    print(f"\n  📊 Gap signals: {len(gap_signals)} (risk >= {min_risk})")

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
