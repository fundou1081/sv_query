"""[iter_332 / PLAN P36.1] trace profile：波形关联元数据。

给定信号，输出：
- canonical id / aliases / 层级 / 位映射 / 声明位置
- clock / reset / sequential 画像
- driver/load 计数

只读；不做仿真值。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from cli.core.semantic.trace_common import (
    _collect_signals, resolve_signal, resolution_error_message,
    SignalResolutionError,
)
logger = logging.getLogger(__name__)

from trace.core.compiler import CompilationError
from trace.core.trace_evidence import TraceEvidenceResolver


def _first_source(edge) -> tuple[str, int | None]:
    loc = getattr(edge, "source_location", None)
    if loc is not None and not loc.is_empty():
        return loc.file, loc.line_start
    return "", None


def _profile_signal(tracer, graph, sig: str, evidence_resolver=None) -> dict:
    res = resolve_signal(graph, sig)
    if not res["ok"]:
        raise SignalResolutionError(
            resolution_error_message(sig, res),
            error_code=("E_SIGNAL_AMBIGUOUS" if res["status"] == "ambiguous"
                        else "E_SIGNAL_NOT_FOUND"),
            resolution=res["status"], candidates=res.get("candidates"),
            suggestions=res.get("suggestions"),
        )
    node_id = res["resolved"]
    node = graph.get_node(node_id)
    if node is None:
        raise SignalResolutionError(
            f"resolved signal {node_id!r} has no graph node",
            error_code="E_SIGNAL_NOT_FOUND", resolution=res["status"],
        )

    clocks: list[dict] = []
    resets: list[dict] = []
    assign_types: list[str] = []
    driver_file, driver_line = "", None
    for pred in sorted(graph.predecessors(node_id)):
        for edge in graph.get_edges(pred, node_id):
            kind = getattr(getattr(edge, "kind", None), "name", "")
            cond = getattr(edge, "condition", "") or getattr(edge, "effective_condition", "")
            if kind == "CLOCK":
                clocks.append({"signal": pred, "condition": cond,
                               "clock_domain": getattr(edge, "clock_domain", "")})
            elif kind == "RESET":
                resets.append({"signal": pred, "condition": cond})
            elif kind == "DRIVER":
                at = getattr(edge, "assign_type", "")
                if at and at not in assign_types:
                    assign_types.append(at)
                if driver_line is None:
                    driver_file, driver_line = _first_source(edge)

    clock_domains = sorted({c.get("clock_domain") or c["signal"] for c in clocks})
    is_seq = bool(clocks or resets) or any(
        t in ("always_ff", "always_ff_nonblocking", "nonblocking") for t in assign_types)
    # 用 evidence resolver 修正 driver 源码行（edge.source_location 常是条件行）
    if evidence_resolver is not None:
        try:
            ev = evidence_resolver.resolve(node_id)
            loc = getattr(ev, "source_location", None)
            if loc is not None and not loc.is_empty():
                driver_file, driver_line = loc.file, loc.line_start
        except Exception as ev_err:
            logger.debug("profile evidence driver loc failed for %s: %s", node_id, ev_err)
    aliases = []
    for a in (node.id, node.name,
              node.id.split(".", 1)[1] if "." in node.id else ""):
        if a and a not in aliases:
            aliases.append(a)

    return {
        "signal": sig,
        "index": 0,
        "resolved_signal": node_id,
        "resolution": res["status"],
        "aliases": aliases,
        "width": list(node.width) if node.width else None,
        "is_signed": node.is_signed,
        "kind": getattr(getattr(node, "kind", None), "name", ""),
        "module": node.module,
        "bit": {
            "bit_range": node.bit_range,
            "parent": node.parent,
            "parent_bit_start": node.parent_bit_start,
            "parent_bit_end": node.parent_bit_end,
        },
        "source": {
            "file": getattr(node, "file", ""),
            "line": getattr(node, "line", 0),
            "declaration": (f"{node.file}:{node.line}"
                            if getattr(node, "file", "") and getattr(node, "line", 0) else ""),
            "driver": ({"file": driver_file, "line": driver_line}
                       if driver_line is not None else None),
        },
        "role": {
            "is_clock": bool(node.is_clock),
            "is_reset": bool(node.is_reset),
            "is_enable": bool(node.is_enable),
            "is_port": bool(node.is_port),
            "modport_dir": node.modport_dir,
        },
        "clock_domains": clock_domains,
        "clocks": clocks,
        "resets": resets,
        "sequential": {
            "is_sequential": is_seq,
            "assign_types": assign_types,
            "stage": None,
            "stage_known": False,
        },
        "driver_count": len(tracer.trace_fanin(node_id, depth=1)),
        "load_count": len(tracer.trace_fanout(node_id, depth=1)),
        "error": "",
    }


def profile(
    signal: str = typer.Argument(None, help="Signal to profile (e.g., top.q). Optional with --batch/--batch-file."),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    batch_file: str = typer.Option(None, "--batch-file", help="one signal per line"),
    batch: str = typer.Option(None, "--batch", help="comma-separated signals"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """信号 profile：canonical/aliases/位映射/clock/reset/sequential/source。"""
    try:
        signals = _collect_signals(signal, batch_file, batch)
        tracer = _build_tracer(file=file, filelist=filelist, log_level=log_level)
        graph = tracer.build_graph()
        out = []
        errors = []
        try:
            evidence_resolver = TraceEvidenceResolver(graph=graph,
                                                      adapter=tracer._get_adapter())
        except Exception:
            evidence_resolver = None
        for i, sig in enumerate(signals):
            try:
                item = _profile_signal(tracer, graph, sig, evidence_resolver)
                item["index"] = i
                out.append(item)
            except Exception as e:
                errors.append({
                    "signal": sig, "index": i,
                    "error": str(e),
                    "error_code": getattr(e, "error_code", "E_INTERNAL"),
                    "resolution": getattr(e, "resolution", "internal"),
                    "candidates": getattr(e, "candidates", []),
                })
                out.append({
                    "signal": sig, "index": i,
                    "resolved_signal": None,
                    "resolution": getattr(e, "resolution", "internal"),
                    "aliases": [], "width": None, "is_signed": None, "kind": "",
                    "module": "", "bit": {}, "source": {}, "role": {},
                    "clock_domains": [], "clocks": [], "resets": [],
                    "sequential": {"is_sequential": False, "assign_types": [],
                                   "stage": None, "stage_known": False},
                    "driver_count": 0, "load_count": 0,
                    "error": str(e),
                })
        data = {
            "ok": not errors,
            "command": "trace_profile",
            "params": {"signals": signals, "file": str(file) if file else None,
                       "filelist": filelist, "batch_file": batch_file, "batch": batch},
            "result": {"signals": out, "total_signals": len(signals),
                       "failed_signals": len(errors)},
            "errors": errors,
        }
        if json_output:
            emit_json(data, pretty)
        else:
            for item in out:
                print(f"{item['signal']} -> {item.get('resolved_signal')}")
                print(f"  width={item.get('width')} signed={item.get('is_signed')} "
                      f"clock={item.get('clock_domains')} reset={[r['signal'] for r in item.get('resets', [])]} "
                      f"sequential={item.get('sequential', {}).get('is_sequential')}")
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "trace_profile", "error": str(e),
                "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}", file=__import__("sys").stderr)
        raise typer.Exit(code=1) from None
