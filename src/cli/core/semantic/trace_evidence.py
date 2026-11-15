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
import re
from pathlib import Path

import typer

from cli._evidence_helpers import build_resolver as _build_evidence_resolver  # noqa: E402
from cli._evidence_helpers import evidence_to_dict as _evidence_to_dict  # noqa: E402
from cli._output import emit_json
from cli.core.semantic.trace_common import (
    _collect_signals, resolve_signal, resolution_fields,
    resolution_error_message, SignalResolutionError,
)
from sv_query.trace.core.sva_extractor import SVAExtractor
from sv_query.trace.unified_tracer import UnifiedTracer

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _compiler_sources(adapter) -> dict[str, str]:
    compiler = getattr(adapter, "_compiler", None)
    if compiler is None:
        return {}
    return dict(getattr(compiler, "sources", {}) or {})


def _read_source_text(file_name: str, sources: dict[str, str] | None = None) -> str | None:
    """Read a source file, tolerating basenames from filelist mode."""
    if sources:
        for key, text in sources.items():
            if Path(key).name != Path(file_name).name:
                continue
            try:
                return Path(key).read_text(errors="ignore")
            except OSError:
                return text
    p = Path(file_name)
    candidates = [p] if p.is_absolute() else [Path.cwd() / p, _REPO_ROOT / p]
    for candidate in candidates:
        try:
            return candidate.read_text(errors="ignore")
        except OSError:
            continue
    return None


def _strip_block_comments(text: str) -> str:
    def _blank(match):
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))
    return re.sub(r"/\*.*?\*/", _blank, text, flags=re.S)


def _line_is_lhs(text: str, signal: str) -> bool:
    leaf = signal.rsplit(".", 1)[-1]
    code = _strip_block_comments(text or "").split("//")[0].strip()
    pat = re.compile(
        rf"^(?:else\s+)?(?:if\s*\([^)]*\)\s*)?(?:assign\s+)?"
        rf"{re.escape(leaf)}\b\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))")
    return bool(pat.search(code))


def _collect_if_condition(lines: list[str], idx: int) -> str | None:
    text = "\n".join(lines[idx:idx + 8])
    m = re.search(r"\bif\s*\(", text)
    if not m:
        return None
    depth, start = 1, m.end()
    for pos in range(start, len(text)):
        if text[pos] == "(":
            depth += 1
        elif text[pos] == ")":
            depth -= 1
            if depth == 0:
                return text[start:pos]
    return text[start:]


def _branch_condition(lines: list[str], lo: int, idx: int) -> str | None:
    for j in range(idx, lo - 1, -1):
        code = lines[j].split("//")[0]
        if re.search(r"\bif\s*\(", code):
            return _collect_if_condition(lines, j)
        if re.search(r"\belse\b", code):
            return ""  # plain else branch is functional
    return None


def _nearest_if_is_reset(lines: list[str], lo: int, idx: int) -> bool:
    cond = _branch_condition(lines, lo, idx)
    return bool(cond and _is_reset_condition(cond))

def _find_functional_assignment(signal: str, file_text: str,
                                start: int, end: int) -> tuple[int, str] | None:
    """Find the non-reset LHS assignment line for a signal in a source range."""
    lines = _strip_block_comments(file_text).splitlines()
    lo = max(0, start - 1)
    hi = min(len(lines), end if end else len(lines))
    candidates = [i for i in range(lo, hi) if _line_is_lhs(lines[i], signal)]
    for idx in reversed(candidates):
        if _nearest_if_is_reset(lines, lo, idx):
            continue
        return idx + 1, lines[idx].strip()
    return None


# ==============================================================================
# Stage 3A: evidence 命令 - 召回 always/if 块完整源码
# ==============================================================================

def _is_reset_condition(cond: str) -> bool:
    c = (cond or "").strip().lower()
    return bool(re.search(r"(?:^|[^a-z0-9])(?:a?reset|s?rst|arst|nrst)\w*", c)) and "&&" not in c and "||" not in c


def _line_has_reset_edge(graph, signal: str, line: int) -> bool:
    if graph is None or not line:
        return False
    for src, dst in graph.edges():
        if dst != signal:
            continue
        for edge in graph.get_edges(src, dst):
            loc = getattr(edge, "source_location", None)
            if loc is None or getattr(loc, "line_start", 0) != line:
                continue
            if _is_reset_condition(getattr(edge, "condition", "") or ""):
                return True
    return False


def _is_const_edge(graph, edge) -> bool:
    node = graph.get_node(edge.src)
    kind = getattr(getattr(node, "kind", None), "name", "")
    return kind == "CONST"


def _edge_source_text(loc, expression: str, sources=None) -> str:
    text = _read_source_text(getattr(loc, "file", ""), sources)
    if text:
        lines = text.splitlines()
        if 0 < getattr(loc, "line_start", 0) <= len(lines):
            return lines[loc.line_start - 1].strip()
    return expression


def _edge_line_ok(text: str, signal: str) -> bool:
    return bool(text) and _line_is_lhs(text, signal)


def _snapshot_edge_evidence(graph, signal: str, sources=None) -> dict | None:
    """Build assignment-level evidence from snapshot edges.

    A snapshot has no source text, but P119 edges carry source_location and
    expression. Prefer a functional driver edge with an expression over a
    clock/reset edge, so evidence points at the assignment rather than the
    declaration or reset branch.
    """
    candidates = []
    for src, dst in graph.edges():
        if dst != signal:
            continue
        for edge in graph.get_edges(src, dst):
            loc = getattr(edge, "source_location", None)
            if loc is None or not getattr(loc, "file", ""):
                continue
            candidates.append((edge, loc))
    if not candidates:
        return None
    # Prefer a functional data assignment over a reset/const edge.
    candidates.sort(key=lambda item: (
        _is_const_edge(graph, item[0]),
        _is_reset_condition(getattr(item[0], "condition", "") or ""),
        not bool(getattr(item[0], "expression", "")),
        getattr(item[1], "line_start", 0),
        item[0].src,
    ))
    edge, loc = candidates[0]
    source_text = _edge_source_text(loc, getattr(edge, "expression", "") or "", sources)
    line_ok = _edge_line_ok(source_text, signal)
    return {
        "signal": signal,
        "source_location": loc.to_dict(),
        "source_text": source_text,
        "enclosing_always": None,
        "enclosing_always_comb": None,
        "enclosing_if": None,
        "enclosing_assign": None,
        "enclosing_class": None,
        "enclosing_constraint": None,
        "enclosing_chain": [],
        "is_verified": line_ok,
        "credibility_score": 1.0 if line_ok else 0.2,
    }


def _evidence_source(d):
    if not isinstance(d, dict):
        return "", 0
    loc = d.get("source_location") or {}
    return d.get("source_text", "") or "", loc.get("line_start", 0)


def _evidence_is_reset(graph, signal, d):
    text, line = _evidence_source(d)
    if _is_reset_condition(text):
        return True
    return _line_has_reset_edge(graph, signal, line)


def _functional_line_for(ev_dict, signal: str, sources=None):
    loc = ev_dict.get("source_location") or {}
    file_name = loc.get("file", "")
    if not file_name:
        return None
    text = _read_source_text(file_name, sources)
    if text is None:
        return None
    always = ev_dict.get("enclosing_always") or {}
    start = always.get("line_start") or max(1, loc.get("line_start", 0) - 12)
    end = always.get("line_end") or (loc.get("line_end", 0) + 12)
    return _find_functional_assignment(signal, text, start, end)


def _with_functional_line(ev_dict, signal: str, sources=None):
    if not isinstance(ev_dict, dict):
        return ev_dict
    if ev_dict.get("enclosing_class") or ev_dict.get("enclosing_constraint"):
        return ev_dict
    found = _functional_line_for(ev_dict, signal, sources)
    if found is None:
        return ev_dict
    line, source = found
    ev_dict = dict(ev_dict)
    ev_dict["source_location"] = {**ev_dict["source_location"],
                                  "line_start": line, "line_end": line}
    ev_dict["source_text"] = source
    leaf = signal.rsplit(".", 1)[-1]
    ev_dict["is_verified"] = leaf in source
    ev_dict["credibility_score"] = 1.0 if leaf in source else 0.2
    return ev_dict

def _resolve_evidence_dict(resolver, graph, signal: str, sources=None) -> dict | None:
    ev_dict = _evidence_to_dict(resolver.resolve(signal))
    fallback = _snapshot_edge_evidence(graph, signal, sources)
    text, _ = _evidence_source(ev_dict)
    if not ev_dict or not text:
        return _with_functional_line(
            fallback if fallback is not None else ev_dict, signal, sources)
    if (fallback is not None and _evidence_is_reset(graph, signal, ev_dict)
            and not _evidence_is_reset(graph, signal, fallback)):
        return _with_functional_line(fallback, signal, sources)
    return _with_functional_line(ev_dict, signal, sources)

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
        _sources = _compiler_sources(_sem)

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
                    ev_dicts = _resolve_evidence_dict(resolver, _graph, _query_sig, _sources)
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "evidence": ev_dicts,
                    "error": "",
                    **resolution_fields(_res),
                })
            except Exception as sig_err:
                # [A3 2026-07-04] Per-signal failure → record error, continue
                from cli.errors import code_for_exception, make_error
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
            "params": {"signals": signals, "file": str(file) if file else None,
                       "chain": chain, "batch_file": batch_file, "batch": batch,
                       "from_snapshot": from_snapshot, "no_cache": no_cache},
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
