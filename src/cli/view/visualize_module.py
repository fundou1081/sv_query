# ==============================================================================
# visualize_module.py — visualize 子命令: module 命令 + DOT 写出
# ==============================================================================
"""[iter_254 T3-3] 从 `view/visualize.py` (2,376 行 / 10 个命令) 拆出: module 命令 + DOT 写出。
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

def module(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
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
        None, "--emit-dot", help="Write DOT graph to file (raw DOT; 可视化统一用 --svg 输出渲染结果)",
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

    [Phase B 2026-07-17] --file/--filelist/--include via shared options.
    [Phase B] Module 命令不走 build_viz_tracer 因为它需要 AST path (semantic_adapter)
    不是单纯 graph. 直接用 UnifiedTracer 构造, 保留原有的二进制垃圾-safe except.
    """
    from trace.core.module_extractor import (
        extract_module_edges_from_mig,
        extract_module_from_graph,
    )

    if not file and not filelist:
        typer.echo("Error: need --file or --filelist", err=True)
        raise typer.Exit(1)

    include_dirs = include.split(",") if include else None
    try:
        if filelist:
            tracer = UnifiedTracer(
                filelist=filelist, include_dirs=include_dirs, 
            )
        else:
            with open(file) as f:
                sources = {file: f.read()}
            tracer = UnifiedTracer(
                sources=sources, include_dirs=include_dirs, 
            )
    except Exception as e:
        # [FIX 2026-06-26] safe print: e may contain binary garbage from pyslang
        try:
            msg = f"Error building tracer: {e}"
        except (UnicodeDecodeError, TypeError):
            msg = "Error building tracer: <message contains binary garbage>"
        typer.echo(msg, err=True)
        raise typer.Exit(1) from None

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
    except Exception as e:
        logger.warning("%s: 忽略 Exception: %s", __name__, e)

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
      'axi_xbar_dp_ram.i_xbar_intf' -> 'axi_xbar_intf'
      'axi_xbar_dp_ram.i_xbar_intf.i_xbar' -> 'axi_xbar'
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
