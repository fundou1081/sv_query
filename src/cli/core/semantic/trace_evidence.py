# ==============================================================================
# trace_evidence.py — evidence 命令 (召回 always/if 块完整源码)
# ==============================================================================
"""evidence 命令 (召回 always/if 块完整源码)

[iter_253 T3-3] 从 `semantic/trace.py` (1,835 行) 拆出: 该文件同时承载 fanin/fanout/
impact/evidence/overview 五个命令 + DOT 生成 + 多种文本渲染。本模块只放 evidence 命令 (召回 always/if 块完整源码)。
命令注册仍在 `trace.py` (避免循环 import)。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from cli._evidence_helpers import build_resolver as _build_evidence_resolver  # noqa: E402
from cli._evidence_helpers import evidence_to_dict as _evidence_to_dict  # noqa: E402
from cli._output import emit_json
from cli.core.semantic.trace_common import (
    _collect_signals, resolve_signal, resolution_fields,
    resolution_error_message, SignalResolutionError,
)
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer

logger = logging.getLogger(__name__)

# ==============================================================================
# Stage 3A: evidence 命令 - 召回 always/if 块完整源码
# ==============================================================================

def evidence(
    signal: str = typer.Argument(None, help="Signal to query (e.g., top.q). Optional when --batch or --batch-file is used."),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    chain: bool = typer.Option(False, "--chain", "-c", help="Show evidence for entire driver chain"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly tree output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
    batch_file: str = typer.Option(None, "--batch-file", help="[B1 2026-07-03] Path to file with one signal per line (# comment, blank skipped)."),
    batch: str = typer.Option(None, "--batch", help="[B1 2026-07-03] Inline batch of signals, comma-separated (e.g., 'top.clk,top.rst_n')."),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="[B4 2026-07-03] Load graph from saved snapshot tag. Mutually exclusive with --file/--filelist."),
    no_cache: bool = typer.Option(False, "--no-cache", help="[A1 2026-07-04] Disable AST cache (default: cache enabled for repeat invocations)."),
) -> None:
    """展示信号的源码 evidence (enclosing always/if 块完整源码)

    Single signal: sv_query trace evidence top.q -f top.sv
    Batch:        sv_query trace evidence --batch 'top.q,top.a' -f top.sv
    """
    try:
        signals = _collect_signals(signal, batch_file, batch)
        # [Stage 5] 用公共 helper build resolver (其他 4 个命令也共用)
        resolver, _graph, _sem = _build_evidence_resolver(file=file, filelist=filelist, preprocess_macros=preprocess_macros, from_snapshot=from_snapshot)

        # [B1 2026-07-03] Batch mode
        # [A3 2026-07-04] Per-signal try/except: failed signals go to errors[], continue on others
        signals_result = []
        per_signal_errors = []
        for i, sig in enumerate(signals):
            try:
                _res = resolve_signal(_graph, sig)
                if not _res["ok"]:
                    raise SignalResolutionError(
                        resolution_error_message(sig, _res),
                        error_code=("E_SIGNAL_AMBIGUOUS" if _res["status"] == "ambiguous"
                                    else "E_SIGNAL_NOT_FOUND"),
                        resolution=_res["status"], candidates=_res.get("candidates"),
                        suggestions=_res.get("suggestions"),
                    )
                _query_sig = _res["resolved"]
                if chain:
                    evidences = resolver.resolve_chain(_query_sig)
                    ev_dicts = [_evidence_to_dict(e) for e in evidences]
                else:
                    ev = resolver.resolve(_query_sig)
                    ev_dicts = _evidence_to_dict(ev)
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "evidence": ev_dicts,
                    "error": "",
                    **resolution_fields(_res),
                })
            except Exception as sig_err:
                # [A3 2026-07-04] Per-signal failure → record error, continue
                from src.cli.errors import code_for_exception, make_error
                err_data = make_error(
                    code_for_exception(sig_err), str(sig_err), command="trace_evidence",
                )
                per_signal_errors.append({
                    "signal": sig,
                    "index": i,
                    "error": err_data["error"],
                    "error_code": err_data.get("error_code", "E_INTERNAL"),
                })
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "evidence": None,
                    "resolved_signal": getattr(sig_err, "resolved", None),
                    "resolution": getattr(sig_err, "resolution", "internal"),
                    "candidates": getattr(sig_err, "candidates", []),
                    "suggestions": getattr(sig_err, "suggestions", []),
                    "error": err_data["error"],
                })

        data = {
            "ok": per_signal_errors == [],
            "command": "trace_evidence",
            "params": {"signals": signals, "file": str(file), "chain": chain, "batch_file": batch_file, "batch": batch, "from_snapshot": from_snapshot, "no_cache": no_cache},
            "result": {
                "signals": signals_result,
                "total_signals": len(signals),
                "failed_signals": len(per_signal_errors),
            },
            "errors": per_signal_errors,
        }

        # [FIX 2026-07-05] single-signal backward compat: 顶级 evidence field
        if len(signals_result) == 1 and not chain:
            data["evidence"] = signals_result[0]["evidence"]

        if json_output:
            emit_json(data, pretty)
        else:
            # Text mode: render each signal's evidence with header
            for sig_entry in signals_result:
                sig = sig_entry["signal"]
                idx = sig_entry["index"] + 1
                total = len(signals)
                print(f"signal {idx}/{total}: {sig}")
                print("=" * 60)
                if sig_entry.get("resolution") in ("not_found", "ambiguous"):
                    print(f"  error: {sig_entry.get('error', sig_entry.get('resolution'))}")
                    for cand in sig_entry.get("candidates", [])[:8]:
                        print(f"    candidate: {cand}")
                    if idx < total:
                        print()
                    continue
                ev_data = {"signal": sig}
                if chain:
                    ev_data["evidence_chain"] = sig_entry["evidence"]
                else:
                    ev_data["evidence"] = sig_entry["evidence"]
                _output_evidence_text(ev_data, tree=tree, human=human)
                if idx < total:
                    print()

    except Exception as e:
        data = {"ok": False, "command": "trace_evidence", "error": str(e), "errors": [str(e)]}
        if json_output:
            emit_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


# [Stage 5] 移到 cli/_evidence_helpers.py,5 个命令共用


def _output_evidence_text(data: dict, tree: bool = False, human: bool = False) -> None:
    """人友好文本输出

    tree: --tree flag. 当 --chain mode 时, 在 [Step N] 列表前加 render_signal_tree
    human: --human flag. (现仅影响是否去掉 ANSI color, current implementation 不区分)
    """
    signal = data.get("signal", "")
    print(f"Signal: {signal}")
    print("=" * 60)

    chain = data.get("evidence_chain")
    if chain is not None:
        # driver chain mode
        if not chain:
            print("  (no evidence found)")
            return
        # [FIX 2026-07-05] --tree: 在 [Step N] 之前用 render_signal_tree 画 chain tree
        if tree:
            from cli._evidence_helpers import render_signal_tree
            chain_signals = [ev.get("signal", "?") for ev in chain]
            tree_out = render_signal_tree(chain_signals)
            if tree_out:
                print(f"\n{tree_out}")
        for i, ev in enumerate(chain):
            print(f"\n[Step {i}] {ev.get('signal', '?')}")
            if ev.get("source_text"):
                print(f"  Source: {ev['source_text']!r}")
            if ev.get("enclosing_if"):
                loc = ev["enclosing_if"]
                print(f"\n  >>> Enclosing IF @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
            if ev.get("enclosing_always"):
                loc = ev["enclosing_always"]
                print(f"\n  >>> Enclosing ALWAYS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
            if ev.get("enclosing_class"):
                loc = ev["enclosing_class"]
                print(f"\n  >>> Enclosing CLASS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
            if ev.get("enclosing_constraint"):
                loc = ev["enclosing_constraint"]
                print(f"\n  >>> Enclosing CONSTRAINT @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
        return

    ev = data.get("evidence", {})
    if not ev:
        print("  (no evidence found)")
        return
    if ev.get("source_text"):
        print(f"Source: {ev['source_text']!r}")
    if ev.get("enclosing_if"):
        loc = ev["enclosing_if"]
        print(f"\n>>> Enclosing IF @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    if ev.get("enclosing_always"):
        loc = ev["enclosing_always"]
        print(f"\n>>> Enclosing ALWAYS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    if ev.get("enclosing_class"):
        loc = ev["enclosing_class"]
        print(f"\n>>> Enclosing CLASS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    if ev.get("enclosing_constraint"):
        loc = ev["enclosing_constraint"]
        print(f"\n>>> Enclosing CONSTRAINT @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    chain_inner = ev.get("enclosing_chain", [])
    if chain_inner:
        print(f"\nFull chain ({len(chain_inner)} levels):")
        for i, snip in enumerate(chain_inner):
            if snip:
                preview = snip["text"][:60].replace("\n", "\\n")
                print(f"  [{i}] {snip['file']}:{snip['line_start']}-{snip['line_end']}  {preview!r}")
