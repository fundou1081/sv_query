# ==============================================================================
# visualize_teach.py — visualize 子命令: teach 命令 + DOT/HTML 渲染
# ==============================================================================
"""[iter_254 T3-3] 从 `view/visualize.py` (2,376 行 / 10 个命令) 拆出: teach 命令 + DOT/HTML 渲染。
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

from cli.view.visualize_common import _resolve_signal_id

def teach(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
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
        None, "--emit-dot", "-d", help="Output focused DOT (raw DOT)",
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
    from cli._common import handle_compilation_error
    from trace.core.compiler import CompilationError
    from trace.core.graph.analyzer.pipeline_viz import detect_pipeline
    from trace.core.graph.analyzer.signal_classifier import classify_graph

    try:
        tracer, graph_obj = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            target_module=target,
        )
        sources = get_viz_sources(tracer, file, filelist)
        sva = SVAExtractor(sources).extract()
        cov_list = CovergroupExtractor(sources).extract()
    except CompilationError as e:
        handle_compilation_error(e)
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
            typer.echo("  Hint: use 'sv_query graph dump --file F' to list all signals", err=True)
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

def _render_teach_dot(
    graph_obj, target: str, focus_id: str | None, neighborhood: set[str],
    show_coverage: bool, covered: set[str], show_drives: bool,
    show_source: bool = False,
    direction_label: str = "downstream",
) -> list[str]:
    """[V6] Render a focused / coverage-aware DOT for the teach command."""
    lines: list[str] = []
    if focus_id:
        lines.append('digraph teach_focus {')
        lines.append(f'  label="Focused Graph: {focus_id} ({direction_label})";')
    else:
        lines.append('digraph teach {')
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
        # [V6.3 2026-07-22] Edge condition label.
        # For if/case/ternary the extractor stores the guarding condition
        # on each driver edge (e.g. `sel` for `if(sel) y<=a`, `!sel` for else,
        # `op == 2'd0` for case branches). Surface it as an edge label so the
        # user can see *which condition activates each path* at a glance.
        # Prefer raw `condition` (full expression like `op == 2'd0`) over
        # `effective_condition` (cleaned to just the value, e.g. `2'd0`) so
        # the user sees BOTH the selector and the value.
        # Skip CLOCK/ENABLE/RESET edges since their 'condition' is just the
        # always-block guard, not a per-edge guard.
        edge_label = ""
        # [FIX 2026-08-13] 条件链拼接: 之前只读 edge.condition (简化成 'a == 2'b0'),
        #   丢了内层 ternary 条件. 根因在渲染层 (非 driver_extractor — 该层已正确填
        #   condition_chain e.g. ['a == 2'b0', 'g']). 现在优先用 condition_chain
        #   拼接完整条件.
        try:
            edge = graph_obj.get_edge(u, v)
            if edge is not None:
                kind = getattr(edge, "kind", None)
                kind_name = getattr(kind, "name", "") if kind else ""
                if kind_name == "DRIVER":
                    chain = getattr(edge, "condition_chain", None) or []
                    chain = [c for c in chain if c]
                    if chain:
                        # [FIX 2026-08-13] 用 condition_chain 拼接完整条件.
                        # case 套 ternary 时 chain 含比较运算符 (e.g. ['a == 2'b0','g']),
                        #   期望带括号 '(a == 2'b0) && (g)'; 纯 ternary 嵌套时 chain 是
                        #   纯信号名 (e.g. ['g','h']), 期望不带括号 'g && h'.
                        # 判据: chain 长度 > 1 且任一元素含比较运算符 ('==' 或 verilog 字面量)
                        #   → 全加括号; 否则直接 join 不带括号.
                        has_cmp = any(("==" in c) or ("'b" in c) or ("'h" in c) or ("'d" in c) for c in chain)
                        if len(chain) > 1 and has_cmp:
                            edge_label = " && ".join(f"({c})" for c in chain)
                        else:
                            edge_label = " && ".join(chain)
                    else:
                        cond = (getattr(edge, "condition", "") or "").strip() \
                            or (getattr(edge, "effective_condition", "") or "").strip()
                        edge_label = cond
        except Exception:
            edge_label = ""
        # Drives highlight (C) - focus signal as driver
        if show_drives and focus_id and u == focus_id:
            color = "#ff9900"
            penwidth = 2.5
            style = "bold"
        label_attr = f' label="{edge_label}"' if edge_label else ''
        lines.append(
            f'  "{u}" -> "{v}" [color="{color}" penwidth={penwidth} style={style}{label_attr}];'
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
