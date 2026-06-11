# ==============================================================================
# risk.py - 风险分析命令
# ==============================================================================
"""
Usage:
  python run_cli.py risk analyze top.sv
  python run_cli.py risk analyze top.sv --json
  python run_cli.py risk top --module top
"""

import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
_project_root = _src_dir.parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
import warnings

import typer

warnings.filterwarnings("ignore")

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.models import NodeKind
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer

# [Stage 5] evidence helper (可选 --evidence flag)
from cli._evidence_helpers import (  # noqa: E402
    make_resolver as _make_evidence_resolver,
    evidence_to_dict,
    evidence_summary_indented,
)

risk_app = typer.Typer(help="Signal risk analysis: classify nodes by clock/reset/data, compute risk scores")


@risk_app.command(name="analyze")
def analyze(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(False, "--strict", help="Strict mode: elaboration error 立即 raise (默认 non-strict)"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    max_comb_depth: int = typer.Option(3, "--max-comb-depth", help="Max combinational depth threshold"),
    evidence: bool = typer.Option(False, "--evidence", "-e", help="Include source evidence for each data signal (optional)"),
) -> None:
    """Analyze signal risk: clock/reset/data classification + risk scoring

    [ADD 2026-06-11 Req-9] 支持 --filelist 跑多文件项目.
    [ADD 2026-06-11 任务3] elaboration error 统一 catch.
    """
    from cli._common import _build_tracer, handle_compilation_error
    from trace.core.compiler import CompilationError

    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    try:
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
            log_level=log_level,
        )
        graph = tracer.build_graph()
        sources = tracer._sources
        sva = SVAExtractor(sources).extract()
        cov_list = CovergroupExtractor(sources).extract()
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)

    # 覆盖信号
    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)
    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)

    # 分类节点
    clocks, resets, data_signals = [], [], []
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        name = node_id.split(".")[-1]
        if node.is_clock or name in ("clk", "clk_i"):
            clocks.append({"id": node_id, "name": name})
        elif node.is_reset or name in ("rst_n", "rst", "resetn"):
            resets.append({"id": node_id, "name": name})
        else:
            data_signals.append(node_id)

    # 计算数据信号风险
    def compute_risk(graph, node_id, sva_signals, cov_signals, max_comb_depth):
        node = graph.get_node(node_id)
        if node is None:
            return None
        name = node_id.split(".")[-1]
        fan_in = graph.in_degree(node_id)
        fan_out = graph.out_degree(node_id)
        width_bits = max(1, node.width[1] - node.width[0] + 1) if node.width else 1
        is_reg = node.kind == NodeKind.REG
        is_conv = fan_in >= 3
        is_div = fan_out >= 3
        has_sva = name in sva_signals
        has_cov = name in cov_signals

        func = fan_in * 3 + fan_out * 2 + width_bits * 0.3
        func += 15 if is_conv else 0
        func += 10 if is_div else 0
        func += 12 if not has_sva else 0
        func += 8 if not has_cov else 0

        timing = 15 if is_reg else 0
        timing += fan_in * 2
        timing += max_comb_depth * 5

        func_level = "CRITICAL" if func >= 40 else "HIGH" if func >= 25 else "MEDIUM" if func >= 15 else "LOW"
        timing_level = "CRITICAL" if timing >= 40 else "HIGH" if timing >= 25 else "MEDIUM" if timing >= 15 else "LOW"

        return {
            "node_id": node_id,
            "name": name,
            "kind": str(node.kind),
            "fan_in": fan_in,
            "fan_out": fan_out,
            "width": width_bits,
            "is_reg": is_reg,
            "is_conv": is_conv,
            "is_div": is_div,
            "has_sva": has_sva,
            "has_cov": has_cov,
            "func_score": round(func, 1),
            "func_level": func_level,
            "timing_score": round(timing, 1),
            "timing_level": timing_level,
        }

    data_risks = []
    for nid in data_signals:
        r = compute_risk(graph, nid, sva_signals, cov_signals, max_comb_depth)
        if r:
            data_risks.append(r)

    data_risks.sort(key=lambda x: x["func_score"] + x["timing_score"], reverse=True)

    # [Stage 5] (可选) evidence 召回
    evidence_resolver = None
    if evidence:
        evidence_resolver = _make_evidence_resolver(graph, tracer._get_adapter())
        for r in data_risks:
            r["evidence"] = evidence_to_dict(evidence_resolver.resolve(r["node_id"]))

    if json_output:
        import json

        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "risk analyze",
                    "params": {"file": file, "max_comb_depth": max_comb_depth},
                    "result": {
                        "clocks": clocks,
                        "resets": resets,
                        "data_signals": data_risks,
                        "summary": {
                            "total": len(data_risks),
                            "critical": len([r for r in data_risks if r["func_level"] == "CRITICAL"]),
                            "high": len([r for r in data_risks if r["func_level"] == "HIGH"]),
                            "sva_covered": len(sva_signals),
                            "cov_covered": len(cov_signals),
                        },
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    # 文本输出
    # [ADD 2026-06-11 Req-9] file/filelist 模式都显示实际被分析的文件名, 行为一致
    display_file = file if file else (list(sources.keys())[0] if sources else filelist)
    print(f"{'=' * 80}")
    print(f"风险分析: {display_file}")
    print(f"{'=' * 80}")

    print(f"\n  ⏰ 时钟信号 ({len(clocks)}): {', '.join(c['name'] for c in clocks)}")
    print(f"  🔄 复位信号 ({len(resets)}): {', '.join(r['name'] for r in resets)}")

    print("\n  数据信号风险排名:")
    print(f"  {'排名':4s} {'信号':25s} {'类型':6s} {'fan_in':6s} {'fan_out':7s} {'功能分':6s} {'时序分':6s}")
    print(f"  {'─' * 4} {'─' * 25} {'─' * 6} {'─' * 6} {'─' * 7} {'─' * 6} {'─' * 6}")

    level_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    level_icons_t = {"CRITICAL": "⏱🔴", "HIGH": "⏱🟠", "MEDIUM": "⏱🟡", "LOW": "⏱🟢"}

    for i, r in enumerate(data_risks[:20], 1):
        kind_short = {"PORT_IN": "IN", "PORT_OUT": "OUT", "REG": "REG", "SIGNAL": "SIG"}.get(r["kind"], "?")
        fi = level_icon.get(r["func_level"], "?")
        ti = level_icons_t.get(r["timing_level"], "?")
        sva_m = "✓" if r["has_sva"] else "✗"
        cov_m = "✓" if r["has_cov"] else "✗"
        print(
            f"  {i:4d} {r['name']:25s} {kind_short:6s} {r['fan_in']:6d} {r['fan_out']:7d} {fi} {r['func_score']:5.1f} {ti} {r['timing_score']:5.1f}  SVA:{sva_m} Cov:{cov_m}"
        )
        # [Stage 5] 可选 evidence 1 行摘要
        if evidence and r.get("evidence"):
            summary = evidence_summary_indented(r["evidence"])
            if summary:
                print(summary)

    func_summary = {}
    for r in data_risks:
        func_summary[r["func_level"]] = func_summary.get(r["func_level"], 0) + 1

    print("\n  风险分布:")
    for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = func_summary.get(level, 0)
        pct = count / len(data_risks) * 100 if data_risks else 0
        icon = level_icon.get(level, "?")
        bar = "█" * int(pct / 3)
        print(f"    {icon} {level:8s} {count:3d} ({pct:5.1f}%) {bar}")

    print("\n  覆盖状态:")
    print(f"    SVA 覆盖: {len(sva_signals)} 个信号")
    print(f"    Coverage 覆盖: {len(cov_signals)} 个信号")


if __name__ == "__main__":
    typer.run(analyze)
