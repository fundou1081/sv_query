"""
core/semantic/paths.py — [iter_237] 跨模块路径查询 (`svq paths <src> <dst>`)

与 `dataflow analyze` 的分工:
  - `dataflow analyze`: 工程语境下的源→目标路径分析 (边语义/条件/风险)
  - `paths`          : **图上的路径枚举**, 含**跨模块端口映射跳转**
                       (进模块 top.u.a→sub.a; 出模块 sub.y→top.u.y)

数据源: `PathResolver` (SignalGraph + ModuleInstanceGraph)。
[iter_237] 同时修了 PathResolver 的跨模块缺陷 (旧实现只"进模块"不"出模块" → 跨模块路径恒为 None)。
"""
from __future__ import annotations

from pathlib import Path

import typer

from cli.core.semantic._common import build_tracer, emit, fail


def paths_cmd(
    src: str = typer.Argument(..., help="起点信号 id (如 inst_demo.in_a)"),
    dst: str = typer.Argument(..., help="终点信号 id (如 inst_demo.add_out)"),
    all_paths: bool = typer.Option(False, "--all", "-a", help="枚举全部简单路径 (默认只给一条)"),
    max_paths: int = typer.Option(50, "--max", "-n", help="--all 时的路径数上限"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """图上从 src 到 dst 的路径 (跨模块端口可跳转)。

    例: svq paths inst_demo.in_a inst_demo.add_out --filelist project.f --json
    """
    tracer = build_tracer(file, filelist, log_level)
    if tracer is None:
        return

    resolver = tracer.get_path_resolver()
    if resolver is None:
        fail("path resolver unavailable (graph not built?)", json_output, pretty)

    graph = tracer.get_graph()
    known = set(graph.nodes()) if graph is not None else set()
    unknown = [x for x in (src, dst) if x not in known]
    if unknown:
        fail("signal id not found in graph", json_output, pretty, unknown=unknown,
             hint="用 `svq graph nodes --json` 列出可用 id")

    if all_paths:
        found = resolver.find_all_paths(src, dst, max_paths=max_paths)
        emit({"ok": True, "src": src, "dst": dst, "count": len(found),
              "truncated": len(found) >= max_paths, "all_paths": found}, json_output, pretty)
        return

    one = resolver.find_path(src, dst)
    emit({"ok": True, "src": src, "dst": dst, "found": one is not None,
          "hop_count": (len(one) - 1) if one else None, "path": one}, json_output, pretty)
