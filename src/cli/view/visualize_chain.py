# ==============================================================================
# visualize_chain.py — visualize 子命令: chain 命令 + DOT 生成
# ==============================================================================
"""[iter_254 T3-3] 从 `view/visualize.py` (2,376 行 / 10 个命令) 拆出: chain 命令 + DOT 生成。
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

from cli.view.visualize_common import _auto_detect_io_ports

def chain(
    file: str = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    include: str = INCLUDE_OPTION,
    target: str = typer.Option(None, "--target", "-t", help="Target module (focus scope)"),
    from_signals: list[str] = typer.Option([], "--from", help="Source signal(s) (e.g. dot11_tx.phy_tx_start). Can pass multiple."),
    to_signals: list[str] = typer.Option([], "--to", help="Target signal(s) (e.g. dot11_tx.result_i). Can pass multiple."),
    auto: bool = typer.Option(False, "--auto", help="Auto-detect all input ports -> output ports paths in --target module"),
    max_edges: int = typer.Option(30, "--max-edges", help="Max edges to render (default 30, prevents huge graphs)"),
    max_depth: int = typer.Option(0, "--max-depth", help="[ADD 2026-07-10] Max path depth (default 0=unlimited, 方豆 feedback '不限制depth')"),
    layout: str = typer.Option("LR", "--layout", "-l", help="Layout: LR (left-right, default) or TB (top-bottom)"),
    layout_engine: str = typer.Option("neato", "--layout-engine", help="Layout engine: neato (square, default) / dot / fdp"),
    dot_output: str = typer.Option(None, "--svg", "-d", help="Output SVG file"),
    png_output: str = typer.Option(None, "--png", help="Output PNG file (auto-call <engine> -Tpng)"),
    svg_output: str = typer.Option(None, "--svg-graphviz", help="Output SVG file (auto-call <engine> -Tsvg)"),
) -> None:
    """[Plan B+ 2026-07-08] 从 input 到 output 画 data path, 方形 layout.

    Use case: 方豆反馈 "深入到具体 module, 完整 input -> output 图, 尽可能方形".

    例子:
      # 手动指定 from/to
      sv_query visualize chain -f dot11_tx.v \\
        --from dot11_tx.phy_tx_start --to dot11_tx.result_i \\
        --layout LR --layout-engine neato --png /tmp/chain.png

      # Auto mode: 自动从 target module 的所有 input ports 找 path 到所有 output ports
      sv_query visualize chain -f dot11_tx.v \\
        --target dot11_tx --auto --max-edges 20 \\
        --layout LR --layout-engine neato --png /tmp/chain.png

    [Phase B 2026-07-17] --file/--filelist/--include via shared options.
    """
    from cli._common import handle_compilation_error
    from trace.core.compiler import CompilationError

    if not auto and (not from_signals or not to_signals):
        typer.echo("Error: need --from and --to, OR --auto with --target", err=True)
        raise typer.Exit(code=1)

    try:
        # [FIX 2026-07-17] Pass target_module to build_graph if provided.
        tracer, graph = build_viz_tracer(
            file=file, filelist=filelist, include=include,
            target_module=target if target else None,
        )
    except CompilationError as e:
        handle_compilation_error(e)
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
    # 到完整 hierarchy path. e.g. "bitreverse.i_clk" -> "openofdm_tx.dot11_tx.ifft64.revstage.i_clk"
    # 这样 chain 图能正确显示 sub-module 边界.
    mig = getattr(tracer, "_module_graph", None)
    hierarchy_map: dict[str, str] = {}  # flat_id -> full_hierarchy_id
    if mig is not None:
        # [FIX 2026-07-08] 2-level remap:
        # Level 1: port signals (inst_type.port_name) -> inst_path.port_name
        # Level 2: internal signals (inst_type.signal_name) -> inst_path.signal_name
        #   (e.g. "bitreverse.brmem" 是 bitreverse module 内部 wire, 不是 port)
        #   我们用 inst_type 模糊匹配: 任何 "<inst_type>.<signal_name>"
        #   重写到 "<inst_path>.<signal_name>"

        # Collect (module_type) -> [instance_id] for module-type -> instance mapping
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
            f"  Hierarchy remap: {len(hierarchy_map)} flat signals -> full path "
            f"(e.g. bitreverse.i_clk -> openofdm_tx.dot11_tx.ifft64.revstage.i_clk)",
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
        chain_edges: set = set()
        chain_nodes: set = set()
        sorted_paths = []
        # [V6.9] 即使没有数据路径, full-module anomaly scan 仍要运行
        # 路径构建失败时仍然检测 orphan_wire, unused_reg 等 RTL 问题
    else:
        # [FIX 2026-07-08] Sort paths by length DESCENDING (LONGEST first)
        # 这样优先选 multi-hop paths (有 intermediate nodes),
        # 不是 1-edge paths (只 input -> output, no intermediate).
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
                anomalies_extra[node_id] = "ORPHAN"
            elif n_in == 0:
                anomalies_extra[node_id] = "X_DRIVER"
            elif n_out == 0:
                anomalies_extra[node_id] = "DANGLING"

        # [FIX V6.9] Merge full-module scan results into anomalies
        if anomalies_extra:
            anomalies.update(anomalies_extra)

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
                "     ORPHAN=两端无连接 (悬空) | X_DRIVER=只出不进 (未定值) | DANGLING=只进不出 (死代码)",
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
    - 每条边标 [+M cycle] (src->dst 之间经过几个 reg)
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
            node.split(".", 1)[0] if "." in node else node
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
        lines.append('    style="rounded,dashed";')  # [FIX] 虚线边框, 不填背景
        lines.append(f'    color="{border_color}";')
        lines.append('    penwidth=2.5;')
        lines.append('    fontsize=14;')
        lines.append(f'    fontcolor="{border_color}";')  # [FIX] 跟边框同色
        lines.append('    fontname="Helvetica-Bold";')  # [FIX] 加粗 (必须 quote)
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
        lines.append('  }')

    # [FIX 2026-07-08] External sub-module cluster (e.g. bitreverse.i_clk 没 target prefix)
    # 放在独立 cluster 里, 用灰色虚线边框 + 灰色填充 (不跟正常 cluster 混淆)
    if external_nodes:
        lines.append('  subgraph "cluster_external" {')
        lines.append('    label="External sub-modules";')
        lines.append('    style="rounded,dashed";')
        lines.append('    color="#999999";')
        lines.append('    penwidth=2.0;')
        lines.append('    fontsize=12;')
        lines.append('    fontcolor="#666666";')
        lines.append('    fontname="Helvetica-Bold";')
        lines.append('    bgcolor="#f5f5f5";')  # 极浅灰背景区分
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
        lines.append('  }')

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
        {n for n in anomalies if n in nodes}
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
            # (之前不加限制 -> 100+ anomalies 时 DOT 有 40+ 边, 违反 max-edges=5 的预期)
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
