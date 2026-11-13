"""[P136.3] Candidate join: TB random field -> RTL snapshot signal.

This is deliberately a *candidate* join: the TB and RTL are separate
compilation domains, so a name match is evidence, not a proof.  The command
shows constraints from the TB side and all exact-leaf RTL candidates.
"""
from __future__ import annotations

from pathlib import Path

import typer

from cli._common import _build_tracer
from cli._output import emit_json
from cli.core.semantic.trace_common import _load_tracer_from_snapshot
from sv_query.trace.core.compiler import CompilationError
from cli._common import handle_compilation_error
from cli.core.semantic.constraints import constraint_dict




def _rtl_candidates(graph, leaf: str) -> list[dict]:
    rows = []
    for nid in graph.nodes():
        node = graph.get_node(nid)
        if node is None:
            continue
        suffix = nid.rsplit(".", 1)[-1]
        if node.name != leaf and suffix != leaf:
            continue
        rows.append({
            "signal": nid, "name": node.name, "kind": node.kind.name,
            "module": node.module, "file": node.file, "line": node.line,
            "reason": "name == field leaf" if node.name == leaf
                      else "id last segment == field leaf",
        })
    rows.sort(key=lambda x: (x["name"] != leaf, x["signal"]))
    return rows


def tb_join_cmd(
    field: str = typer.Argument(..., help="TB class property, e.g. i2c_item.nakok"),
    filelist: str = typer.Option(None, "--filelist", help="TB filelist (.f/.fl)"),
    file: Path = typer.Option(None, "--file", "-f", help="TB source file"),
    from_snapshot: str = typer.Option(
        ..., "--from-snapshot", help="RTL snapshot tag (required)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Candidate join from a TB random field to an RTL snapshot signal."""
    try:
        data = _join_payload(field, file, filelist, from_snapshot)
        if json_output:
            emit_json(data, pretty)
        else:
            _print_join(data["result"])
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except typer.BadParameter as e:
        _fail_join(str(e), json_output, pretty)
    except (ValueError, OSError) as e:
        _fail_join(f"snapshot error: {e}", json_output, pretty)


def _join_payload(field, file, filelist, from_snapshot) -> dict:
    tb = _build_tracer(file=file, filelist=filelist, log_level="ERROR")
    tb.build_graph()
    constraints = tb.trace_constraints(field)
    tb_graph = tb.get_graph()
    if tb_graph is None or tb_graph.get_node(field) is None:
        raise typer.BadParameter(f"TB field not found: {field}")
    leaf = field.rsplit(".", 1)[-1]
    rtl = _load_tracer_from_snapshot(from_snapshot)
    graph = rtl.get_graph()
    if graph is None:
        raise typer.BadParameter(f"snapshot graph missing: {from_snapshot}")
    candidates = _rtl_candidates(graph, leaf)
    status = ("single_candidate" if len(candidates) == 1
              else "multiple_candidates" if candidates else "not_found")
    return {
        "ok": True, "command": "trace_tb_join",
        "params": {"field": field, "from_snapshot": from_snapshot},
        "result": {
            "tb_field": field, "leaf": leaf,
            "constraints": [constraint_dict(c) for c in constraints],
            "join_status": status,
            "rtl_candidates": candidates,
            "note": "name-based candidate join; verify against driver/BFM/source",
        },
        "errors": [],
    }


def _print_join(result: dict) -> None:
    typer.echo(f"TB field: {result['tb_field']} "
               f"({len(result['constraints'])} constraint block(s))")
    typer.echo(f"Candidates: {len(result['rtl_candidates'])} "
               f"({result['join_status']})")
    for c in result["rtl_candidates"]:
        typer.echo(f"  {c['signal']} [{c['kind']}] {c['file']}:{c['line']}")


def _fail_join(message: str, json_output: bool, pretty: bool) -> None:
    data = {"ok": False, "command": "trace_tb_join", "error": message}
    if json_output:
        emit_json(data, pretty)
    else:
        typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1) from None
