#==============================================================================
# arch.py - 项目架构可视化命令
#
# Usage:
#   python run_cli.py arch -f top.sv                              # 架构概览 (DOT 默认)
#   python run_cli.py arch -f top.sv --depth 3                   # 限制层级
#   python run_cli.py arch -f top.sv --summary                    # 一段话描述
#   python run_cli.py arch -f top.sv --format mermaid            # Mermaid 输出
#   python run_cli.py arch -f top.sv --format html               # 交互式 HTML
#   python run_cli.py arch -f top.sv --with-ports                # 显示跨 module 端口连接
#   python run_cli.py arch --filelist=project.f -t top -d 3      # 多文件项目
#
# 设计: 复用 ModuleInstanceGraph (MIG) L1 + extract_module_edges_from_mig L2,
#        跟 visualize module 同源, 但 arch 更聚焦"项目架构 overview"而非"单 module 内部".
#==============================================================================
"""
arch.py - Project architecture visualization.

[arch v1 2026-06-24] 命令设计目标:
  - 让新人 30 秒看懂项目架构 (模块层次 + 端口连接)
  - 输出 DOT/Mermaid/HTML, 适合贴 README 或本地查看
  - --summary 模式生成项目架构描述 (一段话)

架构图内容:
  - L1: Module 抽取 (1 box = 1 submodule instance)
  - L2: 跨 module 端口连接 (instance-to-instance port edges)
  - Hierarchy: cluster 嵌套 (按 wrapper 分组)

跟 visualize module 区别:
  - visualize module: 详尽 (cluster + port edges + internal signals)
  - arch: 简洁 (默认 depth=2, 突出 hierarchy + 关键 port edges)
"""
import sys
from pathlib import Path
from typing import Optional

import typer

from src.cli._common import _build_tracer

arch_app = typer.Typer(help="Project architecture visualization (L1 + L2 overview)")


@arch_app.callback(invoke_without_command=True)
def _arch_default(
    ctx: typer.Context,
    file: str | None = typer.Option(None, "--file", "-f"),
    filelist: str | None = typer.Option(None, "--filelist"),
    target: str = typer.Option("top", "--target", "-t"),
    depth: int = typer.Option(2, "--depth", "-d"),
    format: str = typer.Option("dot", "--format"),
    output: str | None = typer.Option(None, "--output", "-o"),
    summary: bool = typer.Option(False, "--summary"),
    cluster_by_type: bool = typer.Option(False, "--cluster-by-type"),
    max_nodes: int = typer.Option(100, "--max-nodes"),
    max_port_edges: int = typer.Option(200, "--max-port-edges"),
):
    """[arch v1 2026-06-24, v2 2026-06-25] Default: 直接当 show 跑.

    如果传 --summary, 调用 summary 逻辑; 否则按 --format 输出.
    """
    if ctx.invoked_subcommand is not None:
        # subcommand was given, let it run
        return
    if not file and not filelist:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    # 直接重演 show 逻辑 (避免重复实现)
    include_dirs = None
    instances, edges, _, _ = _build_arch_graph(
        file=file, filelist=filelist, target=target, depth=depth,
        include_dirs=include_dirs, strict=False,
    )
    output_format = "summary" if summary else format
    if output_format == "summary":
        _print_summary(instances, edges, target, file, filelist)
        return
    if output_format == "dot":
        content = _render_dot(instances, edges, target, True,
                              cluster_by_type=cluster_by_type, max_nodes=max_nodes,
                              max_port_edges=max_port_edges)
    elif output_format == "mermaid":
        content = _render_mermaid(instances, edges, target, True)
    elif output_format == "html":
        content = _render_html(instances, edges, target, True)
    elif output_format == "svg":
        dot_text = _render_dot(instances, edges, target, True,
                               cluster_by_type=cluster_by_type, max_nodes=max_nodes)
        try:
            content = _render_svg(dot_text, target, output)
        except RuntimeError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
    else:
        typer.echo(f"Error: unknown format '{output_format}'", err=True)
        raise typer.Exit(1)
    if output:
        Path(output).write_text(content)
        typer.echo(f"✓ Wrote {output_format} ({len(content)} bytes): {output}")
    else:
        typer.echo(content)


def _build_arch_graph(file, filelist, target, depth, include_dirs, strict):
    """共用: 跑 tracer + 抽 MIG + 抽 L2 端口边.

    返回: (instances, edges, mig, tracer) 或 raise.
    """
    from trace.core.module_extractor import (
        extract_module,
        extract_module_edges_from_mig,
    )
    from trace.core.semantic_adapter import SemanticAdapter

    try:
        if filelist:
            tracer = _build_tracer(
                filelist=filelist,
                include_dirs=include_dirs,
                strict=strict,
            )
        else:
            with open(file) as f:
                sources = {file: f.read()}
            tracer = _build_tracer(
                file=Path(file),
                include_dirs=include_dirs,
                strict=strict,
            )
    except Exception as e:
        typer.echo(f"Error building tracer: {e}", err=True)
        raise typer.Exit(1)

    tracer.build_graph()
    semantic_adapter = SemanticAdapter(tracer._get_compiler().get_root())

    # L1: Module 抽取
    try:
        result = extract_module(semantic_adapter, target, max_depth=depth)
    except Exception as e:
        typer.echo(f"Error extracting module: {e}", err=True)
        raise typer.Exit(1)

    instances = [(i.id, i.def_name, i.depth) for i in result.instances]

    # L2: 跨 module 端口连接
    edges = []
    mig = getattr(tracer, "_module_graph", None)
    if mig is not None:
        # [Bug fix 2026-06-25] MIG port_to_internal 用 pyslang 的
        # hierarchicalPath, 起点是第一个 top instance (e.g. ariane).
        # 但 extract_module 用 user-specified target (e.g. cva6).
        # 两者 prefix 不一致 → edges 0. Rewrite MIG port_to_internal keys+values
        # 用 target 替换 top-level prefix + 剥掉 wrapper 层 (e.g. i_cva6).
        # 同时 rewrite extract_module 返回的 inst IDs 以对齐.
        pti = getattr(mig, "port_to_internal", {})
        if pti:
            top_prefixes = set()
            for k in pti:
                top_prefixes.add(k.split(".", 1)[0])
            top_prefixes.add(target)

            # Pass 1: replace top-level prefix (e.g. ariane.* → cva6.*).
            pass1 = {}
            for k, v in pti.items():
                def replace_top(p: str) -> str:
                    if not p:
                        return p
                    for tp in top_prefixes:
                        if tp == target:
                            continue
                        if p == tp:
                            return target
                        if p.startswith(tp + "."):
                            return target + p[len(tp):]
                    return p
                pass1[replace_top(k)] = replace_top(v)

            # Pass 2: detect wrapper layer after Pass 1. Look for "<target>.<one_seg>.<rest>"
            # patterns and identify "<one_seg>" segments that are dense AND whose "rest"
            # parts overlap with extract_module's inst IDs. Strip them.
            wrapper_candidates = {}
            for k in pass1:
                parts = k.split(".")
                if len(parts) >= 3 and parts[0] == target:
                    mid = parts[1]
                    rest = ".".join(parts[2:])
                    wrapper_candidates.setdefault(mid, []).append(rest)
            # Wrapper segment = frequent (≥ 10 occurrences)
            wrappers = [mid for mid, rests in wrapper_candidates.items() if len(rests) >= 10]

            def rewrite_path(p: str) -> str:
                if not p:
                    return p
                parts = p.split(".")
                if (
                    len(parts) >= 3
                    and parts[0] == target
                    and parts[1] in wrappers
                ):
                    p = target + "." + ".".join(parts[2:])
                return p

            new_pti = {rewrite_path(k): rewrite_path(v) for k, v in pass1.items()}
            mig.port_to_internal = new_pti
            itp = getattr(mig, "internal_to_port", {})
            if itp:
                mig.internal_to_port = {rewrite_path(k): rewrite_path(v) for k, v in itp.items()}
            if wrappers:
                print(
                    f"[sv_query] namespace rewrite: stripped wrappers {wrappers} "
                    f"to align MIG with extract_module's '{target}.*' namespace",
                    file=sys.stderr,
                )

            # [Bug fix 2026-06-25] extract_module 返回的 inst IDs 也含 wrapper segment
            # (e.g. darksocv.bridge0.core0), rewrite 后变成 darksocv.core0 跟 MIG keys
            # 对齐. 不 rewrite 会导致 inst_port_to_inst 匹配不上 → edges=0.
            if wrappers:
                import dataclasses
                rewritten_instances = []
                any_rewritten = False
                for inst in result.instances:
                    new_id = rewrite_path(inst.id)
                    if new_id != inst.id:
                        rewritten_instances.append(dataclasses.replace(inst, id=new_id))
                        any_rewritten = True
                    else:
                        rewritten_instances.append(inst)
                if any_rewritten:
                    result = dataclasses.replace(result, instances=rewritten_instances)
                    # Also rewrite the public 'instances' list (used by render pipeline)
                    instances = [(i.id, i.def_name, i.depth) for i in rewritten_instances]
        try:
            edges = extract_module_edges_from_mig(
                mig, instances=result.instances, max_edges=500,
            )
        except Exception as e:
            import traceback
            print(f"DEBUG: extract_module_edges_from_mig fail: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            edges = []

    return instances, edges, mig, tracer


def _hash_color(name: str) -> str:
    """[v2 2026-06-25] Hash-based color for module type name.

    相同 type 同色 → 同一 type 的 instance 一眼可见.
    Returns: hex color string like "#4488cc".
    """
    import hashlib
    h = hashlib.md5(name.encode()).hexdigest()
    # 用 hash 前 6 位作为颜色 (限制亮度避免太暗/太亮)
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    # 限制亮度: 任一分量 < 80 时 +50 提亮 (避免太暗看不清字)
    r = max(r, 80) if r + g + b < 350 else r
    g = max(g, 80) if r + g + b < 350 else g
    b = max(b, 80) if r + g + b < 350 else b
    return f"#{r:02x}{g:02x}{b:02x}"


def _collapse_instances(instances, max_nodes: int) -> tuple[list, str | None]:
    """[v2 2026-06-25] 限制 nodes 数. 超出折叠成 <N more ...> placeholder.

    Returns: (visible_instances, placeholder_note) 或 (instances, None).
    Strategy: 按 type 计数, 保留最常见的 max_nodes 个 type 的第一个 instance,
              其他折叠成 note.
    """
    if len(instances) <= max_nodes:
        return instances, None
    from collections import Counter, defaultdict
    type_counts = Counter(t for _, t, _ in instances)
    # 保留 top-K types (K = max_nodes)
    top_types = set(t for t, _ in type_counts.most_common(max_nodes))
    visible = []
    collapsed = []
    for inst_id, inst_type, depth in instances:
        if inst_type in top_types and not any(v[1] == inst_type for v in visible):
            # 保留 top type 的第一个 instance
            visible.append((inst_id, inst_type, depth))
        else:
            collapsed.append((inst_id, inst_type, depth))
    if not collapsed:
        return visible, None
    collapsed_counts = Counter(t for _, t, _ in collapsed)
    note = (
        f"<FONT POINT-SIZE=\"11\" COLOR=\"#888888\"><I>"
        f"Showing {len(visible)} of {len(instances)} instances "
        f"(use --max-nodes to adjust, {len(collapsed_counts)} types collapsed: "
        f"{', '.join(t for t, _ in collapsed_counts.most_common(3))}"
        f"{'...' if len(collapsed_counts) > 3 else ''})"
        f"</I></FONT>"
    )
    return visible, note


def _safe_cluster_name(name: str) -> str:
    """[v2 2026-06-25] 安全 cluster 名 (DOT id 不能含 -).

    'axi_master_xbar' → 'cluster_axi_master_xbar'
    """
    return "cluster_" + name.replace("-", "_").replace(".", "_")


def _render_dot(
    instances, edges, target_module: str, with_ports: bool,
    cluster_by_type: bool = False, max_nodes: int = 100,
    max_port_edges: int = 200,
) -> str:
    """生成 DOT 格式 (Graphviz).

    v1: depth palette + flat nodes.
    v2 (--cluster-by-type): same-type instances 合并到 cluster + 同色.
    v2 (--max-nodes N): 超出折叠 + note.

    跟 visualize module 输出兼容, 但简化 (不画 internal signals, 只画 module 框).
    """
    # 应用 max_nodes 限制
    visible_instances, collapse_note = _collapse_instances(instances, max_nodes)
    n_hidden = len(instances) - len(visible_instances)

    lines = [
        f"digraph arch_{target_module} {{",
        "  rankdir=TB;",
        "  splines=polyline;",
        "  nodesep=0.4;",
        "  ranksep=0.6;",
        "  compound=true;",
        "  labelloc=t;",
    ]
    # 标题
    title = f"Architecture of {target_module} ({len(instances)} instances"
    if n_hidden > 0:
        title += f", showing {len(visible_instances)}"
    title += ")"
    lines.append(f'  label="{title}";')
    lines.append("")
    lines.append("  // ---- Instances (L1) ----")

    # 按 cluster_by_type 决定是否分组
    if cluster_by_type:
        from collections import defaultdict
        type_to_instances = defaultdict(list)
        for inst_id, inst_type, depth in visible_instances:
            type_to_instances[inst_type].append((inst_id, depth))

        # 每个 type 一个 cluster
        for inst_type, members in sorted(type_to_instances.items()):
            color = _hash_color(inst_type)
            safe_name = _safe_cluster_name(inst_type)
            lines.append(f'  subgraph "{safe_name}" {{')
            lines.append(f'    label="{inst_type}";')
            lines.append('    style="rounded,filled";')
            lines.append(f'    fillcolor="{color}33";')  # alpha (low opacity)
            lines.append(f'    color="{color}";')
            lines.append('    penwidth=2;')
            lines.append(f'    fontcolor="{color}";')
            lines.append('    fontsize=11;')
            for inst_id, depth in members:
                short = inst_id.split(".")[-1] if "." in inst_id else inst_id
                # node fill 用同色 (不透明), 让 cluster bg 透出来
                lines.append(
                    f'    "{inst_id}" [label="{short}" '
                    f'shape=box style="rounded,filled" fillcolor="{color}" '
                    f'fontcolor="white" penwidth=1];'
                )
            lines.append("  }")
    else:
        # v1 behavior: depth palette, flat
        for inst_id, inst_type, depth in visible_instances:
            color_palette = ["#4488cc", "#22aa55", "#dd8822", "#cc4466", "#7755aa"]
            color = color_palette[min(depth, len(color_palette) - 1)]
            short = inst_id.split(".")[-1] if "." in inst_id else inst_id
            lines.append(
                f'  "{inst_id}" [label="{short}\\n({inst_type})" '
                f'shape=box style="rounded,filled" fillcolor="{color}" '
                f'fontcolor="white" penwidth=1.5];'
            )

    # 父子边 (hierarchy)
    lines.append("")
    lines.append("  // ---- Hierarchy edges ----")
    visible_ids = set(inst_id for inst_id, _, _ in visible_instances)
    for inst_id, _, _ in visible_instances:
        if "." in inst_id:
            parent = ".".join(inst_id.split(".")[:-1])
            # parent 必须在 visible 或当前处理 (top 自身)
            if parent in visible_ids or parent == target_module:
                lines.append(f'  "{parent}" -> "{inst_id}" [style=dashed color="#999999"];')

    # 端口连接边 (L2)
    if with_ports and edges:
        lines.append("")
        lines.append(f"  // ---- Cross-module port connections (L2: {len(edges)} edges) ----")
        for e in edges[:max_port_edges]:  # cap for readability (default 200, was 50)
            src = e.get("src_instance", "")
            dst = e.get("dst_instance", "")
            port = e.get("port", "")
            if src and dst and src in visible_ids and dst in visible_ids:
                lines.append(
                    f'  "{src}" -> "{dst}" [label="{port}" fontsize=9 color="#2266aa"];'
                )

    # 添加 collapse note (用 labelloc=t 的扩展)
    if collapse_note:
        lines.append("")
        lines.append("  // ---- Collapse note ----")
        lines.append(f'  note [label=<{collapse_note}> shape=plaintext];')

    lines.append("}")
    return "\n".join(lines) + "\n"


def _render_mermaid(instances, edges, target_module: str, with_ports: bool) -> str:
    """生成 Mermaid 格式 (GitHub README 友好)."""
    lines = [
        "```mermaid",
        "graph TD",
        f"  %% Architecture of {target_module} ({len(instances)} instances)",
        "",
        "  %% Instances",
    ]

    # 节点 (用 last segment 当 id)
    # [FIX 2026-07-06] 加入 root node (target_module) 当 hierarchy 起点.
    # 之前只有 sub-instance nodes, 而 root (parent of top-level instances) 不在 node_ids 里,
    # 导致 hierarchy edges 从不 emit (parent 在 node_ids 中找不到).
    node_ids = {}  # inst_id or target_module → safe_mermaid_id
    node_ids[target_module] = "n_root"
    lines.append(f'  n_root["{target_module}<br/>(root)"]')
    for i, (inst_id, inst_type, _) in enumerate(instances):
        safe_id = f"n{i}"
        node_ids[inst_id] = safe_id
        short = inst_id.split(".")[-1] if "." in inst_id else inst_id
        lines.append(f'  {safe_id}["{short}<br/>({inst_type})"]')

    # 父子边
    lines.append("")
    lines.append("  %% Hierarchy")
    for inst_id, _, _ in instances:
        if "." in inst_id:
            parent = ".".join(inst_id.split(".")[:-1])
            # [FIX 2026-07-06] 加 or parent == target_module 跟 dot render 一致
            if parent in node_ids:
                lines.append(f"  {node_ids[parent]} -.-> {node_ids[inst_id]}")

    # 端口连接边
    if with_ports and edges:
        lines.append("")
        lines.append(f"  %% Cross-module port connections ({len(edges)} edges)")
        for e in edges[:50]:
            src = e.get("src_instance", "")
            dst = e.get("dst_instance", "")
            port = e.get("port", "")
            if src in node_ids and dst in node_ids:
                # 用 port 当 edge label
                port_clean = port.replace('"', "'") if port else ""
                lines.append(
                    f"  {node_ids[src]} -->|{port_clean}| {node_ids[dst]}"
                )

    lines.append("```")
    return "\n".join(lines) + "\n"


def _render_svg(dot_text: str, target_module: str, output: str | None) -> str:
    """[v2 2026-06-25] 调用 graphviz `dot -Tsvg` 生成 SVG.

    Returns SVG text. 如果 graphviz 没装, raise RuntimeError.
    """
    import shutil
    import subprocess
    import tempfile

    dot_bin = shutil.which("dot")
    if dot_bin is None:
        raise RuntimeError(
            "graphviz 'dot' not found. Install with: brew install graphviz"
        )

    # 写临时 DOT 文件 (graphviz 需要 file path, 也能 stdin)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as f:
        f.write(dot_text)
        tmp_dot = f.name

    try:
        # 调 dot -Tsvg
        result = subprocess.run(
            [dot_bin, "-Tsvg", tmp_dot],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"graphviz failed: {result.stderr[:300]}")
        return result.stdout
    finally:
        try:
            Path(tmp_dot).unlink()
        except Exception:
            pass


def _render_html(instances, edges, target_module: str, with_ports: bool) -> str:
    """生成交互式 HTML (用 vis.js 渲染)."""
    # 把 nodes + edges 转成 vis.js 数据
    import json

    vis_nodes = []
    for i, (inst_id, inst_type, depth) in enumerate(instances):
        color_palette = ["#4488cc", "#22aa55", "#dd8822", "#cc4466", "#7755aa"]
        color = color_palette[min(depth, len(color_palette) - 1)]
        short = inst_id.split(".")[-1] if "." in inst_id else inst_id
        vis_nodes.append({
            "id": inst_id,
            "label": f"{short}\n({inst_type})",
            "color": {"background": color, "border": "#222222"},
            "font": {"color": "white", "size": 14},
            "shape": "box",
            "margin": 10,
        })

    vis_edges = []
    for inst_id, _, _ in instances:
        if "." in inst_id:
            parent = ".".join(inst_id.split(".")[:-1])
            vis_edges.append({
                "from": parent,
                "to": inst_id,
                "arrows": "to",
                "dashes": True,
                "color": {"color": "#999999"},
                "physics": False,
            })
    if with_ports and edges:
        for e in edges[:100]:
            src = e.get("src_instance", "")
            dst = e.get("dst_instance", "")
            port = e.get("port", "")
            if src and dst:
                vis_edges.append({
                    "from": src,
                    "to": dst,
                    "label": port,
                    "arrows": "to",
                    "color": {"color": "#2266aa"},
                    "font": {"size": 9, "align": "middle"},
                })

    nodes_json = json.dumps(vis_nodes, indent=2)
    edges_json = json.dumps(vis_edges, indent=2)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Architecture: {target_module}</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
#header {{ background: #222; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
#header h1 {{ margin: 0 0 10px 0; font-size: 22px; }}
#header .stats {{ font-size: 13px; color: #aaa; }}
#network {{ width: 100%; height: 700px; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.legend {{ background: white; padding: 15px; border-radius: 8px; margin-top: 20px; font-size: 13px; }}
.legend span {{ display: inline-block; padding: 4px 10px; margin-right: 10px; border-radius: 4px; color: white; }}
</style>
</head>
<body>
<div id="header">
  <h1>📐 Architecture: {target_module}</h1>
  <div class="stats">
    {len(instances)} instances &nbsp;|&nbsp;
    {len(edges)} port connections &nbsp;|&nbsp;
    Generated by sv_query arch v1
  </div>
</div>
<div id="network"></div>
<div class="legend">
  <strong>Legend (depth → color):</strong><br>
  <span style="background: #4488cc">Depth 0 (root)</span>
  <span style="background: #22aa55">Depth 1</span>
  <span style="background: #dd8822">Depth 2</span>
  <span style="background: #cc4466">Depth 3</span>
  <span style="background: #7755aa">Depth 4+</span>
  <br><br>
  <em>Solid arrows: cross-module port connections. Dashed: hierarchy (parent→child).</em>
</div>
<script>
var nodes = new vis.DataSet({nodes_json});
var edges = new vis.DataSet({edges_json});
var container = document.getElementById('network');
var data = {{ nodes: nodes, edges: edges }};
var options = {{
  layout: {{
    hierarchical: {{
      direction: 'UD',
      sortMethod: 'directed',
      levelSeparation: 120,
      nodeSpacing: 150,
    }}
  }},
  physics: false,
  interaction: {{ hover: true, tooltipDelay: 100 }},
  nodes: {{ borderWidth: 2 }},
  edges: {{ smooth: {{ type: 'cubicBezier' }} }},
}};
var network = new vis.Network(container, data, options);
</script>
</body>
</html>
"""


def _print_summary(instances, edges, target_module: str, file: str | None, filelist: str | None) -> None:
    """--summary 模式: 一段话描述项目架构."""
    n = len(instances)
    n_edges = len(edges)
    if n == 0:
        print(f"⚠️  No submodule instances found under '{target_module}'.")
        print("   Possible causes:")
        print("   - File has no submodule instantiation (e.g. flat RTL)")
        print("   - Filelist missing required packages (check warnings)")
        print("   - Wrong target module name")
        return

    # 按 type 分组
    from collections import Counter
    type_counts = Counter(inst_type for _, inst_type, _ in instances)
    top_types = type_counts.most_common(5)

    print(f"📐 Project Architecture: {target_module}")
    print("=" * 60)
    print(f"Source: {file or filelist}")
    print()
    print(f"Total instances:  {n}")
    print(f"Hierarchy depth:  {max((d for _, _, d in instances), default=0)} levels")
    print(f"Port connections: {n_edges} (cross-module)")
    print()
    print("Top module types (by instance count):")
    for t, c in top_types:
        bar = "█" * min(c, 30)
        print(f"  {t:40s}  {c:3d}  {bar}")
    print()
    if edges:
        # 找最常见的 port 连接
        from collections import Counter
        port_counts = Counter(e.get("port", "") for e in edges)
        top_ports = port_counts.most_common(5)
        print("Most common port connections:")
        for p, c in top_ports:
            if p:
                print(f"  {p:30s}  {c:3d}")
    print()
    print("💡 Tip:")
    print("  - Use --format dot to generate Graphviz diagram")
    print("  - Use --format mermaid for GitHub README")
    print("  - Use --format html for interactive visualization")


@arch_app.command(name="show")
def show(
    file: str | None = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str | None = typer.Option(None, "--filelist", help="Path to filelist for multi-file projects"),
    include: str | None = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    target: str = typer.Option("top", "--target", "-t", help="Target module name (default: top)"),
    depth: int = typer.Option(2, "--depth", "-d", help="Hierarchy depth (default: 2)"),
    with_ports: bool = typer.Option(True, "--with-ports/--no-ports", help="Show cross-module port connections (default ON)"),
    output_format: str = typer.Option("dot", "--format", help="Output format: dot / mermaid / html / svg / summary"),
    output: str | None = typer.Option(None, "--output", "-o", help="Write to file (default: stdout)"),
    cluster_by_type: bool = typer.Option(False, "--cluster-by-type", help="[v2] Group same-type instances into clusters + hash-colored"),
    max_nodes: int = typer.Option(100, "--max-nodes", help="[v2] Maximum nodes to render (default: 100). Excess collapsed with note."),
    strict: bool = typer.Option(False, "--strict/--no-strict"),
):
    """[arch v1 2026-06-24] 项目架构可视化 (L1 hierarchy + L2 cross-module port edges).

    输出格式:
      - dot     Graphviz DOT 格式 (默认), 用 `dot -Tpng arch.dot > arch.png` 渲染
      - mermaid Mermaid 格式, 贴 GitHub README 直接渲染
      - html    交互式 HTML (vis.js), 浏览器打开
      - summary 一段话描述项目架构

    例子:
      python run_cli.py arch -f sim/openTitan_validation.sv --format summary
      python run_cli.py arch --filelist=picorv32.f -t picorv32 -d 2 --format mermaid
      python run_cli.py arch -f top.sv --format html -o arch.html
    """
    if not file and not filelist:
        typer.echo("Error: need --file or --filelist", err=True)
        raise typer.Exit(1)

    include_dirs = include.split(",") if include else None

    # Step 1: 抽取架构
    instances, edges, mig, tracer = _build_arch_graph(
        file=file,
        filelist=filelist,
        target=target,
        depth=depth,
        include_dirs=include_dirs,
        strict=strict,
    )

    # Step 2: 渲染
    if output_format == "summary":
        _print_summary(instances, edges, target, file, filelist)
        return

    if output_format == "dot":
        content = _render_dot(instances, edges, target, with_ports,
                              cluster_by_type=cluster_by_type, max_nodes=max_nodes)
    elif output_format == "mermaid":
        content = _render_mermaid(instances, edges, target, with_ports)
    elif output_format == "html":
        content = _render_html(instances, edges, target, with_ports)
    elif output_format == "svg":
        # SVG: 先 render DOT (with cluster/max-nodes), 再调 graphviz
        dot_text = _render_dot(instances, edges, target, with_ports,
                               cluster_by_type=cluster_by_type, max_nodes=max_nodes)
        try:
            content = _render_svg(dot_text, target, output)
        except RuntimeError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
    else:
        typer.echo(f"Error: unknown format '{output_format}' (use: dot/mermaid/html/svg/summary)", err=True)
        raise typer.Exit(1)

    # Step 3: 输出
    if output:
        Path(output).write_text(content)
        typer.echo(f"✓ Wrote {output_format} ({len(content)} bytes): {output}")
    else:
        typer.echo(content)


if __name__ == "__main__":
    typer.run(arch_app)
