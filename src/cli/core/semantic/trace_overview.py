# ==============================================================================
# trace_overview.py — overview 复合命令 (dataflow + controlflow + evidence)
# ==============================================================================
"""overview 复合命令 (dataflow + controlflow + evidence)

[iter_253 T3-3] 从 `semantic/trace.py` (1,835 行) 拆出: 该文件同时承载 fanin/fanout/
impact/evidence/overview 五个命令 + DOT 生成 + 多种文本渲染。本模块只放 overview 复合命令 (dataflow + controlflow + evidence)。
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
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer

logger = logging.getLogger(__name__)


# ==========================================================================
# trace overview — B 复合命令: 1 命令出 dataflow + controlflow + evidence
# ==========================================================================

def overview(
    from_signal: str = typer.Argument(..., help="Source signal (e.g., top.a)"),
    to_signal: str = typer.Argument(..., help="Target signal (e.g., top.b)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default)"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    max_paths: int = typer.Option(100, "--max-paths", "-n", help="Maximum dataflow paths"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly output"),
) -> None:
    """[B 复合命令] 1 命令出 A→B 完整 view: dataflow + controlflow + evidence

    示例:
      sv_query trace overview top.a top.b -f top.sv --human
      sv_query trace overview top.a top.b -f top.sv --json | jq
    """
    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    # ── 公共 tracer (编译一次, 复用) ──
    from cli._common import _build_tracer as _bt
    from cli._common import handle_compilation_error
    from cli._evidence_helpers import (
        evidence_to_dict,
    )
    from cli._evidence_helpers import (
        make_resolver as _make_evidence_resolver,
    )
    from trace.core.compiler import CompilationError, SVCompiler
    from trace.core.graph.analyzer.controlflow_analyzer import ControlFlowAnalyzer
    from trace.core.graph.dataflow import DataFlowGraph
    from trace.core.graph_builder import GraphBuilder
    from trace.core.semantic_adapter import SemanticAdapter

    try:
        tracer = _bt(
            file=file, filelist=filelist,
            log_level=log_level,
            preprocess_macros=preprocess_macros,
        )
        graph = tracer.build_graph()
        sources = tracer._sources
    except CompilationError as e:
        handle_compilation_error(e)
        return

    evidence_resolver = _make_evidence_resolver(graph, tracer._get_adapter())

    # ── 1. dataflow (A→B path) ──
    df_data = {}
    df_error = None
    try:
        dfg = DataFlowGraph(tracer._graph, tracer._module_graph)
        df_result = dfg.analyze(from_signal, to_signal, max_paths=max_paths)
        paths_data = []
        for path in df_result.paths:
            segs = []
            for seg in path.segments:
                seg_dict = {
                    "from_signal": seg.from_signal,
                    "to_signal": seg.to_signal,
                    "driver": seg.driver,
                    "condition": seg.condition,
                    "timing": seg.timing,
                    "assign_type": seg.assign_type,
                    "distance": seg.distance,
                    "evidence": evidence_to_dict(evidence_resolver.resolve(seg.to_signal)),
                }
                segs.append(seg_dict)
            paths_data.append({
                "path_id": path.path_id,
                "segments": segs,
                "distance": path.distance,
                "has_conditional": path.has_conditional,
                "latency_cycles": path.latency_cycles,
                "is_async_crossing": path.is_async_crossing,
                "latency_note": path.latency_note,
            })
        df_data = {
            "from_signal": df_result.from_signal,
            "to_signal": df_result.to_signal,
            "is_reachable": df_result.is_reachable,
            "paths_count": df_result.paths_count,
            "primary_latency_cycles": df_result.primary_latency_cycles,
            "primary_is_async": df_result.primary_is_async,
            "clock_domain": df_result.clock_domain,
            "all_conditions": df_result.all_conditions,
            "paths": paths_data,
        }
    except ValueError as e:
        df_error = str(e)
    except Exception as e:
        df_error = f"{type(e).__name__}: {e}"

    # ── 2. controlflow (A 和 B 各自的条件) ──
    cf_data = {}
    cf_errors = []

    compiler = SVCompiler(sources)
    semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)
    graph_builder = GraphBuilder(semantic_adapter)
    graph_builder.graph = graph
    graph_builder._module_graph = tracer._module_graph
    cf_analyzer = ControlFlowAnalyzer(graph_builder)

    for sig_label, sig_name in [("from", from_signal), ("to", to_signal)]:
        try:
            cf_result = cf_analyzer.analyze(sig_name)
            drivers_data = []
            for cd in cf_result.conditioned_drivers:
                conds = []
                for cond in cd.conditions:
                    cond_dict = {
                        "expr": cond.expr,
                        "edge": {
                            "src": cond.edge.src,
                            "dst": cond.edge.dst,
                            "kind": cond.edge.kind.name if hasattr(cond.edge.kind, "name") else str(cond.edge.kind),
                            "condition": cond.edge.condition,
                        },
                        "evidence": evidence_to_dict(evidence_resolver.resolve(cond.edge.dst)),
                    }
                    conds.append(cond_dict)
                drivers_data.append({"to_node": cd.to_node, "conditions": conds})
            cf_data[sig_label] = {
                "signal": cf_result.signal,
                "conditioned_drivers": drivers_data,
                "warnings": cf_result.warnings,
            }
        except Exception as e:
            cf_errors.append({"signal": sig_name, "error": str(e)})

    # ── 3. evidence (关键路径节点) ──
    ev_signals = set()
    # 从 dataflow 中间信号中采样关键节点
    if df_data and df_data.get("paths"):
        for path in df_data["paths"][:3]:  # 前 3 条路径
            for seg in path.get("segments", []):
                ev_signals.add(seg["to_signal"])

    ev_data = {}
    for sig in sorted(ev_signals):
        try:
            ev = evidence_resolver.resolve(sig)
            ev_data[sig] = evidence_to_dict(ev)
        except Exception as e:
            logger.warning("%s: 忽略 Exception: %s", __name__, e)

    # ── 汇编输出 ──
    data = {
        "ok": df_error is None and not cf_errors,
        "command": "trace_overview",
        "params": {
            "from_signal": from_signal,
            "to_signal": to_signal,
            "file": str(file) if file else str(sources.get(next(iter(sources)), "")) if sources else filelist,
            "max_paths": max_paths,
        },
        "result": {
            "dataflow": df_data,
            "controlflow": cf_data,
            "evidence": ev_data,
        },
        "errors": ([df_error] if df_error else []) + [e["error"] for e in cf_errors],
    }

    if json_output:
        indent = 2 if pretty else None
        print(json.dumps(data, indent=indent, ensure_ascii=False))
    else:
        _output_overview_text(data, human=human)


def _output_overview_text(data: dict, human: bool = False) -> None:
    """纯文本输出 B 复合命令结果"""
    result = data.get("result", {})
    params = data.get("params", {})
    from_sig = params.get("from_signal", "?")
    to_sig = params.get("to_signal", "?")
    errors = data.get("errors", [])

    # ── 标题 ──
    print(f"{'='*60}")
    print(f"📊 Overview: {from_sig} → {to_sig}")
    print(f"{'='*60}")

    # ── 段 1: dataflow ──
    df = result.get("dataflow", {})
    print("\n── 1. DataFlow ──")
    if not df:
        print(f"  ⚠️  {errors[0] if errors else 'No dataflow result'}")
    elif not df.get("is_reachable"):
        print("  ❌ Not reachable")
    else:
        latency = df.get("primary_latency_cycles", "?")
        async_flag = df.get("primary_is_async", False)
        paths_count = df.get("paths_count", 0)
        clock = df.get("clock_domain", "?")
        conditions = df.get("all_conditions", [])

        print("  Status: ✅ Reachable")
        print(f"  Latency: {latency} cycle(s)" + (" ⚡ ASYNC" if async_flag else ""))
        print(f"  Clock:   {clock}")
        print(f"  Paths:   {paths_count}")
        if conditions:
            print(f"  Conditions: {'; '.join(conditions[:5])}")

        # 路径详情（human 模式下展开）
        if human:
            from cli._evidence_helpers import format_dataflow_human
            print("\n" + format_dataflow_human(from_sig, to_sig, df.get("paths", []), tree=False))
        else:
            paths = df.get("paths", [])
            if paths:
                print(f"\n  Top path ({paths[0].get('path_id', 0)}):")
                for seg in paths[0].get("segments", []):
                    cond = f" [{seg['condition']}]" if seg.get("condition") else ""
                    print(f"    {seg['from_signal']} → {seg['to_signal']}{cond}  ({seg['timing']})")
                if len(paths) > 1:
                    print(f"  ... and {len(paths)-1} more path(s)")

    # ── 段 2: controlflow (from_signal) ──
    cf = result.get("controlflow", {})
    for label, title in [("from", "Source Signal"), ("to", "Target Signal")]:
        cf_entry = cf.get(label, {})
        sig_name = cf_entry.get("signal", label)
        print(f"\n── 2. ControlFlow ({title}: {sig_name}) ──")

        if not cf_entry:
            print("  (no controlflow data)")
            continue

        drivers = cf_entry.get("conditioned_drivers", [])
        if not drivers:
            print("  (no conditioned drivers)")
        else:
            for cd in drivers:
                cd.get("to_node", "?")
                conditions = cd.get("conditions", [])
                for cond in conditions:
                    expr = cond.get("expr", "?")
                    edge = cond.get("edge", {})
                    src = edge.get("src", "?")
                    dst = edge.get("dst", "?")
                    print(f"  when {expr}: {src} → {dst}")

                    # evidence 小摘要
                    ev = cond.get("evidence", {})
                    if ev and human:
                        loc = ev.get("source_location", {})
                        if loc.get("line_start"):
                            file_short = loc.get("file", "").split("/")[-1]
                            print(f"    📍 {file_short}:{loc['line_start']}-{loc.get('line_end', '')}")

        warnings = cf_entry.get("warnings", [])
        if warnings:
            for w in warnings:
                print(f"  ⚠️  {w}")

    # ── 段 3: evidence (关键路径节点源码) ──
    ev = result.get("evidence", {})
    if ev:
        print(f"\n── 3. Evidence ({len(ev)} key signals) ──")
        for sig, ev_dict in sorted(ev.items()):
            if not ev_dict:
                continue
            loc = ev_dict.get("source_location", {})
            if loc:
                file_short = loc.get("file", "").split("/")[-1]
                print(f"\n  📍 {sig}")
                print(f"     {file_short}:{loc.get('line_start','?')}")
            if human:
                always = ev_dict.get("enclosing_always", {})
                if always and always.get("text"):
                    print("     always block:")
                    for line in always["text"].split("\n")[:6]:
                        print(f"       {line}")
                    if len(always["text"].split("\n")) > 6:
                        print("       ...")

    # ── errors ──
    if errors:
        print(f"\n{'='*60}")
        print("⚠️  Errors:")
        for e in errors[:5]:
            print(f"  - {e}")
    print(f"{'='*60}")
