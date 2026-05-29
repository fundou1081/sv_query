#==============================================================================
# cdc.py - CDC 检测命令
#==============================================================================
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

import typer
import warnings
warnings.filterwarnings("ignore")

from trace.core.graph.analyzer.cdc_analyzer import CDCAnalyzer

cdc_app = typer.Typer(help="CDC (Clock Domain Crossing) detection: identify cross-clock domain paths")


@cdc_app.command(name="analyze")
def analyze(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    high_only: bool = typer.Option(False, "--high-only", help="Show only high-risk CDC paths"),
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

    if json_output:
        import json
        print(json.dumps({
            'ok': True, 'command': 'cdc analyze',
            'result': report,
        }, indent=2, ensure_ascii=False))
        return

    print(f"{'='*70}")
    print(f"CDC 检测报告: {file}")
    print(f"{'='*70}")

    print(f"\n  时钟域 ({len(report['domains'])}):")
    for d in report['domains']:
        print(f"    - {d}")

    print(f"\n  CDC 路径统计:")
    print(f"    总计: {report['total_cdc']}")
    print(f"    🔴 高风险: {report['high_risk']}")
    print(f"    🟢 低风险: {report['low_risk']}")

    paths = report['paths']
    if high_only:
        paths = [p for p in paths if p['risk'] == 'HIGH']

    if paths:
        print(f"\n  CDC 路径详情:")
        for i, p in enumerate(paths, 1):
            risk_icon = '🔴' if p['risk'] == 'HIGH' else '🟢'
            sync_icon = '✓' if p['has_synchronizer'] else '✗'
            print(f"\n  [{i}] {risk_icon} {p['source']} → {p['target']}")
            print(f"      域: {p['source_domain']} → {p['target_domain']}")
            print(f"      边: {p['edge_kind']} | 同步器: {sync_icon}")
    else:
        print(f"\n  未发现 CDC 路径")


if __name__ == "__main__":
    typer.run(analyze)