"""[iter_335 / PLAN P39.1] waveform path lookup。

波形工具提供完整 RTL hier path；本命令严格映射到 graph canonical id：
- 不做模糊后缀解析（避免错误信号）；
- 支持 $root. 前缀/首尾空白；
- 位/切片无节点时回退父总线（显式 bit_parent）；
- 输出 aliases（port↔internal）和 suggestions（not_found）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from trace.core.compiler import CompilationError


def _norm_path(p: str) -> str:
    p = (p or "").strip()
    if p.startswith("$root."):
        p = p[len("$root."):]
    elif p.startswith("$root."):
        p = p[len("$root."):]
    return p


def _build_aliases(tracer, graph) -> dict[str, set[str]]:
    """canonical -> aliases（port/internal 等）。"""
    aliases = {n: {n} for n in graph.nodes()}
    try:
        mig = tracer.get_module_graph()
    except Exception:
        mig = None
    if mig is None:
        return aliases
    for inst_path, inst in sorted(getattr(mig, "instances", {}).items()):
        for port_name, port in sorted(getattr(inst, "ports", {}).items()):
            internal = getattr(port, "internal_signal", None)
            port_id = f"{inst_path}.{port_name}"
            if internal and internal in aliases:
                aliases[internal].add(port_id)
            if port_id in aliases and internal:
                aliases[port_id].add(internal)
    return aliases


def _lookup(graph, aliases, requested: str) -> dict:
    norm = _norm_path(requested)
    if norm in graph.nodes():
        canonical = norm
        res = "exact"
        bit_suffix = None
    else:
        canonical = None
        res = "not_found"
        bit_suffix = None
        m = re.match(r"^(.*)(\[[^\]]+\])$", norm)
        if m:
            base = m.group(1)
            if base in graph.nodes():
                canonical, res, bit_suffix = base, "bit_parent", m.group(2)
    if canonical is None:
        leaf = norm.split(".")[-1].split("[")[0]
        suggestions = sorted(n for n in graph.nodes()
                             if leaf and leaf in n)[:10]
        return {"requested": requested, "found": False, "canonical": None,
                "resolution": "not_found", "bit_suffix": None,
                "aliases": [], "suggestions": suggestions,
                "width": None, "kind": "", "module": ""}
    node = graph.get_node(canonical)
    return {
        "requested": requested,
        "found": True,
        "canonical": canonical,
        "resolution": res,
        "bit_suffix": bit_suffix,
        "aliases": sorted(aliases.get(canonical, {canonical})),
        "suggestions": [],
        "width": list(node.width) if node and node.width else None,
        "kind": getattr(getattr(node, "kind", None), "name", ""),
        "module": getattr(node, "module", "") if node else "",
    }


def _collect_paths(paths: list[str], paths_file: str | None) -> list[str]:
    out = list(paths or [])
    if paths_file:
        try:
            for line in Path(paths_file).read_text().splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    out.append(s)
        except OSError as e:
            raise ValueError(f"paths file not found: {paths_file}") from e
    seen = set()
    out = [p for p in out if not (p in seen or seen.add(p))]
    if not out:
        raise ValueError("no paths: use --path or --paths-file")
    return out


def lookup(
    path: list[str] = typer.Option([], "--path", help="full RTL hier path (repeatable)"),
    paths_file: str = typer.Option(None, "--paths-file", help="file with one full path per line"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """按完整 RTL hier path 严格映射到 canonical graph id。"""
    try:
        requested = _collect_paths(path, paths_file)
        tracer = _build_tracer(file=file, filelist=filelist, log_level=log_level)
        graph = tracer.build_graph()
        aliases = _build_aliases(tracer, graph)
        items = [_lookup(graph, aliases, p) for p in requested]
        failed = sum(1 for i in items if not i["found"])
        data = {
            "ok": True,
            "command": "trace_lookup",
            "params": {"paths": requested, "file": str(file) if file else None,
                       "filelist": filelist},
            "result": {"paths": items, "total": len(items), "found": len(items) - failed,
                       "failed": failed},
            "errors": [],
        }
        if json_output:
            emit_json(data, pretty)
        else:
            for item in items:
                if item["found"]:
                    print(f"{item['requested']} -> {item['canonical']} ({item['resolution']})")
                else:
                    print(f"{item['requested']} -> NOT FOUND")
                    for s in item["suggestions"][:5]:
                        print(f"  candidate: {s}")
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "trace_lookup", "error": str(e),
                "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}")
        raise typer.Exit(code=1) from None
