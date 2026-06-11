# ==============================================================================
# controlflow.py - controlflow analysis subcommand
# ==============================================================================

import json
import sys
from pathlib import Path

import typer
from cli._common import _build_tracer, handle_compilation_error  # [ADD 2026-06-11 Req-9]
from trace.core.compiler import CompilationError  # [ADD 2026-06-11 任务3]

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.graph.analyzer.controlflow_analyzer import (
    ControlFlowAnalyzer,
)
from trace.core.graph_builder import GraphBuilder
from trace.unified_tracer import UnifiedTracer

# [Stage 5] evidence helper (可选 --evidence flag)
from cli._evidence_helpers import (  # noqa: E402
    make_resolver as _make_evidence_resolver,
    evidence_to_dict,
    evidence_summary_indented,
    format_controlflow_human as _format_controlflow_human,
)

def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))

def _is_constant(src: str) -> bool:
    """检查是否为常量（字面量）"""
    if not src:
        return False
    return not src[0].isalpha() and not src.startswith("_")

def output_text(data: dict, human: bool = False, tree: bool = False) -> None:
    """纯文本输出

    Args:
        data: 命令返回的 dict
        human: True 时用人类友好箭头格式 (--human flag)
    """
    command = data.get("command", "")
    result = data.get("result", {})

    if command == "controlflow":
        if human:
            print(_format_controlflow_human(
                result.get("signal", ""),
                result.get("conditioned_drivers", []),
                tree=tree,
            ))
            return
        signal = result.get("signal", "")
        conditioned_drivers = result.get("conditioned_drivers", [])
        warnings = result.get("warnings", [])

        print(f"ControlFlow Analysis: {signal}")

        if not conditioned_drivers:
            print("  (no conditional drivers found)")
        else:
            for cd in conditioned_drivers:
                print("\n  Conditional Drivers:")
                for cond in cd.get("conditions", []):
                    expr = cond.get("expr", "")
                    edge = cond.get("edge", {})
                    src = edge.get("src", "")
                    to = edge.get("dst", "")
                    # 标注常量
                    if _is_constant(src):
                        src = f"CONST {src}"
                    print(f"    when {expr}: {src} → {to}")
                    # [Stage 5] 可选 evidence 1 行摘要 (条件后缩进显示)
                    if data.get("params", {}).get("evidence"):
                        summary = evidence_summary_indented(cond.get("evidence"))
                        if summary:
                            print(f"      {summary.lstrip()}")

        if warnings:
            print("\n  Warnings:")
            for w in warnings:
                print(f"    ⚠️  {w}")

controlflow_app = typer.Typer(help="Analyze control flow conditions for signals")

@controlflow_app.command("analyze")
def analyze(
    signal: str = typer.Argument(..., help="Signal to analyze (e.g., top.q)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(False, "--strict", help="Strict mode: elaboration error 立即 raise (默认 non-strict)"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    evidence: bool = typer.Option(False, "--evidence", "-e", help="Include source evidence for each condition (optional)"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
) -> None:
    """Analyze control flow conditions for a signal"""
    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    try:
        tracer = _build_tracer(
            file=file,
            filelist=filelist,
            strict=strict,
            log_level=log_level,
        )
        graph = tracer.build_graph()
        sources = tracer._sources
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    # Build GraphBuilder for analyzer
    from trace.core.compiler import SVCompiler
    from trace.core.semantic_adapter import SemanticAdapter

    # [FIX 2026-06-12 Req-15] 跟 caller 的 strict 一致, 避免 non-strict 仍报 CompilationError
    compiler = SVCompiler(sources, strict=strict)
    semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

    graph_builder = GraphBuilder(semantic_adapter)
    graph_builder.graph = graph
    graph_builder._module_graph = tracer._module_graph

    analyzer = ControlFlowAnalyzer(graph_builder)
    result = analyzer.analyze(signal)

    # [Stage 5] (可选) evidence 召回 - 每个 condition 的 to_node 独立解析
    evidence_resolver = None
    if evidence:
        evidence_resolver = _make_evidence_resolver(graph, tracer._get_adapter())

    # Build output data
    drivers_data = []
    for cd in result.conditioned_drivers:
        conds_data = []
        for cond in cd.conditions:
            cond_dict = {
                "expr": cond.expr,
                "edge": {
                    "src": cond.edge.src,
                    "dst": cond.edge.dst,
                    "kind": cond.edge.kind.name if hasattr(cond.edge.kind, "name") else str(cond.edge.kind),
                    "condition": cond.edge.condition,
                },
            }
            if evidence_resolver is not None:
                cond_dict["evidence"] = evidence_to_dict(evidence_resolver.resolve(cond.edge.dst))
            conds_data.append(cond_dict)
        drivers_data.append(
            {
                "to_node": cd.to_node,
                "conditions": conds_data,
            }
        )

    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式 params 输出
    params_file = file if file else (list(sources.keys())[0] if sources else filelist)
    data = {
        "ok": True,
        "command": "controlflow",
        "params": {
            "signal": signal,
            "file": str(params_file),
            "evidence": evidence,
        },
        "result": {
            "signal": result.signal,
            "conditioned_drivers": drivers_data,
            "warnings": result.warnings,
        },
        "errors": [],
    }

    if json_output:
        output_json(data, pretty)
    else:
        output_text(data, human=human, tree=tree)

@controlflow_app.command("list-conditioned")
def list_conditioned(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(False, "--strict", help="Strict mode: elaboration error 立即 raise (默认 non-strict)"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """List all signals with conditional drivers"""
    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    try:
        tracer = _build_tracer(
            file=file,
            filelist=filelist,
            strict=strict,
            log_level=log_level,
        )
        graph = tracer.build_graph()
        sources = tracer._sources
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    from trace.core.compiler import SVCompiler
    from trace.core.semantic_adapter import SemanticAdapter

    compiler = SVCompiler(sources, strict=strict)
    semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

    graph_builder = GraphBuilder(semantic_adapter)
    graph_builder.graph = graph
    graph_builder._module_graph = tracer._module_graph

    analyzer = ControlFlowAnalyzer(graph_builder)
    signals = analyzer.find_conditioned_signals()

    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式 params 输出
    params_file = file if file else (list(sources.keys())[0] if sources else filelist)
    data = {
        "ok": True,
        "command": "controlflow",
        "subcommand": "list-conditioned",
        "params": {"file": str(params_file)},
        "result": {
            "signals": signals,
            "count": len(signals),
        },
        "errors": [],
    }

    if json_output:
        output_json(data, pretty)
    else:
        print(f"Signals with conditional drivers ({len(signals)}):")
        for sig in signals:
            print(f"  - {sig}")

@controlflow_app.command("conditions")
def get_conditions(
    signal: str = typer.Argument(..., help="Signal to get conditions for"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(False, "--strict", help="Strict mode: elaboration error 立即 raise (默认 non-strict)"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Get all conditions for a signal"""
    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    try:
        tracer = _build_tracer(
            file=file,
            filelist=filelist,
            strict=strict,
            log_level=log_level,
        )
        graph = tracer.build_graph()
        sources = tracer._sources
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return

    from trace.core.compiler import SVCompiler
    from trace.core.semantic_adapter import SemanticAdapter

    compiler = SVCompiler(sources, strict=strict)
    semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

    graph_builder = GraphBuilder(semantic_adapter)
    graph_builder.graph = graph
    graph_builder._module_graph = tracer._module_graph

    analyzer = ControlFlowAnalyzer(graph_builder)
    conditions = analyzer.get_conditions_for_signal(signal)

    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式 params 输出
    params_file = file if file else (list(sources.keys())[0] if sources else filelist)
    data = {
        "ok": True,
        "command": "controlflow",
        "subcommand": "conditions",
        "params": {
            "signal": signal,
            "file": str(params_file),
        },
        "result": {
            "signal": signal,
            "conditions": conditions,
            "count": len(conditions),
        },
        "errors": [],
    }

    if json_output:
        output_json(data, pretty)
    else:
        print(f"Conditions for {signal} ({len(conditions)}):")
        for cond in conditions:
            print(f"  - {cond}")

