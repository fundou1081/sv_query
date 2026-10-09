"""
core/semantic/_common.py — [iter_237] 语义查询命令的共享工具 (tracer 构建 / JSON 输出 / 节点序列化)

避免 instances/params/ports/paths/classes 各自复制一份。
"""
from __future__ import annotations

import json

import typer

from cli._common import _build_tracer, handle_compilation_error
from trace.core.compiler import CompilationError


def build_tracer(file, filelist, log_level: str = "WARNING"):
    """统一构建 tracer (支持 --file / --filelist) 并 build_graph。

    编译失败 → 走统一错误格式化 (结构化 exit), 返回 None (调用方直接 return)。
    """
    try:
        tracer = _build_tracer(file=file, filelist=filelist, log_level=log_level)
        tracer.build_graph()
        return tracer
    except CompilationError as e:
        handle_compilation_error(e)
        return None


def node_dict(node) -> dict:
    """TraceNode → 精简 dict (id/name/kind/module/width)。"""
    kind = getattr(node, "kind", None)
    width = getattr(node, "width", None)
    return {
        "id": node.id,
        "name": getattr(node, "name", None),
        "kind": kind.name if hasattr(kind, "name") else str(kind),
        "module": getattr(node, "module", None),
        "width": list(width) if width else None,
    }


def emit(data: dict, json_output: bool, pretty: bool) -> None:
    if json_output:
        typer.echo(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))
        return
    for k, v in data.items():
        if isinstance(v, list):
            typer.echo(f"{k}: {len(v)}")
            for item in v[:20]:
                typer.echo(f"  - {item if not isinstance(item, dict) else item.get('id') or item}")
        else:
            typer.echo(f"{k}: {v}")


def fail(msg: str, json_output: bool, pretty: bool, **extra) -> None:
    """结构化失败 (rc=1), 不静默返回空结果。"""
    payload = {"ok": False, "error": msg, **extra}
    typer.echo(json.dumps(payload, indent=2 if pretty else None, ensure_ascii=False)
               if json_output else f"❌ {msg}")
    raise typer.Exit(code=1)
