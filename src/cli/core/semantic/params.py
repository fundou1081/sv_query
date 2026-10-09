"""
core/semantic/params.py — [iter_237] 实例参数生效值查询 (`svq params <实例路径>`)

回答: "这个实例的 `#(.WIDTH(8))` 到底生效成什么?" ——
pyslang 的 `InstanceSymbol.body.parameters` 给出**求值后**的参数 (ConstantValue),
并能区分 **被 override** 与 **用默认值** (`isOverridden`)。
"""
from __future__ import annotations

from pathlib import Path

import typer

from cli.core.semantic._common import build_tracer, emit, fail


def params_cmd(
    path: str = typer.Argument(..., help="实例路径 (如 top.u_dut)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """实例的**生效参数值** (含是否被 override)。

    例: svq params top.u_child --filelist project.f --json
    """
    tracer = build_tracer(file, filelist, log_level)
    if tracer is None:
        return

    target = None
    for w in tracer._get_adapter().get_module_instances():
        sym = getattr(w, "_symbol", None)
        if getattr(sym, "hierarchicalPath", None) == path:
            target = w
            break
    if target is None:
        fail("instance not found", json_output, pretty, path=path,
             hint="用 `svq instances --json` 列可用实例")

    body = getattr(target._symbol, "body", None)
    rows = []
    for p in getattr(body, "parameters", []) or []:
        val = getattr(p, "value", None)
        try:
            text = val.toString() if hasattr(val, "toString") else str(val)
        except Exception:
            text = None
        rows.append({
            "name": str(getattr(p, "name", "")),
            "value": text,
            "is_overridden": bool(getattr(p, "isOverridden", False)),
            "is_local_param": bool(getattr(p, "isLocalParam", False)),
        })
    mtype = getattr(getattr(target, "type", None), "value", None)
    emit({"ok": True, "instance": path, "module_type": str(mtype) if mtype else None,
          "count": len(rows), "parameters": rows}, json_output, pretty)
