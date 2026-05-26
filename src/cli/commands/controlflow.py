#==============================================================================
# controlflow.py - controlflow analysis subcommand
#==============================================================================

import sys
import json
from pathlib import Path
from typing import Optional, List

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.analyzer.controlflow_analyzer import (
    ControlFlowAnalyzer,
    ControlFlowAnalysis,
    ConditionedDriver,
)
from trace.core.graph_builder import GraphBuilder


def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict) -> None:
    """纯文本输出"""
    command = data.get("command", "")
    result = data.get("result", {})

    if command == "controlflow":
        signal = result.get("signal", "")
        conditioned_drivers = result.get("conditioned_drivers", [])
        warnings = result.get("warnings", [])

        print(f"ControlFlow Analysis: {signal}")

        if not conditioned_drivers:
            print(f"  (no conditional drivers found)")
        else:
            for cd in conditioned_drivers:
                print(f"\n  Conditional Drivers:")
                for cond in cd.get("conditions", []):
                    expr = cond.get("expr", "")
                    edge = cond.get("edge", {})
                    src = edge.get("src", "")
                    to = edge.get("dst", "")
                    print(f"    when {expr}: {src} → {to}")

        if warnings:
            print(f"\n  Warnings:")
            for w in warnings:
                print(f"    ⚠️  {w}")


controlflow_app = typer.Typer(help="Analyze control flow conditions for signals")


@controlflow_app.command("analyze")
def analyze(
    signal: str = typer.Argument(..., help="Signal to analyze (e.g., top.q)"),
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Analyze control flow conditions for a signal"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        # Build GraphBuilder for analyzer
        from trace.core.semantic_adapter import SemanticAdapter
        from trace.core.compiler import SVCompiler
        compiler = SVCompiler({str(file): source})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        analyzer = ControlFlowAnalyzer(graph_builder)
        result = analyzer.analyze(signal)

        # Build output data
        drivers_data = []
        for cd in result.conditioned_drivers:
            conds_data = []
            for cond in cd.conditions:
                conds_data.append({
                    "expr": cond.expr,
                    "edge": {
                        "src": cond.edge.src,
                        "dst": cond.edge.dst,
                        "kind": cond.edge.kind.name if hasattr(cond.edge.kind, 'name') else str(cond.edge.kind),
                        "condition": cond.edge.condition,
                    }
                })
            drivers_data.append({
                "to_node": cd.to_node,
                "conditions": conds_data,
            })

        data = {
            "ok": True,
            "command": "controlflow",
            "params": {
                "signal": signal,
                "file": str(file),
            },
            "result": {
                "signal": result.signal,
                "conditioned_drivers": drivers_data,
                "warnings": result.warnings,
            },
            "errors": []
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {
            "ok": False,
            "command": "controlflow",
            "error": str(e),
            "errors": [str(e)]
        }
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)


@controlflow_app.command("list-conditioned")
def list_conditioned(
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """List all signals with conditional drivers"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        from trace.core.semantic_adapter import SemanticAdapter
        from trace.core.compiler import SVCompiler
        compiler = SVCompiler({str(file): source})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        analyzer = ControlFlowAnalyzer(graph_builder)
        signals = analyzer.find_conditioned_signals()

        data = {
            "ok": True,
            "command": "controlflow",
            "subcommand": "list-conditioned",
            "params": {"file": str(file)},
            "result": {
                "signals": signals,
                "count": len(signals),
            },
            "errors": []
        }

        if json_output:
            output_json(data, pretty)
        else:
            print(f"Signals with conditional drivers ({len(signals)}):")
            for sig in signals:
                print(f"  - {sig}")

    except Exception as e:
        data = {
            "ok": False,
            "command": "controlflow",
            "subcommand": "list-conditioned",
            "error": str(e),
            "errors": [str(e)]
        }
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)


@controlflow_app.command("conditions")
def get_conditions(
    signal: str = typer.Argument(..., help="Signal to get conditions for"),
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Get all conditions for a signal"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        from trace.core.semantic_adapter import SemanticAdapter
        from trace.core.compiler import SVCompiler
        compiler = SVCompiler({str(file): source})
        semantic_adapter = SemanticAdapter(compiler.get_root(), compiler)

        graph_builder = GraphBuilder(semantic_adapter)
        graph_builder.graph = graph
        graph_builder._module_graph = tracer._module_graph

        analyzer = ControlFlowAnalyzer(graph_builder)
        conditions = analyzer.get_conditions_for_signal(signal)

        data = {
            "ok": True,
            "command": "controlflow",
            "subcommand": "conditions",
            "params": {
                "signal": signal,
                "file": str(file),
            },
            "result": {
                "signal": signal,
                "conditions": conditions,
                "count": len(conditions),
            },
            "errors": []
        }

        if json_output:
            output_json(data, pretty)
        else:
            print(f"Conditions for {signal} ({len(conditions)}):")
            for cond in conditions:
                print(f"  - {cond}")

    except Exception as e:
        data = {
            "ok": False,
            "command": "controlflow",
            "subcommand": "conditions",
            "error": str(e),
            "errors": [str(e)]
        }
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)