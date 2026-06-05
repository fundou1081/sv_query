# ==============================================================================
# dataflow.py - dataflow path analysis subcommand
# ==============================================================================

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.graph.dataflow import DataFlowGraph
from trace.unified_tracer import UnifiedTracer

# [Stage 5] evidence helper (可选 --evidence flag)
from cli._evidence_helpers import (  # noqa: E402
    make_resolver as _make_evidence_resolver,
    evidence_to_dict,
    evidence_summary_indented,
    format_dataflow_human as _format_dataflow_human,
)


def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict, human: bool = False) -> None:
    """纯文本输出 - 与 trace.py 保持一致格式

    Args:
        data: 命令返回的 dict
        human: True 时用人类友好箭头格式 (--human flag)
    """
    command = data.get("command", "")
    result = data.get("result", {})

    if command == "dataflow":
        if human:
            print(_format_dataflow_human(
                result.get("from_signal", ""),
                result.get("to_signal", ""),
                result.get("paths", []),
            ))
            return
        from_sig = result.get("from_signal", "")
        to_sig = result.get("to_signal", "")
        is_reachable = result.get("is_reachable", False)
        paths_count = result.get("paths_count", 0)
        clock_domain = result.get("clock_domain") or "(none)"
        timing_risk = result.get("timing_risk", "safe")
        intermediate = result.get("intermediate_signals", [])

        print(f"DataFlow: {from_sig} → {to_sig}")
        print(f"  Reachable: {is_reachable}")
        print(f"  Paths: {paths_count}")
        print(f"  Clock Domain: {clock_domain}")
        print(f"  Timing Risk: {timing_risk}")

        if intermediate:
            print(f"  Intermediate Signals ({len(intermediate)}):")
            for sig in sorted(intermediate)[:10]:
                print(f"    - {sig}")
            if len(intermediate) > 10:
                print(f"    ... and {len(intermediate) - 10} more")

        paths = result.get("paths", [])
        if paths:
            print("\n  Path Details:")
            for path in paths[:5]:
                path_id = path.get("path_id", 0)
                distance = path.get("distance", 0)
                has_cond = path.get("has_conditional", False)
                cond_str = " [conditional]" if has_cond else ""
                print(f"\n    Path {path_id}: distance={distance}{cond_str}")

                segments = path.get("segments", [])
                for seg in segments:
                    from_s = seg.get("from_signal", "")
                    to_s = seg.get("to_signal", "")
                    driver = seg.get("driver") or "(none)"
                    condition = seg.get("condition")
                    timing = seg.get("timing") or "(none)"
                    assign_type = seg.get("assign_type", "continuous")

                    print(f"      {from_s} → {to_s}")
                    if driver and driver != "(none)":
                        print(f"        driver: {driver}")
                    if condition:
                        cond_short = condition[:60] + "..." if len(condition) > 60 else condition
                        print(f"        condition: {cond_short}")
                    print(f"        timing: {timing}")
                    print(f"        assign: {assign_type}")
                    # [Stage 5] 可选 evidence 1 行摘要 (贴在 assign 下方)
                    if data.get("params", {}).get("evidence"):
                        summary = evidence_summary_indented(seg.get("evidence"))
                        if summary:
                            print(summary)

                if len(segments) > 5:
                    print(f"      ... and {len(segments) - 5} more segments")

            if len(paths) > 5:
                print(f"\n    ... and {len(paths) - 5} more paths")


dataflow_app = typer.Typer(help="Analyze dataflow paths between signals")


@dataflow_app.command("analyze")
def analyze(
    from_signal: str = typer.Argument(..., help="Source signal (e.g., top.clk)"),
    to_signal: str = typer.Argument(..., help="Target signal (e.g., top.data_out)"),
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    max_paths: int = typer.Option(100, "--max-paths", "-n", help="Maximum number of paths to return"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    evidence: bool = typer.Option(False, "--evidence", "-e", help="Include source evidence for each segment (optional)"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
) -> None:
    """Analyze dataflow path from source signal to target signal"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        _ = tracer.build_graph()

        dfg = DataFlowGraph(tracer._graph, tracer._module_graph)
        result = dfg.analyze(from_signal, to_signal, max_paths=max_paths)

        # [Stage 5] (可选) evidence 召回 - 每个 segment 的 to_signal 独立解析
        evidence_resolver = None
        if evidence:
            evidence_resolver = _make_evidence_resolver(tracer._graph, tracer._get_adapter())

        paths_data = []
        for path in result.paths:
            segments_data = []
            for seg in path.segments:
                seg_dict = {
                    "from_signal": seg.from_signal,
                    "to_signal": seg.to_signal,
                    "driver": seg.driver,
                    "condition": seg.condition,
                    "timing": seg.timing,
                    "assign_type": seg.assign_type,
                    "distance": seg.distance,
                }
                if evidence_resolver is not None:
                    seg_dict["evidence"] = evidence_to_dict(evidence_resolver.resolve(seg.to_signal))
                segments_data.append(seg_dict)
            paths_data.append(
                {
                    "path_id": path.path_id,
                    "segments": segments_data,
                    "distance": path.distance,
                    "has_conditional": path.has_conditional,
                }
            )

        data = {
            "ok": True,
            "command": "dataflow",
            "params": {"from_signal": from_signal, "to_signal": to_signal, "file": str(file), "max_paths": max_paths, "evidence": evidence},
            "result": {
                "from_signal": result.from_signal,
                "to_signal": result.to_signal,
                "is_reachable": result.is_reachable,
                "paths_count": result.paths_count,
                "intermediate_signals": sorted(result.intermediate_signals),
                "all_conditions": result.all_conditions,
                "clock_domain": result.clock_domain,
                "timing_risk": result.timing_risk,
                "paths": paths_data,
            },
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data, human=human)

    except Exception as e:
        data = {"ok": False, "command": "dataflow", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1) from None
