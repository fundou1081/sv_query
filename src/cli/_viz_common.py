"""Shared options and helpers for `sv_query visualize <cmd>` subcommands.

Phase B refactor (2026-07-17): collapse boilerplate across graph/dataflow/
pipeline/chain/module. Before this file:
  - 5 subcommands each defined --file/--filelist/--include/--strict independently
    (4–5 lines × 5 = ~25 lines of duplicated option declarations)
  - 5 subcommands each wrote the same `if not file and not filelist ... raise Exit`
    plus include_dirs split and CompilationError handling (~12 lines × 5 = ~60 lines)

After this file:
  - One source of truth for common options. Edit once, applies to all viz cmds.
  - One helper `build_viz_tracer()` that handles validation, includes split,
    CompilationError handling, and returns (tracer, graph, sources).

When adding a NEW subcommand (e.g. `visualize control-flow`):
    from cli._viz_common import (
        FILE_OPTION, FILELIST_OPTION, INCLUDE_OPTION, STRICT_OPTION,
        build_viz_tracer,
    )
    def controlflow(
        file: str = FILE_OPTION,
        filelist: str = FILELIST_OPTION,
        include: str = INCLUDE_OPTION,
        strict: bool = STRICT_OPTION,
        ...
    ):
        tracer, graph, sources = build_viz_tracer(file, filelist, include, strict)
        ...
"""
from pathlib import Path
from typing import Optional
import typer

from cli._common import _build_tracer


# ---------------------------------------------------------------------------
# Common typer option declarations. Import these instead of redefining.
# ---------------------------------------------------------------------------
FILE_OPTION = typer.Option(
    None, "--file", "-f",
    help="SystemVerilog source file (单文件模式)",
)
FILELIST_OPTION = typer.Option(
    None, "--filelist",
    help="Path to filelist (.f/.fl) for multi-file projects (项目模式)",
)
INCLUDE_OPTION = typer.Option(
    None, "--include", "-I",
    help="Include directory (comma-separated)",
)
STRICT_OPTION = typer.Option(
    True, "--strict/--no-strict",
    help="Strict mode (default): raise on elaboration error. Use --no-strict for partial AST.",
)
SHOW_SOURCE_OPTION = typer.Option(
    False, "--show-source",
    help="[V6.2 2026-07-20] Annotate each node with source file:line + clickable URL.",
)


# ---------------------------------------------------------------------------
# Common tracer build helper.
# ---------------------------------------------------------------------------
def build_viz_tracer(
    file: Optional[str],
    filelist: Optional[str],
    include: Optional[str],
    strict: bool,
    target_module: Optional[str] = None,
    use_cache: bool = False,
):
    """Build a tracer + graph for any visualize subcommand.

    Replaces ~12 lines of boilerplate that was duplicated across 5 subcommands:
        - Validates that exactly one of --file/--filelist is provided.
        - Splits --include comma-separated paths into a list.
        - Invokes _build_tracer and tracer.build_graph.
        - CompilationError propagates naturally — caller decides what to do
          (typer.Exit on strict, or partial-graph analysis on non-strict).

    Returns:
        (tracer, graph) — sources for SVA / Covergroup extractors are
        obtained from the tracer itself:
            - tracer._sources when --file was used (single-file content dict)
            - tracer._get_compiler()._sources when --filelist was used
              (compiler internally loads file contents)

    Raises:
        typer.Exit(code=1) when both --file and --filelist are missing.
    """
    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    include_dirs = include.split(",") if include else None
    file_path = Path(file) if file else None

    tracer = _build_tracer(
        file=file_path,
        filelist=filelist,
        strict=strict,
        include_dirs=include_dirs,
    )
    graph = tracer.build_graph(target_module=target_module, use_cache=use_cache)
    return tracer, graph


def get_viz_sources(tracer, file: Optional[str], filelist: Optional[str]) -> dict:
    """Return the sources dict for downstream SVA / Covergroup extractors.

    Single-file mode uses tracer._sources directly. Filelist mode needs to
    pull from the underlying compiler (its _sources is populated by the
    filelist loader). If the compiler hasn't been instantiated yet (rare,
    e.g. non-strict edge case), lazily build it.
    """
    if filelist:
        return tracer._get_compiler()._sources
    return tracer._sources


def format_source_annotation(node, show_source: bool = False) -> str:
    """[V6.2.1 2026-07-20] Render `file:line` suffix for a node, if available.

    Returns an empty string if `show_source` is False OR if the node has
    no file/line populated. Caller appends to the node label.

    Args:
        node: a TraceNode (must have .name, .file, .line attrs)
        show_source: when True, return formatted source annotation.

    Format: `<file>:<line>` if file is a string, else just `:line`.
    Falls back to empty string if no source is available.
    """
    if not show_source:
        return ""
    if not getattr(node, "file", "") or getattr(node, "line", 0) == 0:
        return ""
    file = node.file or ""
    line = node.line or 0
    # If file is just a basename, show full basename
    if "/" in file:
        file = file.rsplit("/", 1)[-1]
    return f"{file}:{line}"


def render_source_tooltip_and_url(node) -> str:
    """[V6.2.1 2026-07-20] Render the DOT tooltip + URL fragment for a node.

    Returns a string like ` tooltip="foo.sv:42" URL="foo.sv#42"` (with leading
    space), or empty string if node lacks source. Callers embed into DOT.

    The URL is editor-friendly: `code -g file.sv:42` opens at line 42 in VSCode.
    """
    file = getattr(node, "file", "") or ""
    line = getattr(node, "line", 0) or 0
    if not file or line == 0:
        return ""
    return f' tooltip="{file}:{line}" URL="{file}#{line}"'
