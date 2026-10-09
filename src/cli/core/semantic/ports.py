"""
core/semantic/ports.py — [iter_237] 模块端口总览 (`svq ports <模块名>`)

回答: "这个模块有哪些端口、方向、位宽、各连了几条边?" ——
数据来自信号图的 PORT_IN/PORT_OUT/PORT_INOUT 节点 (+ 出入边计数)。
比 `connections <模块>` 更"表格式": 一行一个端口, 适合 agent 直接消费。
"""
from __future__ import annotations

from pathlib import Path

import typer

from cli.core.semantic._common import build_tracer, emit, fail


def ports_cmd(
    module: str = typer.Argument(..., help="模块名 (如 dma_top)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """模块端口一览 (方向/位宽/入边数/出边数)。

注意: in_edges/out_edges 是**信号图原始邻接计数**, 不是语义上的 driver/load 判定
(要看语义用 `svq connections <模块>` / `svq drivers`)。
"""
    tracer = build_tracer(file, filelist, log_level)
    if tracer is None:
        return

    from trace.core.graph.models import NodeKind

    graph = tracer.get_graph()
    port_kinds = {NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.PORT_INOUT}
    rows = []
    for nid in graph.nodes():
        n = graph.get_node(nid)
        if n is None or n.kind not in port_kinds or getattr(n, "module", None) != module:
            continue
        rows.append({
            "port": n.name,
            "id": n.id,
            "direction": {NodeKind.PORT_IN: "input", NodeKind.PORT_OUT: "output",
                          NodeKind.PORT_INOUT: "inout"}[n.kind],
            "width": list(n.width) if n.width else None,
            "in_edges": len(list(graph.predecessors(nid))) if nid in graph else 0,
            "out_edges": len(list(graph.successors(nid))) if nid in graph else 0,
        })
    if not rows:
        fail("module has no ports (or module not found)", json_output, pretty, module=module,
             hint="用 `svq instances --json` / `svq hierarchy --json` 确认模块名")
    rows.sort(key=lambda r: (r["direction"], r["port"] or ""))
    by_dir: dict[str, int] = {}
    for r in rows:
        by_dir[r["direction"]] = by_dir.get(r["direction"], 0) + 1
    emit({"ok": True, "module": module, "count": len(rows), "by_direction": by_dir,
          "ports": rows}, json_output, pretty)
