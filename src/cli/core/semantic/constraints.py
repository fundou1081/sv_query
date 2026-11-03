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


def _constraint_dict(info, graph) -> dict:
    rand_vars = []
    for var in info.vars:
        node = graph.get_node(var)
        if node is not None and (node.extra or {}).get("rand"):
            rand_vars.append(var)
    return {
        "block": info.block_id,
        "vars": list(info.vars),
        "conditions": list(info.conditions),
        "expr_count": info.expr_count,
        "defined_in": info.defined_in,
        "inherited": info.inherited,
        "rand_vars": rand_vars,
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
    except Exception as e:
        data = {"ok": False, "command": "trace_constraints", "error": str(e),
                "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None
