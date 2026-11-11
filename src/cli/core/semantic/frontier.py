"""trace frontier: generic structural boundary probes for agent tracing."""
from __future__ import annotations

from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from cli.core.semantic.trace_common import resolve_signal, _load_tracer_from_snapshot
from trace.core.compiler import CompilationError
from trace.core.query.frontier import analyze_frontier


def _frontier_payload(signal, direction, max_depth, max_frontier, max_visits,
                      file, filelist, from_snapshot) -> dict:
    if direction not in {"fanin", "fanout", "both"}:
        raise ValueError("--direction must be fanin | fanout | both")
    if from_snapshot and (file or filelist):
        raise ValueError("--from-snapshot is mutually exclusive with --file/--filelist")
    tracer = (_load_tracer_from_snapshot(from_snapshot)
              if from_snapshot else _build_tracer(
                  file=file, filelist=filelist, log_level="ERROR"))
    graph = tracer.get_graph() or tracer.build_graph()
    r = resolve_signal(graph, signal)
    if not r.get("ok") or r.get("resolved") not in graph:
        raise ValueError(f"signal {signal!r} not found")
    suffix = f" --from-snapshot {from_snapshot}" if from_snapshot else ""
    return analyze_frontier(graph, r["resolved"], direction=direction,
                            max_depth=max_depth, max_frontier=max_frontier,
                            max_visits=max_visits, probe_suffix=suffix)


def _print_frontier(result: dict) -> None:
    print(f"Frontier for {result['signal']} ({result['summary']['frontier_count']}):")
    for row in result["frontier"]:
        print(f"  [{row['direction']}] {row['node']} "
              f"reason={row['reason']} instance={row['instance']}")
        for probe in row["next_probes"]:
            print(f"    probe: {probe}")


def frontier_cmd(
    signal: str = typer.Argument(..., help="canonical signal id"),
    direction: str = typer.Option("both", "--direction", "-d",
                                  help="fanin | fanout | both"),
    max_depth: int = typer.Option(8, "--max-depth"),
    max_frontier: int = typer.Option(50, "--max-frontier"),
    max_visits: int = typer.Option(2000, "--max-visits",
                                   help="max visited nodes per frontier walk (P158.11)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    from_snapshot: str = typer.Option(None, "--from-snapshot"),
    json_output: bool = typer.Option(False, "--json", "-j"),
    pretty: bool = typer.Option(False, "--pretty", "-p"),
) -> None:
    """Report where a structural trace stops and what to query next."""
    try:
        result = _frontier_payload(signal, direction, max_depth, max_frontier,
                                   max_visits, file, filelist, from_snapshot)
        data = {"ok": True, "command": "trace_frontier",
                "params": {"direction": direction, "max_depth": max_depth,
                           "max_frontier": max_frontier, "max_visits": max_visits},
                "result": result, "errors": []}
        if json_output:
            emit_json(data, pretty)
        else:
            _print_frontier(result)
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except ValueError as e:
        data = {"ok": False, "command": "trace_frontier", "error": str(e)}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
