# ==============================================================================
# cdc.py - CDC 检测命令
# ==============================================================================
"""
Usage:
  python run_cli.py cdc analyze top.sv
  python run_cli.py cdc analyze top.sv --json
  python run_cli.py cdc analyze top.sv --high-only
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

from trace.core.graph.analyzer.cdc_analyzer import CDCAnalyzer

# [Stage 5] evidence helper (可选 --evidence flag)
from cli._evidence_helpers import (  # noqa: E402
    make_resolver as _make_evidence_resolver,
    evidence_to_dict,
    evidence_summary_indented,
    format_cdc_human as _format_cdc_human,
)

cdc_app = typer.Typer(help="CDC (Clock Domain Crossing) detection: identify cross-clock domain paths")


@cdc_app.command(name="analyze")
def analyze(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    high_only: bool = typer.Option(False, "--high-only", help="Show only high-risk CDC paths"),
    evidence: bool = typer.Option(False, "--evidence", "-e", help="Include source evidence for source/target of each CDC path (optional)"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
) -> None:
    """Detect clock domain crossing issues"""
    from trace.unified_tracer import UnifiedTracer

    with open(file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={file: source})
    graph = tracer.build_graph()
    cdc = CDCAnalyzer(graph)
    cdc.identify_clock_domains()
    cdc.assign_domains()
    report = cdc.cdc_report()

    # [Stage 5] (可选) evidence 召回 - 每条 CDC 路径的 source/target 独立解析
    evidence_resolver = None
    if evidence:
        evidence_resolver = _make_evidence_resolver(graph, tracer._get_adapter())
        for p in report.get("paths", []):
            p["source_evidence"] = evidence_to_dict(evidence_resolver.resolve(p["source"]))
            p["target_evidence"] = evidence_to_dict(evidence_resolver.resolve(p["target"]))

    # [Stage 5] JSON 模式修复: domain_pairs 用了 tuple key, 不能直接 json.dumps
    # 转换为 string key (避免 Stage 4 后才暴露的 bug 被 evidence 路径触发)
    if json_output:
        import json

        def _json_safe(obj):
            if isinstance(obj, dict):
                return {str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k: _json_safe(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_json_safe(x) for x in obj]
            return obj

        safe_report = _json_safe(report)
        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "cdc analyze",
                    "params": {"file": file, "high_only": high_only, "evidence": evidence},
                    "result": safe_report,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    # [Stage 6] --human 友好输出: 短路到箭头格式
    if human:
        # 拿 evidence (跟 text 模式一样)
        evidence_resolver = None
        if evidence:
            evidence_resolver = _make_evidence_resolver(graph, tracer._get_adapter())
            for p in report.get("paths", []):
                p["source_evidence"] = evidence_to_dict(evidence_resolver.resolve(p["source"]))
                p["target_evidence"] = evidence_to_dict(evidence_resolver.resolve(p["target"]))
        paths_to_show = report["paths"]
        if high_only:
            paths_to_show = [p for p in paths_to_show if p["risk"] == "HIGH"]
        print(f"CDC 检测报告: {file}")
        print(f"  时钟域: {len(report['domains'])}, 总计: {report['total_cdc']}, "
              f"高风险: {report['high_risk']}, 低风险: {report['low_risk']}")
        print()
        print(_format_cdc_human(paths_to_show))
        return

    print(f"{'=' * 70}")
    print(f"CDC 检测报告: {file}")
    print(f"{'=' * 70}")

    print(f"\n  时钟域 ({len(report['domains'])}):")
    for d in report["domains"]:
        print(f"    - {d}")

    print("\n  CDC 路径统计:")
    print(f"    总计: {report['total_cdc']}")
    print(f"    🔴 高风险: {report['high_risk']}")
    print(f"    🟢 低风险: {report['low_risk']}")

    paths = report["paths"]
    if high_only:
        paths = [p for p in paths if p["risk"] == "HIGH"]

    if paths:
        print("\n  CDC 路径详情:")
        for i, p in enumerate(paths, 1):
            risk_icon = "🔴" if p["risk"] == "HIGH" else "🟢"
            sync_icon = "✓" if p["has_synchronizer"] else "✗"
            print(f"\n  [{i}] {risk_icon} {p['source']} → {p['target']}")
            print(f"      域: {p['source_domain']} → {p['target_domain']}")
            print(f"      边: {p['edge_kind']} | 同步器: {sync_icon}")
            # [Stage 5] 可选 evidence 1 行摘要 (source 和 target 各一行)
            if evidence:
                src_summary = evidence_summary_indented(p.get("source_evidence"), indent="        source: ")
                tgt_summary = evidence_summary_indented(p.get("target_evidence"), indent="        target: ")
                if src_summary:
                    print(src_summary)
                if tgt_summary:
                    print(tgt_summary)
    else:
        print("\n  未发现 CDC 路径")


if __name__ == "__main__":
    typer.run(analyze)
