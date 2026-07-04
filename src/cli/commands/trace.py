# ==============================================================================
# trace.py - trace fanin / fanout / impact subcommands
# ============================================================================
"""
Usage:
  python run_cli.py trace fanin top.clk -f top.sv
  python run_cli.py trace fanout top.data -f top.sv
  python run_cli.py trace impact top.changed_signal -f top.sv
"""

import json
import sys
from pathlib import Path

import typer

# 添加 src 到 path 以便 import trace
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.models import EdgeKind
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer

# [Stage 5] evidence helper (cdc/verify/risk/dataflow/controlflow 复用)
from cli._evidence_helpers import (  # noqa: E402
    build_resolver as _build_evidence_resolver,
    evidence_to_dict as _evidence_to_dict,
    snippet_to_dict as _snippet_to_dict,
    evidence_summary_line as _evidence_summary_line,
    format_fanin_human as _format_fanin_human,
    format_fanout_human as _format_fanout_human,
)


# JSON 输出格式化函数
def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def _collect_signals(
    signal: str | None,
    batch_file: str | None,
    batch: str | None,
) -> list[str]:
    """[B1 2026-07-03] Collect signals from positional + --batch-file + --batch.

    Priority: dedup, preserves first occurrence order.
    Comment lines (#) and empty lines in batch_file are skipped.
    Returns: list of unique signals (at least 1 if any source provided).

    Raises:
        ValueError: batch_file not found, or no signals collected from any source.
    """
    signals: list[str] = []
    if signal:
        signals.append(signal)
    if batch_file:
        try:
            with open(batch_file) as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    signals.append(s)
        except FileNotFoundError as e:
            raise ValueError(f"batch file not found: {batch_file}") from e
    if batch:
        for s in batch.split(","):
            s = s.strip()
            if s:
                signals.append(s)
    # dedup, preserve order
    seen: set[str] = set()
    deduped = [s for s in signals if not (s in seen or seen.add(s))]
    if not deduped:
        raise ValueError(
            "No signals: provide SIGNAL, --batch-file PATH, or --batch 'sig1,sig2'"
        )
    return deduped


def _node_to_dict(node) -> dict:
    """[B2 2026-07-03] Convert TraceNode to dict with module + width info.

    暴露 module (for --module filter) + width_msb/width_lsb/width (for --width-min/max).
    原有 id/kind/distance 字段保留 (向后兼容).
    """
    width_tuple = getattr(node, "width", (0, 0))
    if isinstance(width_tuple, (tuple, list)) and len(width_tuple) >= 2:
        width_msb = width_tuple[0]
        width_lsb = width_tuple[1]
        width = max(0, width_msb - width_lsb + 1)
    else:
        width_msb = width_lsb = width = 0
    return {
        "id": node.id,
        "kind": getattr(node, "kind", "UNKNOWN").name if hasattr(node, "kind") else "UNKNOWN",
        "module": getattr(node, "module", ""),
        "width_msb": width_msb,
        "width_lsb": width_lsb,
        "width": width,
        "distance": getattr(node, "distance", 1) if hasattr(node, "distance") else 1,
    }


def _apply_filters(
    items: list[dict],
    type_filter: str | None = None,
    module_filter: str | None = None,
    width_min: int | None = None,
    width_max: int | None = None,
    exclude: str | None = None,
) -> list[dict]:
    """[B2 2026-07-03] Apply 5 filters to driver/load dicts.

    Uses fnmatch (NOT regex - project discipline: no regex in src/trace/core/).
    Returns filtered list (preserves order). Empty list if all filtered out.
    """
    import fnmatch
    out = items
    if type_filter:
        types = {t.strip().upper() for t in type_filter.split(",") if t.strip()}
        out = [d for d in out if d.get("kind", "").upper() in types]
    if module_filter:
        out = [d for d in out if fnmatch.fnmatch(d.get("module", ""), module_filter)]
    if width_min is not None:
        out = [d for d in out if d.get("width", 0) >= width_min]
    if width_max is not None:
        out = [d for d in out if d.get("width", 0) <= width_max]
    if exclude:
        out = [d for d in out if not fnmatch.fnmatch(d.get("id", ""), exclude)]
    return out


def _load_tracer_from_snapshot(
    tag: str,
    log_level: str = "ERROR",
    strict: bool = True,
    preprocess_macros: bool = True,
) -> "UnifiedTracer":
    """[B4 2026-07-03] Build UnifiedTracer from saved snapshot, skip SV parse.

    用途: 同一 graph 跑多次 trace 命令, parse 1 次 (snapshot save) + trace N 次.
    加速: 大项目 (50+ SV) 跑 4 子命令各 1 次 = 4× parse, 现在 1×.

    [A2 2026-07-04] Use SignalGraph.from_dict() instead of manual add_trace_node/edge
    (1 line vs 30 lines, prevents field drift).

    Returns: UnifiedTracer with _graph + _signal_tracer pre-populated from snapshot JSON.

    Raises:
        ValueError: snapshot tag not found.
    """
    from trace.core.snapshot_manager import SnapshotManager
    from trace.core.graph.models import SignalGraph
    from trace.core.query.signal import SignalTracer

    manager = SnapshotManager()
    snap = manager.load(tag)
    if snap is None:
        raise ValueError(f"Snapshot not found: {tag}")

    # [A2 2026-07-04] Use from_dict (handles all node/edge fields + port_to_internal)
    # Snapshot extra fields (version, files, elaboration_errors, ...) are ignored
    # by from_dict, which is what we want.
    graph = SignalGraph.from_dict(snap)

    # Stub tracer: pre-populate _graph + _signal_tracer
    tracer = UnifiedTracer(
        sources={}, log_level=log_level, strict=strict, preprocess_macros=preprocess_macros,
    )
    tracer._graph = graph
    tracer._signal_tracer = SignalTracer(graph, mig=None, use_mig=False)
    return tracer


def output_text(data: dict, human: bool = False, tree: bool = False) -> None:
    """纯文本输出

    Args:
        data: 命令返回的 dict
        human: True 时用人类友好箭头格式 (--human flag)
        tree: True 强制竖向 tree 输出 (--tree flag, 链 > 6 自动)
    """
    command = data.get("command", "")
    result = data.get("result", {})

    if command == "trace_fanin":
        # [B1 2026-07-03] Batch mode: result.signals = [{signal, drivers, ...}, ...]
        #                 Single mode: result.drivers = [...] (legacy)
        signals_result = result.get("signals")
        if signals_result is not None:
            # Batch output
            total = len(signals_result)
            for sig_entry in signals_result:
                sig = sig_entry["signal"]
                drivers = sig_entry["drivers"]
                i = sig_entry["index"] + 1
                print(f"signal {i}/{total}: {sig}")
                if human:
                    ev = sig_entry.get("evidence")
                    print(_format_fanin_human(sig, drivers, evidence_map={sig: ev} if ev else None, tree=tree))
                else:
                    if not drivers:
                        print("  (no drivers)")
                    for d in drivers:
                        dist = d.get("distance", "")
                        kind = d.get("kind", "")
                        print(f"  [{dist}] {d['id']} ({kind})")
                if i < total:
                    print()
        else:
            # Single-signal legacy mode
            signal = data.get("params", {}).get("signal", "")
            drivers = result.get("drivers", [])
            if human:
                ev = result.get("evidence")
                print(_format_fanin_human(signal, drivers, evidence_map={signal: ev} if ev else None, tree=tree))
            else:
                print(f"Fanin of '{signal}':")
                if not drivers:
                    print("  (no drivers)")
                for d in drivers:
                    dist = d.get("distance", "")
                    kind = d.get("kind", "")
                    print(f"  [{dist}] {d['id']} ({kind})")

    elif command == "trace_fanout":
        # [B1 2026-07-03] Batch mode
        signals_result = result.get("signals")
        if signals_result is not None:
            total = len(signals_result)
            for sig_entry in signals_result:
                sig = sig_entry["signal"]
                loads = sig_entry["loads"]
                i = sig_entry["index"] + 1
                print(f"signal {i}/{total}: {sig}")
                if human:
                    ev = sig_entry.get("evidence")
                    print(_format_fanout_human(sig, loads, evidence_map={sig: ev} if ev else None, tree=tree))
                else:
                    if not loads:
                        print("  (no loads)")
                    for load in loads:
                        dist = load.get("distance", "")
                        kind = load.get("kind", "")
                        print(f"  [{dist}] {load['id']} ({kind})")
                if i < total:
                    print()
        else:
            # Single-signal legacy mode
            signal = data.get("params", {}).get("signal", "")
            loads = result.get("loads", [])
            if human:
                ev = result.get("evidence")
                print(_format_fanout_human(signal, loads, evidence_map={signal: ev} if ev else None, tree=tree))
            else:
                print(f"Fanout of '{signal}':")
                if not loads:
                    print("  (no loads)")
                for load in loads:
                    dist = load.get("distance", "")
                    kind = load.get("kind", "")
                    print(f"  [{dist}] {load['id']} ({kind})")

    elif command == "trace_impact":
        if human:
            _output_impact_human(data, tree=tree)
        else:
            _output_impact_text(data)


def _output_impact_text(data: dict) -> None:
    """输出 impact 结果"""
    result = data.get("result", {})
    signal = data.get("params", {}).get("signal", "")
    paths = result.get("paths", [])
    modules = result.get("modules", [])
    high_risk = result.get("high_risk_count", 0)
    total_paths = result.get("total_paths", 0)

    print("=== Impact Summary ===")
    print(f"Signal: {signal}")
    print(f"Paths: {total_paths} total, {high_risk} high-risk")

    if not paths:
        print("\n  (no impact paths found)")
        return

    print(f"\nModules: {', '.join(modules) if modules else 'N/A'}")

    print(f"\n{'=' * 60}")

    for i, path in enumerate(paths, 1):
        risk = path.get("risk", "")
        risk_icon = "🔴" if risk == "HIGH" else ("🟡" if risk == "MEDIUM" else "✅")

        print(f"\n  {i}. {risk_icon} {risk} - {path.get('path_type', 'path')}")
        print(f"     Path: {' → '.join(path.get('path', []))}")
        print(f"     Fanout: {path.get('fanout', 0)} downstream loads")

        # 覆盖状态
        coverage = path.get("coverage", {})
        sva_status = coverage.get("sva", "NONE")
        cov_status = coverage.get("covergroup", "NONE")

        if sva_status == "covered" or cov_status == "covered":
            print("     Coverage: ✓ SVA covered" if sva_status == "covered" else "")
            print("     Coverage: ✓ Covergroup covered" if cov_status == "covered" else "")
        else:
            print(f"     ⚠️  No coverage (SVA: {sva_status}, Covergroup: {cov_status})")


def _output_impact_human(data: dict, tree: bool = False) -> None:
    """[Stage 6] impact 人类友好输出: 箭头链 + 风险 / 覆盖 tag

    tree: True 强制竖向 tree 输出 (--tree flag)
    """
    result = data.get("result", {})
    signal = data.get("params", {}).get("signal", "")
    paths = result.get("paths", [])
    modules = result.get("modules", [])
    high_risk = result.get("high_risk_count", 0)
    total_paths = result.get("total_paths", 0)

    # ANSI color re-import in this scope (避免乱动模块顶部 import)
    from cli._evidence_helpers import (
        _color, _ANSI_BOLD, _ANSI_DIM, _ANSI_CYAN, _ANSI_RED, _ANSI_YELLOW, _ANSI_GREEN, _ARROW
    )

    print(f"Impact of {_color(signal, _ANSI_BOLD)}")
    print(f"  {total_paths} paths, {high_risk} high-risk, {len(modules)} modules")
    if modules:
        print(f"  modules: {_color(', '.join(modules), _ANSI_DIM)}")
    print()

    if not paths:
        print(f"  {_color('(no impact paths)', _ANSI_DIM)}")
        return

    from cli._evidence_helpers import should_use_tree, render_signal_tree

    for i, path in enumerate(paths, 1):
        risk = (path.get("risk", "") or "").upper()
        if risk == "HIGH":
            risk_str = _color("HIGH", _ANSI_RED)
        elif risk == "MEDIUM":
            risk_str = _color("MEDIUM", _ANSI_YELLOW)
        else:
            risk_str = _color(risk or "LOW", _ANSI_GREEN)

        chain = path.get("path", [])
        cond = path.get("condition", "")
        cov = path.get("coverage", {})
        sva = cov.get("sva", "none")
        cg = cov.get("covergroup", "none")
        sug = path.get("suggestion", "")

        # tree 模式 / 自动转 tree
        if should_use_tree(len(chain), tree):
            print(f"  {i}. (tree)")
            tree_out = render_signal_tree(
                chain,
                title=None,
                risk_marker=risk if risk in ("HIGH", "MEDIUM") else None,
                terminal_meta=f"when {cond}" if cond else None,
            )
            for ln in tree_out.split("\n"):
                print(f"     {ln}")
        else:
            if chain:
                chain_str = " ".join(
                    [_color(chain[0], _ANSI_BOLD)] + [_ARROW] + [_color(s, _ANSI_CYAN) for s in chain[1:]]
                )
            else:
                chain_str = "(empty)"
            print(f"  {i}. {chain_str}  [{risk_str}]")

        cov_str = f"sva={sva}, covergroup={cg}"
        cond_str = f"  when {_color(cond, _ANSI_DIM)}" if cond else ""
        print(f"     {cov_str}  fanout={path.get('fanout', 0)}{cond_str}")
        if sug:
            print(f"     {_color('└─ ' + sug, _ANSI_DIM)}")

        # 条件/时钟信息
        if path.get("condition"):
            print(f"     Condition: {path['condition']}")
        if path.get("clock_domain"):
            print(f"     Clock: {path['clock_domain']}")

        # 建议
        suggestion = path.get("suggestion", "")
        if suggestion:
            print(f"     💡 {suggestion}")

    # 总结建议
    if high_risk > 0:
        print(f"\n{'=' * 60}")
        print(f"⚠️  High-risk: {high_risk} paths lack coverage")
        print("💡  Review these paths before making changes")


trace_app = typer.Typer(help="[EXPERIMENTAL] Trace signal drivers (fanin), loads (fanout), or impact analysis")


@trace_app.command()
def fanin(
    signal: str = typer.Argument(None, help="Signal to trace (e.g., top.clk). Optional when --batch or --batch-file is used."),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    depth: int | None = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
    max_results: int | None = typer.Option(None, "--max-results", "-N", help="[C1 2026-06-28 LLM] Cap number of results per signal (None=unlimited). Returns truncated=true if any signal capped."),
    batch_file: str = typer.Option(None, "--batch-file", help="[B1 2026-07-03] Path to file with one signal per line (# comment, blank skipped)."),
    batch: str = typer.Option(None, "--batch", help="[B1 2026-07-03] Inline batch of signals, comma-separated (e.g., 'top.clk,top.rst_n')."),
    type_filter: str = typer.Option(None, "--type", help="[B2 2026-07-03] Filter by node kind, comma-separated (e.g., 'REG,PORT_IN')."),
    module_filter: str = typer.Option(None, "--module", help="[B2 2026-07-03] Filter by module name, fnmatch glob (e.g., 'uart_*')."),
    width_min: int = typer.Option(None, "--width-min", help="[B2 2026-07-03] Minimum signal bit width (inclusive)."),
    width_max: int = typer.Option(None, "--width-max", help="[B2 2026-07-03] Maximum signal bit width (inclusive)."),
    exclude: str = typer.Option(None, "--exclude", help="[B2 2026-07-03] Exclude by signal id, fnmatch glob (e.g., '*_int')."),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="[B4 2026-07-03] Load graph from saved snapshot tag (skip SV parse). Mutually exclusive with --file/--filelist."),
    no_cache: bool = typer.Option(False, "--no-cache", help="[A1 2026-07-04] Disable AST cache (default: cache enabled for repeat invocations)."),
) -> None:
    """Trace signal drivers (fanin)

    Single signal: sv_query trace fanin top.clk -f top.sv
    Batch:        sv_query trace fanin --batch 'top.clk,top.rst_n' -f top.sv
                  sv_query trace fanin --batch-file signals.txt -f top.sv
    """
    try:
        signals = _collect_signals(signal, batch_file, batch)
        # [B4 2026-07-03] Mutually exclusive: --from-snapshot vs --file/--filelist
        if from_snapshot and (file or filelist):
            raise ValueError("--from-snapshot is mutually exclusive with --file/--filelist")
        if from_snapshot:
            tracer = _load_tracer_from_snapshot(from_snapshot, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        elif filelist:
            tracer = UnifiedTracer(filelist=filelist, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        else:
            if file is None:
                raise ValueError("Either --file, --filelist, or --from-snapshot must be provided")
            with open(str(file)) as f:
                source = f.read()
            tracer = UnifiedTracer(sources={str(file): source}, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        _ = tracer.build_graph(use_cache=not no_cache)

        # [B1 2026-07-03] Batch mode: 1 tracer parse, N signals trace
        # [A3 2026-07-04] Per-signal try/except: failed signals go to errors[], continue on others
        signals_result = []
        per_signal_errors = []
        total_count = 0
        total_pre_filter = 0
        truncated_global = False
        for i, sig in enumerate(signals):
            try:
                result = tracer.trace_fanin(sig, depth=depth)
                drivers = []
                for d in result if hasattr(result, "__iter__") else []:
                    if hasattr(d, "id"):
                        drivers.append(_node_to_dict(d))
                # [B2 2026-07-03] Apply 5 filters
                drivers_pre = len(drivers)
                drivers = _apply_filters(
                    drivers,
                    type_filter=type_filter,
                    module_filter=module_filter,
                    width_min=width_min,
                    width_max=width_max,
                    exclude=exclude,
                )
                # [C1 2026-06-28 LLM] Cap per-signal results
                truncated = False
                if max_results is not None and len(drivers) > max_results:
                    drivers = drivers[:max_results]
                    truncated = True
                    truncated_global = True
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "drivers": drivers,
                    "count": len(drivers),
                    "pre_filter_count": drivers_pre,
                    "truncated": truncated,
                })
                total_count += len(drivers)
                total_pre_filter += drivers_pre
            except Exception as sig_err:
                # [A3 2026-07-04] Per-signal failure → record error, continue with others
                from src.cli.errors import make_error, code_for_exception
                err_data = make_error(
                    code_for_exception(sig_err), str(sig_err), command="trace_fanin",
                )
                per_signal_errors.append({
                    "signal": sig,
                    "index": i,
                    "error": err_data["error"],
                    "error_code": err_data.get("error_code", "E_INTERNAL"),
                })
                # Add empty entry to signals_result to preserve order
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "drivers": [],
                    "count": 0,
                    "pre_filter_count": 0,
                    "truncated": False,
                })

        data = {
            "ok": per_signal_errors == [],  # [A3] ok=False if any sig failed
            "command": "trace_fanin",
            "params": {"signals": signals, "file": str(file), "depth": depth, "max_results": max_results, "batch_file": batch_file, "batch": batch, "type": type_filter, "module": module_filter, "width_min": width_min, "width_max": width_max, "exclude": exclude, "from_snapshot": from_snapshot, "no_cache": no_cache},
            "result": {
                "signals": signals_result,
                "total_signals": len(signals),
                "total_count": total_count,
                "total_pre_filter": total_pre_filter,
                "truncated": truncated_global,
                "failed_signals": len(per_signal_errors),
            },
            "errors": per_signal_errors,
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data, human=human, tree=tree)

    except Exception as e:
        # [Phase 2 B2 2026-06-28] LLM-friendly error with stable code
        from src.cli.errors import make_error, code_for_exception
        data = make_error(code_for_exception(e), str(e), command="trace_fanin")
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@trace_app.command()
def fanout(
    signal: str = typer.Argument(None, help="Signal to trace (e.g., top.data). Optional when --batch or --batch-file is used."),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    depth: int | None = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    include_clock: bool = typer.Option(False, "--include-clock", help="[Req-12] Include CLOCK edges (sensitivity list)"),
    include_reset: bool = typer.Option(False, "--include-reset", help="[Req-12] Include RESET edges"),
    include_control: bool = typer.Option(False, "--include-control", help="[Req-12] Include CONTROL edges (always block refs)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
    max_results: int | None = typer.Option(None, "--max-results", "-N", help="[C1 2026-06-28 LLM] Cap number of results per signal (None=unlimited). Returns truncated=true if any signal capped."),
    batch_file: str = typer.Option(None, "--batch-file", help="[B1 2026-07-03] Path to file with one signal per line (# comment, blank skipped)."),
    batch: str = typer.Option(None, "--batch", help="[B1 2026-07-03] Inline batch of signals, comma-separated (e.g., 'top.clk,top.rst_n')."),
    type_filter: str = typer.Option(None, "--type", help="[B2 2026-07-03] Filter by node kind, comma-separated (e.g., 'REG,PORT_OUT')."),
    module_filter: str = typer.Option(None, "--module", help="[B2 2026-07-03] Filter by module name, fnmatch glob (e.g., 'sync_*')."),
    width_min: int = typer.Option(None, "--width-min", help="[B2 2026-07-03] Minimum signal bit width (inclusive)."),
    width_max: int = typer.Option(None, "--width-max", help="[B2 2026-07-03] Maximum signal bit width (inclusive)."),
    exclude: str = typer.Option(None, "--exclude", help="[B2 2026-07-03] Exclude by signal id, fnmatch glob (e.g., '*_int')."),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="[B4 2026-07-03] Load graph from saved snapshot tag (skip SV parse). Mutually exclusive with --file/--filelist."),
    no_cache: bool = typer.Option(False, "--no-cache", help="[A1 2026-07-04] Disable AST cache (default: cache enabled for repeat invocations)."),
) -> None:
    """Trace signal loads (fanout)

    [ADD 2026-06-11 Req-12 Issue 19] 默认只走 DRIVER+CONNECTION 边, 不含 CLOCK/RESET/CONTROL.
    用 --include-clock/reset/control flag 可加入. 完整视图请用 'visualize graph'.

    Single signal: sv_query trace fanout top.data -f top.sv
    Batch:        sv_query trace fanout --batch 'top.clk,top.data' -f top.sv
    """
    try:
        signals = _collect_signals(signal, batch_file, batch)
        # [B4 2026-07-03] Mutually exclusive: --from-snapshot vs --file/--filelist
        if from_snapshot and (file or filelist):
            raise ValueError("--from-snapshot is mutually exclusive with --file/--filelist")
        if from_snapshot:
            tracer = _load_tracer_from_snapshot(from_snapshot, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        elif filelist:
            tracer = UnifiedTracer(filelist=filelist, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        else:
            if file is None:
                raise ValueError("Either --file, --filelist, or --from-snapshot must be provided")
            with open(str(file)) as f:
                source = f.read()
            tracer = UnifiedTracer(sources={str(file): source}, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        _ = tracer.build_graph(use_cache=not no_cache)

        # [B1 2026-07-03] Batch mode
        # [A3 2026-07-04] Per-signal try/except: failed signals go to errors[], continue on others
        signals_result = []
        per_signal_errors = []
        total_count = 0
        total_pre_filter = 0
        truncated_global = False
        for i, sig in enumerate(signals):
            try:
                result = tracer.trace_fanout(
                    sig, depth=depth,
                    include_clock=include_clock,
                    include_reset=include_reset,
                    include_control=include_control,
                )
                loads = []
                for load in result if hasattr(result, "__iter__") else []:
                    if hasattr(load, "id"):
                        loads.append(_node_to_dict(load))
                # [B2 2026-07-03] Apply 5 filters
                loads_pre = len(loads)
                loads = _apply_filters(
                    loads,
                    type_filter=type_filter,
                    module_filter=module_filter,
                    width_min=width_min,
                    width_max=width_max,
                    exclude=exclude,
                )
                truncated = False
                if max_results is not None and len(loads) > max_results:
                    loads = loads[:max_results]
                    truncated = True
                    truncated_global = True
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "loads": loads,
                    "count": len(loads),
                    "pre_filter_count": loads_pre,
                    "truncated": truncated,
                })
                total_count += len(loads)
                total_pre_filter += loads_pre
            except Exception as sig_err:
                # [A3 2026-07-04] Per-signal failure → record error, continue
                from src.cli.errors import make_error, code_for_exception
                err_data = make_error(
                    code_for_exception(sig_err), str(sig_err), command="trace_fanout",
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
                    "loads": [],
                    "count": 0,
                    "pre_filter_count": 0,
                    "truncated": False,
                })

        data = {
            "ok": per_signal_errors == [],
            "command": "trace_fanout",
            "params": {"signals": signals, "file": str(file), "depth": depth, "max_results": max_results, "batch_file": batch_file, "batch": batch, "type": type_filter, "module": module_filter, "width_min": width_min, "width_max": width_max, "exclude": exclude, "from_snapshot": from_snapshot, "no_cache": no_cache},
            "result": {
                "signals": signals_result,
                "total_signals": len(signals),
                "total_count": total_count,
                "total_pre_filter": total_pre_filter,
                "truncated": truncated_global,
                "failed_signals": len(per_signal_errors),
            },
            "errors": per_signal_errors,
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data, human=human, tree=tree)

    except Exception as e:
        # [Phase 2 B2 2026-06-28] LLM-friendly error with stable code
        from src.cli.errors import make_error, code_for_exception
        data = make_error(
            code_for_exception(e),
            str(e),
            command="trace_fanout",
        )
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@trace_app.command()
def impact(
    signal: str = typer.Argument(None, help="Signal to analyze impact (e.g., top.rst_ni). Optional when --batch or --batch-file is used."),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    min_risk: float = typer.Option(30.0, "--min-risk", "-r", help="Minimum risk score for high-risk"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
    batch_file: str = typer.Option(None, "--batch-file", help="[B1 2026-07-03] Path to file with one signal per line (# comment, blank skipped)."),
    batch: str = typer.Option(None, "--batch", help="[B1 2026-07-03] Inline batch of signals, comma-separated (e.g., 'top.clk,top.rst_n')."),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="[B4 2026-07-03] Load graph from saved snapshot tag. Mutually exclusive with --file/--filelist."),
    no_cache: bool = typer.Option(False, "--no-cache", help="[A1 2026-07-04] Disable AST cache (default: cache enabled for repeat invocations)."),
) -> None:
    """Analyze impact of changing a signal

    Traces downstream loads (fanout) and assesses:
    - Impact paths and their risk levels
    - Coverage status (SVA/Covergroup)
    - Suggestions for safe modification

    Single signal: sv_query trace impact top.rst_ni -f top.sv
    Batch:        sv_query trace impact --batch 'top.clk,top.rst_ni' -f top.sv
    """
    try:
        signals = _collect_signals(signal, batch_file, batch)
        # [B4 2026-07-03] Mutually exclusive: --from-snapshot vs --file/--filelist
        if from_snapshot and (file or filelist):
            raise ValueError("--from-snapshot is mutually exclusive with --file/--filelist")
        if from_snapshot:
            tracer = _load_tracer_from_snapshot(from_snapshot, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        elif filelist:
            tracer = UnifiedTracer(filelist=filelist, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        else:
            if file is None:
                raise ValueError("Either --file, --filelist, or --from-snapshot must be provided")
            with open(str(file)) as f:
                source = f.read()
            tracer = UnifiedTracer(sources={str(file): source}, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        graph = tracer.build_graph(use_cache=not no_cache)

        # 提取 SVA 和 Coverage 信息 (shared across batch)
        if filelist or from_snapshot:
            # [BUGFIX 2026-07-03] c.sources 是 dict (不是 callable!), 之前 .sources() 错
            # [B4 2026-07-03] from_snapshot 时 c.sources 是空 dict (snapshot 不存 SV 源)
            sources_for_extractors = tracer._get_compiler().sources
        else:
            with open(str(file)) as f:
                source = f.read()
            sources_for_extractors = {str(file): source}
        sva_extractor = SVAExtractor(sources_for_extractors)
        sva_data = sva_extractor.extract()
        cov_extractor = CovergroupExtractor(sources_for_extractors)
        cov_data = cov_extractor.extract()

        sva_signals = set()
        for prop in sva_data.properties.values():
            sva_signals.update(prop.signals)

        cov_signals = set()
        for cg in cov_data:
            for cp in cg.coverpoints:
                cov_signals.add(cp.signal)

        # [B1 2026-07-03] Batch mode
        # [A3 2026-07-04] Per-signal try/except: failed signals go to errors[], continue on others
        signals_result = []
        per_signal_errors = []
        total_paths_all = 0
        total_high_risk_all = 0
        for i, sig in enumerate(signals):
            try:
                load_nodes = tracer.trace_fanout(sig, depth=None)
                paths = _build_impact_paths(sig, load_nodes, graph, sva_signals, cov_signals, min_risk)
                modules = _extract_modules(paths)
                risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
                paths.sort(key=lambda x: risk_order.get(x.get("risk", "LOW"), 2))
                high_risk_count = sum(1 for p in paths if p.get("risk") == "HIGH")
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "total_paths": len(paths),
                    "high_risk_count": high_risk_count,
                    "modules": modules,
                    "paths": paths,
                })
                total_paths_all += len(paths)
                total_high_risk_all += high_risk_count
            except Exception as sig_err:
                # [A3 2026-07-04] Per-signal failure → record error, continue
                from src.cli.errors import make_error, code_for_exception
                err_data = make_error(
                    code_for_exception(sig_err), str(sig_err), command="trace_impact",
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
                    "total_paths": 0,
                    "high_risk_count": 0,
                    "modules": [],
                    "paths": [],
                })

        data = {
            "ok": per_signal_errors == [],
            "command": "trace_impact",
            "params": {"signals": signals, "file": str(file), "min_risk": min_risk, "batch_file": batch_file, "batch": batch, "from_snapshot": from_snapshot, "no_cache": no_cache},
            "result": {
                "signals": signals_result,
                "total_signals": len(signals),
                "total_paths": total_paths_all,
                "total_high_risk_count": total_high_risk_all,
                "failed_signals": len(per_signal_errors),
            },
            "errors": per_signal_errors,
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data, human=human, tree=tree)

    except Exception as e:
        data = {"ok": False, "command": "trace_impact", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


def _build_impact_paths(
    signal: str, load_nodes: list, graph, sva_signals: set, cov_signals: set, min_risk: float
) -> list:
    """构建影响路径列表（从信号向下游追溯）

    Args:
        signal: 目标信号
        load_nodes: 下游负载节点列表（来自 trace_fanout）
        graph: 信号图
        sva_signals: 有 SVA 覆盖的信号集合
        cov_signals: 有 Covergroup 覆盖的信号集合
        min_risk: 最小风险分数（低于此值为 LOW）

    Returns:
        list: 影响路径列表
    """
    paths = []
    seen_paths = set()

    for node in load_nodes:
        node_id = node.id if hasattr(node, "id") else str(node)

        # 构建路径字符串
        path_nodes = [signal, node_id]

        # 递归向下追溯获取完整路径
        full_path = _get_full_load_path(node_id, graph, set())
        if len(full_path) > 1:
            path_nodes = [signal] + full_path

        path_key = " → ".join(path_nodes)
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)

        # 计算扇出
        downstream_fanout = len(
            [
                d
                for d in graph.successors(node_id)
                if graph.get_edge(node_id, d) and graph.get_edge(node_id, d).kind == EdgeKind.DRIVER
            ]
        )

        # 获取边的条件信息
        edge = graph.get_edge(signal, node_id)
        condition = edge.condition if edge and edge.condition else ""
        clock_domain = edge.clock_domain if edge and edge.clock_domain else ""
        assign_type = edge.assign_type if edge and edge.assign_type else ""

        # 计算风险分数
        risk_score = _calculate_risk(
            path_nodes, downstream_fanout, condition, clock_domain, sva_signals, cov_signals, signal
        )
        risk_level = _risk_to_level(risk_score, min_risk)

        # 检查覆盖状态
        target_covered = signal in sva_signals or signal in cov_signals
        node_covered = node_id in sva_signals or node_id in cov_signals

        coverage = {
            "sva": "covered" if node_id in sva_signals else "none",
            "covergroup": "covered" if node_id in cov_signals else "none",
        }

        # 生成建议
        suggestion = _generate_suggestion(path_nodes, risk_level, target_covered, node_covered, downstream_fanout)

        # 分类路径类型
        path_type = "combinational"
        if condition:
            path_type = "conditional"
        if assign_type == "nonblocking":
            path_type = "clocked"

        paths.append(
            {
                "path": path_nodes,
                "path_type": path_type,
                "risk": risk_level,
                "risk_score": risk_score,
                "fanout": downstream_fanout,
                "coverage": coverage,
                "condition": condition,
                "clock_domain": clock_domain,
                "suggestion": suggestion,
            }
        )

    return paths


def _get_full_load_path(signal_id: str, graph, visited: set) -> list:
    """递归获取完整的负载路径

    Args:
        signal_id: 当前信号 ID
        graph: 信号图
        visited: 已访问的节点集合（用于避免循环）

    Returns:
        list: 从当前信号开始的下游路径
    """
    if signal_id in visited:
        return []
    visited.add(signal_id)

    result = [signal_id]

    # 查找这个信号驱动的下游信号
    for succ in graph.successors(signal_id):
        edge = graph.get_edge(signal_id, succ)
        if edge and edge.kind == EdgeKind.DRIVER:
            sub_path = _get_full_load_path(succ, graph, visited)
            # 避免重复：只添加还没在 result 中的节点
            for node in sub_path[1:]:
                if node not in result:
                    result.append(node)

    return result


def _calculate_risk(
    path_nodes: list, fanout: int, condition: str, clock_domain: str, sva_signals: set, cov_signals: set, signal: str
) -> float:
    """计算路径风险分数

    Args:
        path_nodes: 路径节点列表
        fanout: 当前节点的扇出数
        condition: 驱动条件
        clock_domain: 时钟域
        sva_signals: SVA 覆盖的信号集合
        cov_signals: Covergroup 覆盖的信号集合
        signal: 目标信号

    Returns:
        float: 风险分数
    """
    score = 0.0

    # 路径长度风险
    score += len(path_nodes) * 5

    # 扇出风险
    score += fanout * 2

    # 无覆盖风险
    last_node = path_nodes[-1] if path_nodes else signal
    if last_node not in sva_signals and last_node not in cov_signals:
        score += 20

    # 高扇出风险
    if fanout > 10:
        score += 15
    elif fanout > 5:
        score += 10

    # 时钟/复位信号额外风险
    signal_name = signal.split(".")[-1].lower()
    if "clk" in signal_name or "clock" in signal_name:
        score += 20
    if "rst" in signal_name or "reset" in signal_name:
        score += 20

    # 驱动条件复杂性
    if condition:
        score += 10

    return score


def _risk_to_level(score: float, min_risk: float) -> str:
    """将风险分数转换为等级"""
    if score >= min_risk:
        return "HIGH"
    elif score >= min_risk * 0.6:
        return "MEDIUM"
    else:
        return "LOW"


def _generate_suggestion(path_nodes: list, risk: str, target_covered: bool, node_covered: bool, fanout: int) -> str:
    """生成优化建议"""
    suggestions = []

    signal_name = path_nodes[-1].split(".")[-1] if path_nodes else ""

    if risk == "HIGH":
        if not node_covered:
            suggestions.append("Add SVA or coverage for this critical path")
        if fanout > 10:
            suggestions.append(f"High fanout ({fanout}), consider local buffering")

    if "clk" in signal_name.lower() or "rst" in signal_name.lower():
        if fanout > 50:
            suggestions.append("Clock/reset network too heavy, consider clock gating or split reset")

    if not node_covered and len(path_nodes) > 2:
        suggestions.append("Long path without coverage, add intermediate checks")

    return "; ".join(suggestions)


def _extract_modules(paths: list) -> list:
    """提取所有涉及的模块"""
    modules = set()
    for path in paths:
        for node in path.get("path", []):
            parts = node.split(".")
            if len(parts) > 1:
                modules.add(parts[0])
    return sorted(list(modules))


# ==============================================================================
# Stage 3A: evidence 命令 - 召回 always/if 块完整源码
# ==============================================================================

@trace_app.command()
def evidence(
    signal: str = typer.Argument(None, help="Signal to query (e.g., top.q). Optional when --batch or --batch-file is used."),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    chain: bool = typer.Option(False, "--chain", "-c", help="Show evidence for entire driver chain"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly tree output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
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
        resolver, _graph, _sem = _build_evidence_resolver(file=file, filelist=filelist, strict=strict, preprocess_macros=preprocess_macros, from_snapshot=from_snapshot)

        # [B1 2026-07-03] Batch mode
        # [A3 2026-07-04] Per-signal try/except: failed signals go to errors[], continue on others
        signals_result = []
        per_signal_errors = []
        for i, sig in enumerate(signals):
            try:
                if chain:
                    evidences = resolver.resolve_chain(sig)
                    ev_dicts = [_evidence_to_dict(e) for e in evidences]
                else:
                    ev = resolver.resolve(sig)
                    ev_dicts = _evidence_to_dict(ev)
                signals_result.append({
                    "signal": sig,
                    "index": i,
                    "evidence": ev_dicts,
                })
            except Exception as sig_err:
                # [A3 2026-07-04] Per-signal failure → record error, continue
                from src.cli.errors import make_error, code_for_exception
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

        if json_output:
            output_json(data, pretty)
        else:
            # Text mode: render each signal's evidence with header
            for sig_entry in signals_result:
                sig = sig_entry["signal"]
                idx = sig_entry["index"] + 1
                total = len(signals)
                print(f"signal {idx}/{total}: {sig}")
                print("=" * 60)
                ev_data = {"signal": sig}
                if chain:
                    ev_data["evidence_chain"] = sig_entry["evidence"]
                else:
                    ev_data["evidence"] = sig_entry["evidence"]
                _output_evidence_text(ev_data)
                if idx < total:
                    print()

    except Exception as e:
        data = {"ok": False, "command": "trace_evidence", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


# [Stage 5] 移到 cli/_evidence_helpers.py,5 个命令共用


def _output_evidence_text(data: dict) -> None:
    """人友好文本输出"""
    signal = data.get("signal", "")
    print(f"Signal: {signal}")
    print("=" * 60)

    chain = data.get("evidence_chain")
    if chain is not None:
        # driver chain mode
        if not chain:
            print("  (no evidence found)")
            return
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
