#==============================================================================
# main.py - CLI entry point
#==============================================================================
"""
Usage:
  python -m cli.main dataflow --help
  python src/cli/main.py dataflow --help
"""

import sys
from pathlib import Path

# 设置 sys.path - 允许直接运行或作为模块运行
# 找到 src/ 目录的父目录并添加到 path
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent  # src/cli/
_project_root = _src_dir.parent.parent  # 项目根目录

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import typer

from src.cli.commands.trace import trace_app
from src.cli.commands.diff import diff_app
from src.cli.commands.snapshot import snapshot_app
from src.cli.commands.dataflow import dataflow_app
from src.cli.commands.controlflow import controlflow_app
from src.cli.commands.risk import risk_app
from src.cli.commands.sva import sva_app
from src.cli.commands.timing import timing_app
from src.cli.commands.cdc import cdc_app

app = typer.Typer(
    name="svq",
    help="SystemVerilog signal tracer and graph diff tool",
    add_completion=False,
)

# 注册子命令组
app.add_typer(trace_app, name="trace")
app.add_typer(diff_app, name="diff")
app.add_typer(snapshot_app, name="snapshot")
app.add_typer(dataflow_app, name="dataflow")
app.add_typer(controlflow_app, name="controlflow")
app.add_typer(risk_app, name="risk")
app.add_typer(sva_app, name="sva")
app.add_typer(timing_app, name="timing")
app.add_typer(cdc_app, name="cdc")

# stats 是单独命令，不需要子 Typer
# 动态导入避免循环依赖
from src.cli.commands.stats import stats as stats_cmd


def stats_callback(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Show graph statistics"""
    if file:
        from trace.unified_tracer import UnifiedTracer

        with open(file) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={file: source})
        graph = tracer.build_graph()
        
        nodes_count = {}
        for n in graph.nodes():
            node = graph.get_node(n)
            if node:
                kind = node.kind.name if hasattr(node.kind, 'name') else str(node.kind)
                nodes_count[kind] = nodes_count.get(kind, 0) + 1
        
        edges_count = {}
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge:
                kind = edge.kind.name if hasattr(edge.kind, 'name') else str(edge.kind)
                edges_count[kind] = edges_count.get(kind, 0) + 1
        
        modules = list(graph.modules) if hasattr(graph, 'modules') else []
        
        data = {
            "ok": True,
            "command": "stats",
            "params": {"file": file},
            "result": {
                "total_nodes": len(graph.nodes()),
                "total_edges": len(graph.edges()),
                "nodes": nodes_count,
                "edges": edges_count,
                "modules": modules,
            },
            "errors": []
        }
        
        if json_output:
            import json as json_mod
            indent = 2 if pretty else None
            print(json_mod.dumps(data, indent=indent, ensure_ascii=False))
        else:
            print("=== Graph Statistics ===")
            print(f"  Total nodes: {len(graph.nodes())}")
            print(f"  Total edges: {len(graph.edges())}")
            print(f"\n  Node kinds:")
            for kind, count in nodes_count.items():
                print(f"    {kind}: {count}")
            print(f"\n  Edge kinds:")
            for kind, count in edges_count.items():
                print(f"    {kind}: {count}")
            print(f"\n  Modules ({len(modules)}):")
            for m in modules[:10]:
                print(f"    - {m}")
    else:
        typer.echo("Error: --file is required", err=True)
        raise typer.Exit(code=1)


# 注册 stats 为独立命令
app.command(name="stats", help="Show graph statistics")(stats_callback)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """SystemVerilog signal tracer and graph diff tool"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()