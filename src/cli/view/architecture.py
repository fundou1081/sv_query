"""Module/instance-level RTL architecture view (experimental).

This is deliberately not the retired full-signal/design graph: nodes are
instances, edges are real parent-net connections from MIG + CONNECTION edges.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from trace.core.compiler import CompilationError
from trace.core.query.architecture import build_architecture, to_dot

architecture_app = typer.Typer(help="Module/instance-level RTL architecture view")


def _to_dict(arch) -> dict:
    return {
        "nodes": [
            {"id": n.id, "module": n.module, "parent": n.parent,
             "depth": n.depth, "ports": n.ports}
            for n in arch.nodes
        ],
        "edges": [
            {"src": e.src, "dst": e.dst, "net": e.net,
             "src_port": e.src_port, "dst_port": e.dst_port,
             "src_direction": e.src_direction,
             "dst_direction": e.dst_direction}
            for e in arch.edges
        ],
        "boundaries": arch.boundaries,
        "stats": arch.stats,
    }


def _emit_output(arch, json_output: bool, pretty: bool, dot: Path | None,
                  svg: Path | None, include_boundaries: bool,
                  include_clock_reset: bool) -> None:
    if json_output:
        emit_json({"ok": True, "command": "architecture_graph",
                   "result": _to_dict(arch), "errors": []}, pretty)
    if not dot and not svg:
        if not json_output:
            typer.echo(to_dot(arch, include_boundaries=include_boundaries,
                              include_clock_reset=include_clock_reset), nl=False)
        return
    dot_src = to_dot(arch, include_boundaries=include_boundaries,
                     include_clock_reset=include_clock_reset)
    if dot:
        dot.write_text(dot_src)
    if svg:
        try:
            proc = subprocess.run(["dot", "-Tsvg"], input=dot_src,
                                  capture_output=True, text=True, check=True)
        except FileNotFoundError:
            raise ValueError("graphviz `dot` not found") from None
        svg.write_text(proc.stdout)
        if not json_output:
            typer.echo(f"wrote {svg} ({arch.stats})")


@architecture_app.command("graph")
def graph_cmd(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    module: str = typer.Option(None, "--module", "-m", help="root instance path"),
    depth: int = typer.Option(None, "--depth", "-d", help="max hierarchy depth"),
    include_primitives: bool = typer.Option(
        False, "--include-primitives",
        help="show prim_* leaf instances (default: block-level view)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    svg: Path = typer.Option(None, "--svg", help="write SVG via graphviz dot"),
    dot: Path = typer.Option(None, "--dot", help="write DOT source"),
    include_boundaries: bool = typer.Option(
        False, "--include-boundaries", help="draw external top-level ports"),
    include_clock_reset: bool = typer.Option(
        False, "--include-clock-reset", help="draw clk/rst edges (default hidden)"),
) -> None:
    """Build a module/instance architecture graph from real connections."""
    try:
        tracer = _build_tracer(file=file, filelist=filelist, log_level="ERROR")
        arch = build_architecture(tracer, root=module, max_depth=depth,
                                  include_primitives=include_primitives)
        _emit_output(arch, json_output, pretty, dot, svg,
                     include_boundaries, include_clock_reset)
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except ValueError as e:
        data = {"ok": False, "command": "architecture_graph", "error": str(e),
                "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
