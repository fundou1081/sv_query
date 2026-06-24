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
    file: Optional[str] = typer.Option(None, "--file", "-f"),
    filelist: Optional[str] = typer.Option(None, "--filelist"),
    target: str = typer.Option("top", "--target", "-t"),
    depth: int = typer.Option(2, "--depth", "-d"),
    format: str = typer.Option("dot", "--format"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
    summary: bool = typer.Option(False, "--summary"),
):
    """[arch v1 2026-06-24] Default: 直接当 show 跑.

    如果传 --summary, 调用 summary 逻辑; 否则按 --format 输出.
    """
    if ctx.invoked_subcommand is not None:
        # subcommand was given, let it run
        return
    # 没有 subcommand, 把参数转发给 show
    show_args = {
        "file": file, "filelist": filelist, "target": target,
        "depth": depth, "output_format": "summary" if summary else format,
        "output": output, "with_ports": True, "strict": False, "include": None,
    }
    # typer 不允许 callback 调 subcommand, 用 sys.argv hack 不优雅;
    # 优雅方案: 如果没 subcommand, 调 _build + render 直接.
    if not file and not filelist:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    # 直接重演 show 逻辑 (避免重复实现)
    include_dirs = None
    instances, edges, _, _ = _build_arch_graph(
        file=file, filelist=filelist, target=target, depth=depth,
        include_dirs=include_dirs, strict=False,
    )
    if show_args["output_format"] == "summary":
        _print_summary(instances, edges, target, file, filelist)
        return
    if show_args["output_format"] == "dot":
        content = _render_dot(instances, edges, target, True)
    elif show_args["output_format"] == "mermaid":
        content = _render_mermaid(instances, edges, target, True)
    elif show_args["output_format"] == "html":
        content = _render_html(instances, edges, target, True)
    else:
        typer.echo(f"Error: unknown format '{show_args['output_format']}'", err=True)
        raise typer.Exit(1)
    if output:
        Path(output).write_text(content)
        typer.echo(f"✓ Wrote {show_args['output_format']} ({len(content)} bytes): {output}")
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
        try:
            edges = extract_module_edges_from_mig(mig, max_edges=500)
        except Exception:
            edges = []

    return instances, edges, mig, tracer


def _render_dot(instances, edges, target_module: str, with_ports: bool) -> str:
    """生成 DOT 格式 (Graphviz).

    跟 visualize module 输出兼容, 但简化 (不画 internal signals, 只画 module 框).
    """
    lines = [
        f"digraph arch_{target_module} {{",
        f"  rankdir=TB;",
        f"  splines=polyline;",
        f"  nodesep=0.4;",
        f"  ranksep=0.6;",
        f"  compound=true;",
        f"  labelloc=t;",
        f'  label="Architecture of {target_module} ({len(instances)} instances)";',
        f"",
        f"  // ---- Instances (L1) ----",
    ]

    # 节点
    for inst_id, inst_type, depth in instances:
        # 颜色按 depth 渐变
        color_palette = ["#4488cc", "#22aa55", "#dd8822", "#cc4466", "#7755aa"]
        color = color_palette[min(depth, len(color_palette) - 1)]
        # instance_id 可能含 . (层级), 取最后一段当 label
        short = inst_id.split(".")[-1] if "." in inst_id else inst_id
        lines.append(
            f'  "{inst_id}" [label="{short}\\n({inst_type})" '
            f'shape=box style="rounded,filled" fillcolor="{color}" '
            f'fontcolor="white" penwidth=1.5];'
        )

    # 父子边 (hierarchy)
    lines.append("")
    lines.append("  // ---- Hierarchy edges ----")
    for inst_id, _, _ in instances:
        # 父 = "." 前缀去掉最后一段
        if "." in inst_id:
            parent = ".".join(inst_id.split(".")[:-1])
            lines.append(f'  "{parent}" -> "{inst_id}" [style=dashed color="#999999"];')

    # 端口连接边 (L2)
    if with_ports and edges:
        lines.append("")
        lines.append(f"  // ---- Cross-module port connections (L2: {len(edges)} edges) ----")
        for e in edges[:50]:  # cap at 50 for readability
            src = e.get("src_instance", "")
            dst = e.get("dst_instance", "")
            port = e.get("port", "")
            if src and dst:
                lines.append(
                    f'  "{src}" -> "{dst}" [label="{port}" fontsize=9 color="#2266aa"];'
                )

    lines.append("}")
    return "\n".join(lines) + "\n"


def _render_mermaid(instances, edges, target_module: str, with_ports: bool) -> str:
    """生成 Mermaid 格式 (GitHub README 友好)."""
    lines = [
        f"```mermaid",
        f"graph TD",
        f"  %% Architecture of {target_module} ({len(instances)} instances)",
        f"",
        f"  %% Instances",
    ]

    # 节点 (用 last segment 当 id)
    node_ids = {}  # inst_id → safe_mermaid_id
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
        print(f"   Possible causes:")
        print(f"   - File has no submodule instantiation (e.g. flat RTL)")
        print(f"   - Filelist missing required packages (check warnings)")
        print(f"   - Wrong target module name")
        return

    # 按 type 分组
    from collections import Counter
    type_counts = Counter(inst_type for _, inst_type, _ in instances)
    top_types = type_counts.most_common(5)

    print(f"📐 Project Architecture: {target_module}")
    print(f"=" * 60)
    print(f"Source: {file or filelist}")
    print()
    print(f"Total instances:  {n}")
    print(f"Hierarchy depth:  {max((d for _, _, d in instances), default=0)} levels")
    print(f"Port connections: {n_edges} (cross-module)")
    print()
    print(f"Top module types (by instance count):")
    for t, c in top_types:
        bar = "█" * min(c, 30)
        print(f"  {t:40s}  {c:3d}  {bar}")
    print()
    if edges:
        # 找最常见的 port 连接
        from collections import Counter
        port_counts = Counter(e.get("port", "") for e in edges)
        top_ports = port_counts.most_common(5)
        print(f"Most common port connections:")
        for p, c in top_ports:
            if p:
                print(f"  {p:30s}  {c:3d}")
    print()
    print(f"💡 Tip:")
    print(f"  - Use --format dot to generate Graphviz diagram")
    print(f"  - Use --format mermaid for GitHub README")
    print(f"  - Use --format html for interactive visualization")


@arch_app.command(name="show")
def show(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: Optional[str] = typer.Option(None, "--filelist", help="Path to filelist for multi-file projects"),
    include: Optional[str] = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    target: str = typer.Option("top", "--target", "-t", help="Target module name (default: top)"),
    depth: int = typer.Option(2, "--depth", "-d", help="Hierarchy depth (default: 2)"),
    with_ports: bool = typer.Option(True, "--with-ports/--no-ports", help="Show cross-module port connections (default ON)"),
    output_format: str = typer.Option("dot", "--format", help="Output format: dot / mermaid / html / summary"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write to file (default: stdout)"),
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
        content = _render_dot(instances, edges, target, with_ports)
    elif output_format == "mermaid":
        content = _render_mermaid(instances, edges, target, with_ports)
    elif output_format == "html":
        content = _render_html(instances, edges, target, with_ports)
    else:
        typer.echo(f"Error: unknown format '{output_format}' (use: dot/mermaid/html/summary)", err=True)
        raise typer.Exit(1)

    # Step 3: 输出
    if output:
        Path(output).write_text(content)
        typer.echo(f"✓ Wrote {output_format} ({len(content)} bytes): {output}")
    else:
        typer.echo(content)


if __name__ == "__main__":
    typer.run(arch_app)