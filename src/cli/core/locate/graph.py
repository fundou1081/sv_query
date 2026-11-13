# ==============================================================================
# graph.py - graph inspection subcommands
# ============================================================================

import sys
from pathlib import Path

import typer

from cli._paths import ensure_on_path, PROJECT_ROOT  # noqa: E402
ensure_on_path(PROJECT_ROOT)

from cli._common import _build_tracer, handle_compilation_error  # [iter_236 1a]
from cli.core.semantic.trace_common import resolve_signal  # [iter_362 P60]
from sv_query.trace.core.query.subgraph import SubgraphError, SubgraphOptions, build_subgraph  # [iter_362 P60]
from sv_query.trace.core.compiler import CompilationError
from cli._output import emit_json


graph_app = typer.Typer(help="Inspect signal graph")


@graph_app.command("nodes")
def list_nodes(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="[iter_236 1a] filelist (.f/.fl) 多文件项目"),
    kind: str | None = typer.Option(None, "--kind", "-k", help="Filter by node kind (SIGNAL, EXPRESSION, etc)"),
    module: str | None = typer.Option(None, "--module", "-m", help="Filter by module name"),
    match: str | None = typer.Option(None, "--match", help="[iter_249] 只保留 id 含该子串的节点 "
                                                  "(原 `graph find`, 大小写不敏感)"),
    detail: bool = typer.Option(False, "--detail", help="[iter_249] 附带表达式/条件等富字段 "
                                                       "(原 `graph dump` 的节点部分)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """列图节点 (可按 kind/module/子串过滤; --detail 给富字段)。

    [iter_249 T2] 合并原 `graph find` (`--match`) 与 `graph dump` 的节点视图 (`--detail`);
    整图导出请用 `graph nodes --detail --json` + `graph edges --json`。
    """
    try:
        tracer = _build_tracer(file=file, filelist=filelist)
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
                if match and match.lower() not in nid.lower():
                    continue

                item = {
                    "id": nid,
                    "name": node.name,
                    "kind": node_kind,
                    "module": node.module,
                }
                if detail:
                    # TraceNode 无这些属性 —— 都在 node.extra 里 (原 dump 的做法)
                    extra = node.extra if hasattr(node, "extra") else {}
                    item.update({
                        "width": node.width,
                        "expression": extra.get("expression", ""),
                        "operands": extra.get("operands", []),
                        "signals": extra.get("signals", []),
                        "function_name": extra.get("function_name", ""),
                        "condition": extra.get("condition", ""),
                        "true_branch": extra.get("true_branch", ""),
                        "false_branch": extra.get("false_branch", ""),
                    })
                nodes.append(item)

        data = {
            "ok": True,
            "command": "list_nodes",
            "params": {"file": str(file) if file else None, "filelist": filelist,
                       "kind": kind, "module": module, "match": match, "detail": detail},
            "result": {"nodes": nodes, "total": len(nodes)},
            "errors": [],
        }

        if json_output:
            emit_json(data)
        else:
            print(f"Nodes ({len(nodes)}):")
            for n in nodes:
                print(f"  [{n['kind']}] {n['id']} ({n['module']})")

    except CompilationError as e:
        handle_compilation_error(e)
        return
    except Exception as e:
        data = {"ok": False, "command": "list_nodes", "error": str(e)}
        if json_output:
            emit_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@graph_app.command("edges")
def list_edges(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="[iter_236 1a] filelist (.f/.fl) 多文件项目"),
    kind: str | None = typer.Option(None, "--kind", "-k", help="Filter by edge kind (DRIVER, etc)"),
    src: str | None = typer.Option(None, "--src", "-s", help="Filter by source node"),
    dst: str | None = typer.Option(None, "--dst", "-d", help="Filter by destination node"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """List all edges in the graph"""
    try:
        tracer = _build_tracer(file=file, filelist=filelist)
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
            "params": {"file": str(file) if file else None, "filelist": filelist, "kind": kind, "src": src, "dst": dst},
            "result": {"edges": edges, "total": len(edges)},
            "errors": [],
        }

        if json_output:
            emit_json(data)
        else:
            print(f"Edges ({len(edges)}):")
            for e in edges:
                print(f"  {e['src']} → {e['dst']} ({e['kind']})")

    except CompilationError as e:
        handle_compilation_error(e)
        return
    except Exception as e:
        data = {"ok": False, "command": "list_edges", "error": str(e)}
        if json_output:
            emit_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


def _resolve_subgraph_seeds(graph, seeds):
    rows = []
    valid = []
    errors = []
    for raw in seeds:
        r = resolve_signal(graph, raw)
        rows.append({
            "requested": raw,
            "resolved": r.get("resolved"),
            "status": r.get("status"),
        })
        if r.get("ok") and r.get("resolved") in graph:
            valid.append(r["resolved"])
        else:
            errors.append({
                "requested": raw,
                "status": r.get("status"),
                "candidates": r.get("candidates", []),
                "suggestions": r.get("suggestions", []),
            })
    return valid, rows, errors


def _emit_subgraph_failure(message: str, json_output: bool) -> None:
    data = {"ok": False, "command": "graph_subgraph",
            "error": message, "errors": [message]}
    if json_output:
        emit_json(data)
    else:
        print(f"Error: {message}", file=sys.stderr)


def _print_subgraph(result: dict) -> None:
    print(f"Subgraph: {len(result['nodes'])} nodes, "
          f"{len(result['edges'])} edges")
    print(f"  boundary: {len(result['boundary'])}, "
          f"truncated: {result['truncated']}")
    for n in result["nodes"]:
        print(f"  [{n['kind']}] {n['id']} ({n['module']})")


@graph_app.command("subgraph")
def subgraph_cmd(
    seeds: list[str] = typer.Argument(..., help="Canonical/relative seed signal(s)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) 多文件项目"),
    depth: int = typer.Option(2, "--depth", help="k-hop depth (0 = seeds only)"),
    direction: str = typer.Option("both", "--direction", help="in / out / both (relative to seeds)"),
    edge_kinds: str = typer.Option("driver,connection", "--edge-kinds",
                                   help="comma list: driver,connection,control,clock,reset,bit_select,member_select,branch"),
    max_nodes: int = typer.Option(80, "--max-nodes", help="hard node budget (includes seeds)"),
    max_edges: int = typer.Option(160, "--max-edges", help="hard edge budget"),
    evidence: bool = typer.Option(False, "--evidence", help="include file:line evidence"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
) -> None:
    """局部子图：从 seed 出发的 k-hop 邻域（有预算，不做全图 BFS）。"""
    try:
        tracer = _build_tracer(file=file, filelist=filelist)
        graph = tracer.build_graph()
        valid, seed_rows, seed_errors = _resolve_subgraph_seeds(graph, seeds)
        if not valid:
            data = {
                "ok": False,
                "command": "graph_subgraph",
                "error": "no resolvable seed",
                "seeds": seed_rows,
                "errors": seed_errors,
            }
            if json_output:
                emit_json(data)
            else:
                print(f"Error: no resolvable seed: {seed_errors}", file=sys.stderr)
            raise typer.Exit(code=1)

        opts = SubgraphOptions(
            depth=depth,
            direction=direction,
            edge_kinds=tuple(edge_kinds.split(",")),
            max_nodes=max_nodes,
            max_edges=max_edges,
            include_evidence=evidence,
        )
        result = build_subgraph(graph, valid, options=opts)
        data = {
            "ok": True,
            "command": "graph_subgraph",
            "params": {
                "file": str(file) if file else None,
                "filelist": filelist,
                "depth": depth,
                "direction": direction,
                "edge_kinds": list(opts.edge_kinds),
                "max_nodes": max_nodes,
                "max_edges": max_edges,
                "evidence": evidence,
            },
            "seeds": seed_rows,
            "result": result,
            "errors": seed_errors,
        }
        if json_output:
            emit_json(data)
        else:
            _print_subgraph(result)
    except typer.Exit:
        raise
    except SubgraphError as e:
        _emit_subgraph_failure(str(e), json_output)
        raise typer.Exit(code=1) from None
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        _emit_subgraph_failure(str(e), json_output)
        raise typer.Exit(code=1) from None
