"""[iter_365 / PLAN P63.2] constraint 语义查询。

约束是声明式关系（CONSTRAINS/HAS_*），不是数据流；本命令只委托
ConstraintTracer，不进入 fanin。
"""
from __future__ import annotations

from pathlib import Path

import sys

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from cli.core.semantic.trace_common import resolve_signal
from trace.core.compiler import CompilationError


def constraint_dict(info, graph=None, *, id_key: str = "block") -> dict:
    """Single canonical constraint-block serialization for all CLI views."""
    rand_vars = []
    if graph is not None:
        for var in info.vars:
            node = graph.get_node(var)
            if node is not None and (node.extra or {}).get("rand"):
                rand_vars.append(var)
    return {
        id_key: info.block_id,
        "vars": list(info.vars),
        "conditions": list(info.conditions),
        "expr_count": info.expr_count,
        "defined_in": info.defined_in,
        "inherited": info.inherited,
        "rand_vars": rand_vars,
        "solve_before": list(getattr(info, "solve_before", []) or []),
        "dist": list(getattr(info, "dist", []) or []),
    }


def _constraint_dict(info, graph) -> dict:
    return constraint_dict(info, graph)


def _relative_hint(property: str, graph) -> dict:
    """[P76] 相对 class property -> 可行动提示。"""
    suffix = "." + property
    matches = [n for n in graph.nodes() if n.endswith(suffix)]
    if matches:
        return {
            "hint": "相对名已匹配到实例级候选；请用 canonical id",
            "suggestions": sorted(matches)[:5],
        }
    return {
        "hint": (
            "class-relative property is not a graph id; use an instance-level "
            "canonical id (e.g. top.e.p.addr) or a type-level id (packet.addr). "
            "Discover instances with `svq class <type> --relations` / "
            "`svq class <type> --member <name>`."
        ),
        "suggestions": [f"class <type> --member {property.rsplit('.', 1)[-1]}"],
    }


def _query(tracer, graph, property: str):
    r = resolve_signal(graph, property)
    if r.get("ok") and r.get("resolved") in graph:
        resolved = r["resolved"]
    else:
        # 实例成员节点可能未建 (未被 RTL 使用)；ConstraintTracer 仍可按
        # 实例前缀 + class 类型解析。无约束则仍是 not_found。
        if not tracer.trace_constraints(property):
            raise ValueError(f"property {property!r} not_found")
        resolved = property
    return resolved, [_constraint_dict(x, graph)
                       for x in tracer.trace_constraints(resolved)]


def _print_constraints(resolved: str, items: list[dict]) -> None:
    print(f"Constraints for {resolved} ({len(items)}):")
    for item in items:
        print(f"  {item['block']} vars={item['vars']} "
              f"conditions={item['conditions']} exprs={item['expr_count']}")


def constraints_cmd(
    property: str = typer.Argument(..., help="packet.addr / top.e.p.addr"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """属性受哪些 constraint 约束（类型级/实例级；不走数据流）。"""
    try:
        tracer = _build_tracer(file=file, filelist=filelist)
        graph = tracer.build_graph()
        resolved, items = _query(tracer, graph, property)
        data = {
            "ok": True,
            "command": "trace_constraints",
            "params": {"file": str(file) if file else None, "filelist": filelist,
                       "property": property},
            "result": {"property": property, "resolved": resolved,
                       "count": len(items), "constraints": items},
            "errors": [],
        }
        if json_output:
            emit_json(data, pretty)
        else:
            _print_constraints(resolved, items)
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except ValueError as e:
        hint = _relative_hint(property, tracer.get_graph())
        data = {"ok": False, "command": "trace_constraints", "error": str(e),
                "errors": [str(e)], **hint}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}", file=sys.stderr)
            print(f"Hint: {hint['hint']}", file=sys.stderr)
        raise typer.Exit(code=1) from None
    except Exception as e:
        data = {"ok": False, "command": "trace_constraints", "error": str(e),
                "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


def _neighborhood_error(exc: Exception, json_output: bool, pretty: bool) -> None:
    data = {"ok": False, "command": "trace_constraint_neighborhood",
            "error": str(exc), "errors": [str(exc)]}
    if json_output:
        emit_json(data, pretty)
    else:
        print(f"Error: {exc}", file=sys.stderr)
    raise typer.Exit(code=1) from None


def _run_neighborhood(property: str, file, filelist, max_depth: int,
                      max_nodes: int) -> dict:
    from trace.core.query.constraint import ConstraintTracer

    if max_depth < 1 or max_nodes < 1:
        raise ValueError("--max-depth and --max-nodes must be >= 1")
    tracer = _build_tracer(file=file, filelist=filelist)
    graph = tracer.build_graph()
    resolved = property
    r = resolve_signal(graph, property)
    if r.get("ok") and r.get("resolved") in graph:
        resolved = r["resolved"]
    result = ConstraintTracer(
        graph, tracer.get_class_hierarchy()
    ).trace_neighborhood(resolved, max_depth=max_depth, max_nodes=max_nodes)
    if result is None:
        raise ValueError(f"property {property!r} not_found")
    return result


def _print_neighborhood(result: dict) -> None:
    summary = result["summary"]
    print(f"Constraint neighborhood for {result['root']} "
          f"({summary['node_count']} vars / {summary['relation_count']} relations):")
    for node in result["nodes"]:
        print(f"  {node['id']} depth={node['depth']} "
              f"degree={node['degree']} blocks={node['block_count']}")


def constraint_neighborhood_cmd(
    property: str = typer.Argument(..., help="packet.addr / top.e.p.addr"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    max_depth: int = typer.Option(6, "--max-depth", help="max BFS depth"),
    max_nodes: int = typer.Option(200, "--max-nodes", help="max variables"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """One-shot cross-block constraint neighborhood around a random variable."""
    try:
        result = _run_neighborhood(property, file, filelist, max_depth, max_nodes)
        data = {
            "ok": True,
            "command": "trace_constraint_neighborhood",
            "params": {"file": str(file) if file else None, "filelist": filelist,
                       "property": property, "max_depth": max_depth,
                       "max_nodes": max_nodes},
            "result": result,
            "errors": [],
        }
        if json_output:
            emit_json(data, pretty)
        else:
            _print_neighborhood(result)
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        _neighborhood_error(e, json_output, pretty)


def _run_constraint_chain(source: str, target: str, file, filelist,
                          max_depth: int, max_nodes: int) -> dict:
    from trace.core.query.constraint import ConstraintTracer

    if max_depth < 1 or max_nodes < 1:
        raise ValueError("--max-depth and --max-nodes must be >= 1")
    tracer = _build_tracer(file=file, filelist=filelist)
    graph = tracer.build_graph()
    result = ConstraintTracer(graph, tracer.get_class_hierarchy()).trace_chain(
        source, target, max_depth=max_depth, max_nodes=max_nodes)
    if result.get("reason") == "endpoint_not_found":
        raise ValueError(f"constraint endpoint not found: {source!r} or {target!r}")
    return result


def _print_constraint_chain(result: dict) -> None:
    if not result.get("found"):
        print(f"No constraint chain: {result.get('reason')}")
        return
    print(f"Constraint chain {result['source']} -> {result['target']} "
          f"({result['hop_count']} hops):")
    for item in result["chain"]:
        if item["kind"] == "variable":
            print(f"  var {item['id']}")
        else:
            print(f"  block {item['id']} via {item['via']}")


def constraint_chain_cmd(
    source: str = typer.Argument(..., help="random property (type/instance)"),
    target: str = typer.Argument(..., help="random property (type/instance)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    max_depth: int = typer.Option(6, "--max-depth"),
    max_nodes: int = typer.Option(200, "--max-nodes"),
    json_output: bool = typer.Option(False, "--json", "-j"),
    pretty: bool = typer.Option(False, "--pretty", "-p"),
) -> None:
    """Random variable -> random variable constraint chain (co-membership)."""
    try:
        result = _run_constraint_chain(source, target, file, filelist,
                                       max_depth, max_nodes)
        data = {"ok": True, "command": "trace_constraint_chain",
                "params": {"source": source, "target": target,
                           "max_depth": max_depth, "max_nodes": max_nodes},
                "result": result, "errors": []}
        if json_output:
            emit_json(data, pretty)
        else:
            _print_constraint_chain(result)
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "trace_constraint_chain",
                "error": str(e), "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None
