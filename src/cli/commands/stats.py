#==============================================================================
# stats.py - graph statistics command
#============================================================================

import sys
import json
from pathlib import Path

import typer
import pyslang

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.unified_tracer import UnifiedTracer


def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict) -> None:
    """纯文本输出"""
    result = data.get("result", {})
    nodes = result.get("nodes", {})
    edges = result.get("edges", {})
    modules = result.get("modules", [])

    print("=== Graph Statistics ===")
    print(f"  Total nodes: {result.get('total_nodes', 0)}")
    print(f"  Total edges: {result.get('total_edges', 0)}")

    print(f"\n  Node kinds:")
    for kind, count in nodes.items():
        print(f"    {kind}: {count}")

    print(f"\n  Edge kinds:")
    for kind, count in edges.items():
        print(f"    {kind}: {count}")

    print(f"\n  Modules ({len(modules)}):")
    for m in modules[:10]:
        print(f"    - {m}")
    if len(modules) > 10:
        print(f"    ... and {len(modules) - 10} more")


def stats(
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Show graph statistics"""
    try:
        tree = pyslang.SyntaxTree.fromFile(str(file))
        tracer = UnifiedTracer(trees={str(file): tree})
        graph = tracer.build_graph()

        # 转换 NodeKind/EdgeKind enum 为字符串
        nodes = {}
        for n in graph.nodes():
            node = graph.get_node(n)
            if node:
                kind = node.kind.name if hasattr(node.kind, 'name') else str(node.kind)
                nodes[kind] = nodes.get(kind, 0) + 1

        edges = {}
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge:
                kind = edge.kind.name if hasattr(edge.kind, 'name') else str(edge.kind)
                edges[kind] = edges.get(kind, 0) + 1

        # 获取模块列表
        modules = list(graph.modules) if hasattr(graph, 'modules') else []

        data = {
            "ok": True,
            "command": "stats",
            "params": {"file": str(file)},
            "result": {
                "total_nodes": len(graph.nodes()),
                "total_edges": len(graph.edges()),
                "nodes": nodes,
                "edges": edges,
                "modules": modules,
            },
            "errors": []
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {
            "ok": False,
            "command": "stats",
            "error": str(e),
            "errors": [str(e)]
        }
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1)