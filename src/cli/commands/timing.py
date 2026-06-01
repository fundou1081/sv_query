# ==============================================================================
# timing.py - 关键路径分析命令
# ==============================================================================
"""
Usage:
  python run_cli.py timing analyze top.sv
  python run_cli.py timing analyze top.sv --json
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

from trace.core.graph.analyzer.timing_analyzer import TimingAnalyzer

timing_app = typer.Typer(help="Timing critical path analysis: register depth, DAG longest path, SCC detection")


@timing_app.command(name="analyze")
def analyze(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    max_paths: int = typer.Option(5, "--max-paths", help="Max number of paths to report"),
) -> None:
    """Analyze timing critical paths"""
    from trace.core.graph.models import NodeKind
    from trace.unified_tracer import UnifiedTracer

    with open(file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={file: source})
    graph = tracer.build_graph()
    analyzer = TimingAnalyzer(graph)

    paths = analyzer.get_critical_paths(max_paths=max_paths)

    # 计算节点统计
    reg_count = sum(1 for n in graph.nodes() if graph.get_node(n) and graph.get_node(n).kind == NodeKind.REG)
    total_nodes = len(graph.nodes())

    if json_output:
        import json

        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "timing analyze",
                    "result": {
                        "total_nodes": total_nodes,
                        "reg_count": reg_count,
                        "critical_paths": [
                            {
                                "depth": p["depth"],
                                "score": p["score"],
                                "registers": [n.split(".")[-1] for n in p["registers"]],
                                "full_path": [n.split(".")[-1] for n in p["path"]],
                            }
                            for p in paths
                        ],
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    print(f"{'=' * 70}")
    print(f"关键路径分析: {file}")
    print(f"{'=' * 70}")

    print(f"\n  节点统计: 总={total_nodes} | 寄存器={reg_count}")

    if not paths:
        print("\n  未发现关键路径（可能无寄存器或数据流）")
        return

    print("\n  关键路径 (按深度排序):")
    print(f"  {'排名':4s} {'深度':5s} {'得分':6s} {'寄存器路径':30s}")
    print(f"  {'─' * 4} {'─' * 5} {'─' * 6} {'─' * 30}")

    for i, p in enumerate(paths, 1):
        reg_path = " → ".join(n.split(".")[-1] for n in p["registers"])
        if len(reg_path) > 30:
            reg_path = reg_path[:27] + "..."
        print(f"  {i:4d} {p['depth']:5d} {p['score']:6d} {reg_path}")

    print("\n  详细路径:")
    for i, p in enumerate(paths, 1):
        print(f"\n  [{i}] 深度={p['depth']}, 得分={p['score']}")
        full_path = " → ".join(n.split(".")[-1] for n in p["path"])
        print(f"      {full_path}")


if __name__ == "__main__":
    typer.run(analyze)
