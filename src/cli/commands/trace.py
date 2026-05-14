#==============================================================================
# trace.py - trace fanin / fanout subcommands
#============================================================================

import sys
import json
from pathlib import Path
from typing import Optional

import typer
import pyslang

# 添加 src 到 path 以便 import trace
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.unified_tracer import UnifiedTracer

# JSON 输出格式化函数
def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict) -> None:
    """纯文本输出"""
    command = data.get("command", "")
    result = data.get("result", {})

    if command == "trace_fanin":
        signal = data.get("params", {}).get("signal", "")
        drivers = result.get("drivers", [])
        print(f"Fanin of '{signal}':")
        if not drivers:
            print("  (no drivers)")
        for d in drivers:
            dist = d.get("distance", "")
            kind = d.get("kind", "")
            print(f"  [{dist}] {d['id']} ({kind})")

    elif command == "trace_fanout":
        signal = data.get("params", {}).get("signal", "")
        loads = result.get("loads", [])
        print(f"Fanout of '{signal}':")
        if not loads:
            print("  (no loads)")
        for l in loads:
            dist = l.get("distance", "")
            kind = l.get("kind", "")
            print(f"  [{dist}] {l['id']} ({kind})")


trace_app = typer.Typer(help="Trace signal drivers (fanin) or loads (fanout)")


@trace_app.command()
def fanin(
    signal: str = typer.Argument(..., help="Signal to trace (e.g., top.clk)"),
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    depth: Optional[int] = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Trace signal drivers (fanin)"""
    try:
        tree = pyslang.SyntaxTree.fromFile(str(file))
        tracer = UnifiedTracer(trees={str(file): tree})
        _ = tracer.build_graph()

        result = tracer.trace_fanin(signal, depth=depth)

        # 转换结果为可序列化格式
        drivers = []
        for d in result if hasattr(result, '__iter__') else []:
            if hasattr(d, 'id'):
                drivers.append({
                    "id": d.id,
                    "kind": getattr(d, 'kind', 'UNKNOWN').name if hasattr(d, 'kind') else 'UNKNOWN',
                    "distance": getattr(d, 'distance', 1) if hasattr(d, 'distance') else 1
                })

        data = {
            "ok": True,
            "command": "trace_fanin",
            "params": {"signal": signal, "file": str(file), "depth": depth},
            "result": {"drivers": drivers},
            "errors": []
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {
            "ok": False,
            "command": "trace_fanin",
            "error": str(e),
            "errors": [str(e)]
        }
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1)


@trace_app.command()
def fanout(
    signal: str = typer.Argument(..., help="Signal to trace (e.g., top.data)"),
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    depth: Optional[int] = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Trace signal loads (fanout)"""
    try:
        tree = pyslang.SyntaxTree.fromFile(str(file))
        tracer = UnifiedTracer(trees={str(file): tree})
        _ = tracer.build_graph()

        result = tracer.trace_fanout(signal, depth=depth)

        # 转换结果为可序列化格式
        loads = []
        for l in result if hasattr(result, '__iter__') else []:
            if hasattr(l, 'id'):
                loads.append({
                    "id": l.id,
                    "kind": getattr(l, 'kind', 'UNKNOWN').name if hasattr(l, 'kind') else 'UNKNOWN',
                    "distance": getattr(l, 'distance', 1) if hasattr(l, 'distance') else 1
                })

        data = {
            "ok": True,
            "command": "trace_fanout",
            "params": {"signal": signal, "file": str(file), "depth": depth},
            "result": {"loads": loads},
            "errors": []
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {
            "ok": False,
            "command": "trace_fanout",
            "error": str(e),
            "errors": [str(e)]
        }
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1)