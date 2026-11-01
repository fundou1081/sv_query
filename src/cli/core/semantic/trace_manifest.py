"""[iter_341 / PLAN P41.2] waveform manifest：完整 path → canonical + profile。

波形工具一次拿全：路径解析、bit/type/clock/reset/sequential/source。
只读；批量 build 一次。
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from cli.core.semantic.trace_lookup import _build_aliases, _collect_paths, _lookup
from cli.core.semantic.trace_profile import (
    _build_stage_index, _build_type_lookup, _profile_signal,
)
from trace.core.compiler import CompilationError
from trace.core.trace_evidence import TraceEvidenceResolver


def manifest(
    path: list[str] = typer.Option([], "--path", help="full RTL hier path (repeatable)"),
    paths_file: str = typer.Option(None, "--paths-file", help="file with one full path per line"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """批量 waveform manifest：path → canonical + profile。"""
    try:
        requested = _collect_paths(path, paths_file)
        tracer = _build_tracer(file=file, filelist=filelist, log_level=log_level)
        graph = tracer.build_graph()
        aliases = _build_aliases(tracer, graph)
        try:
            adapter = tracer._get_adapter()
            evidence_resolver = TraceEvidenceResolver(graph=graph, adapter=adapter)
            type_lookup = _build_type_lookup(adapter)
        except Exception:
            adapter = None
            evidence_resolver = None
            type_lookup = None
        stage_index = _build_stage_index(graph)
        entries = []
        errors = []
        for i, p in enumerate(requested):
            lk = _lookup(graph, aliases, p)
            if not lk["found"]:
                entries.append({"waveform_path": p, "index": i,
                                "found": False, "lookup": lk, "profile": None})
                continue
            try:
                prof = _profile_signal(tracer, graph, p, evidence_resolver,
                                       type_lookup, adapter, stage_index)
                entries.append({"waveform_path": p, "index": i,
                                "found": True, "lookup": lk, "profile": prof})
            except Exception as e:
                errors.append({"waveform_path": p, "index": i, "error": str(e)})
                entries.append({"waveform_path": p, "index": i,
                                "found": False, "lookup": lk, "profile": None,
                                "error": str(e)})
        failed = sum(1 for e in entries if not e["found"])
        data = {
            "ok": True,
            "command": "trace_manifest",
            "params": {"paths": requested, "file": str(file) if file else None,
                       "filelist": filelist},
            "result": {"entries": entries, "total": len(entries),
                       "found": len(entries) - failed, "failed": failed},
            "errors": errors,
        }
        if json_output:
            emit_json(data, pretty)
        else:
            for e in entries:
                print(f"{e['waveform_path']} -> {e['lookup'].get('canonical')}")
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "trace_manifest", "error": str(e),
                "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}")
        raise typer.Exit(code=1) from None
