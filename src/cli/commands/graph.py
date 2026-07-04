# ==============================================================================
# graph.py - graph inspection subcommands
# ============================================================================

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.unified_tracer import UnifiedTracer


def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


graph_app = typer.Typer(help="[EXPERIMENTAL] Inspect signal graph")


@graph_app.command("dump")
def dump(
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    module: str | None = typer.Option(None, "--module", "-m", help="Filter by module name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Dump the signal graph as JSON"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        nodes = []
        for nid in graph.nodes():
            node = graph.get_node(nid)
            if node:
                if module and node.module != module:
                    continue
                nodes.append(
                    {
                        "id": nid,
                        "name": node.name,
                        "kind": node.kind.name if hasattr(node.kind, "name") else str(node.kind),
                        "module": node.module,
                        "width": node.width,
                        "expression": node.expression,
                        "operands": node.operands,
                        "signals": node.signals,
                        "function_name": node.function_name,
                        "condition": node.condition,
                        "true_branch": node.true_branch,
                        "false_branch": node.false_branch,
                    }
                )

        edges = []
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge:
                edges.append(
                    {
                        "src": src,
                        "dst": dst,
                        "kind": edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind),
                        "condition": edge.condition,
                        "function_return": edge.function_return,
                    }
                )

        data = {
            "ok": True,
            "command": "graph_dump",
            "params": {"file": str(file), "module": module},
            "result": {
                "nodes": nodes,
                "edges": edges,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            print(f"Graph dump: {len(nodes)} nodes, {len(edges)} edges")
            if pretty:
                output_json(data, pretty)
            else:
                print(f"Nodes: {[n['id'] for n in nodes[:20]]}{'...' if len(nodes) > 20 else ''}")
                edge_strs = [f"{e['src']}->{e['dst']}" for e in edges[:20]]
                print(f"Edges: {edge_strs}{'...' if len(edges) > 20 else ''}")

    except Exception as e:
        data = {"ok": False, "command": "graph_dump", "error": str(e)}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@graph_app.command("nodes")
def list_nodes(
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    kind: str | None = typer.Option(None, "--kind", "-k", help="Filter by node kind (SIGNAL, EXPRESSION, etc)"),
    module: str | None = typer.Option(None, "--module", "-m", help="Filter by module name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """List all nodes in the graph"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        nodes = []
        for nid in graph.nodes():
            node = graph.get_node(nid)
            if node:
                node_kind = node.kind.name if hasattr(node.kind, "name") else str(node.kind)

                if kind and node_kind != kind:
                    continue
                if module and node.module != module:
                    continue

                nodes.append(
                    {
                        "id": nid,
                        "name": node.name,
                        "kind": node_kind,
                        "module": node.module,
                    }
                )

        data = {
            "ok": True,
            "command": "list_nodes",
            "params": {"file": str(file), "kind": kind, "module": module},
            "result": {"nodes": nodes, "total": len(nodes)},
            "errors": [],
        }

        if json_output:
            output_json(data)
        else:
            print(f"Nodes ({len(nodes)}):")
            for n in nodes:
                print(f"  [{n['kind']}] {n['id']} ({n['module']})")

    except Exception as e:
        data = {"ok": False, "command": "list_nodes", "error": str(e)}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@graph_app.command("edges")
def list_edges(
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    kind: str | None = typer.Option(None, "--kind", "-k", help="Filter by edge kind (DRIVER, etc)"),
    src: str | None = typer.Option(None, "--src", "-s", help="Filter by source node"),
    dst: str | None = typer.Option(None, "--dst", "-d", help="Filter by destination node"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """List all edges in the graph"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        edges = []
        for e_src, e_dst in graph.edges():
            edge = graph.get_edge(e_src, e_dst)
            if edge:
                edge_kind = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)

                if kind and edge_kind != kind:
                    continue
                if src and e_src != src:
                    continue
                if dst and e_dst != dst:
                    continue

                edges.append(
                    {
                        "src": e_src,
                        "dst": e_dst,
                        "kind": edge_kind,
                    }
                )

        data = {
            "ok": True,
            "command": "list_edges",
            "params": {"file": str(file), "kind": kind, "src": src, "dst": dst},
            "result": {"edges": edges, "total": len(edges)},
            "errors": [],
        }

        if json_output:
            output_json(data)
        else:
            print(f"Edges ({len(edges)}):")
            for e in edges:
                print(f"  {e['src']} → {e['dst']} ({e['kind']})")

    except Exception as e:
        data = {"ok": False, "command": "list_edges", "error": str(e)}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@graph_app.command("find")
def find(
    pattern: str = typer.Argument(..., help="Pattern to search (partial match)"),
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """Find nodes matching a pattern"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        matches = []
        for nid in graph.nodes():
            if pattern.lower() in nid.lower():
                node = graph.get_node(nid)
                if node:
                    matches.append(
                        {
                            "id": nid,
                            "name": node.name,
                            "kind": node.kind.name if hasattr(node.kind, "name") else str(node.kind),
                            "module": node.module,
                        }
                    )

        data = {
            "ok": True,
            "command": "find",
            "params": {"pattern": pattern, "file": str(file)},
            "result": {"matches": matches, "total": len(matches)},
            "errors": [],
        }

        if json_output:
            output_json(data)
        else:
            print(f"Found {len(matches)} matches for '{pattern}':")
            for m in matches:
                print(f"  [{m['kind']}] {m['id']} ({m['module']})")

    except Exception as e:
        data = {"ok": False, "command": "find", "error": str(e)}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None
