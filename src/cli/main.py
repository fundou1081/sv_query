#==============================================================================
# main.py - CLI entry point
#============================================================================

import typer

from .commands.trace import trace_app
from .commands.diff import diff_app
from .commands.snapshot import snapshot_app

app = typer.Typer(
    name="svq",
    help="SystemVerilog signal tracer and graph diff tool",
    add_completion=False,
)

# 注册子命令组
app.add_typer(trace_app, name="trace")
app.add_typer(diff_app, name="diff")
app.add_typer(snapshot_app, name="snapshot")

# stats 是单独命令，不需要子 Typer
# 动态导入避免循环依赖
from .commands.stats import stats as stats_cmd


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