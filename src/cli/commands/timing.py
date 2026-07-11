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
from cli._common import _build_tracer, handle_compilation_error  # [ADD 2026-06-11 Req-9]
from trace.core.compiler import CompilationError  # [ADD 2026-06-11 任务3]


warnings.filterwarnings("ignore")

from trace.core.graph.analyzer.timing_analyzer import TimingAnalyzer

timing_app = typer.Typer(help="[EXPERIMENTAL] Timing critical path analysis: register depth, DAG longest path, SCC detection")


@timing_app.command(name="analyze")
def analyze(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    module: str = typer.Option(None, "--module", "-m", help="[Phase 3 2026-07-11] Target module (focus SignalGraph on this module's hierarchy)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图 (供分析不完整项目用)"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. Use --no-preprocess 退回 pyslang 内置处理 (供不跨文件 define 的小项目用)"),

    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    max_paths: int = typer.Option(5, "--max-paths", help="Max number of paths to report"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="[P1 fix 2026-07-10] Output DOT file visualizing critical paths"),
) -> None:
    """Analyze timing critical paths"""
    from trace.core.graph.models import NodeKind
    from trace.unified_tracer import UnifiedTracer

    if not file and not filelist:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    try:
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
            log_level=log_level,
            preprocess_macros=preprocess_macros,
        )
        # [Phase 3 2026-07-11] Pass --module as target_module for correct namespace
        graph = tracer.build_graph(target_module=module)
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return
    analyzer = TimingAnalyzer(graph)

    paths = analyzer.get_critical_paths(max_paths=max_paths)

    # [FIX 2026-07-10 方豆 feedback 15:23] Detect RTL anomalies in target module.
    # This explains why timing's critical path may be incomplete (truncated at
    # an undriven signal). Critical path is computed from port → reg → port;
    # an X_DRIVER signal in the path forces the path to stop.
    target_module = tracer._tracer_root if hasattr(tracer, "_tracer_root") else None
    timing_anomalies: dict[str, str] = {}
    from trace.core.graph.models import NodeKind
    for nid in graph.nodes():
        # Only check target module's signals (heuristic: first part of dotted name)
        if "." not in nid:
            continue
        first_seg = nid.split(".", 1)[0]
        if target_module and first_seg != target_module:
            continue  # Skip sub-modules
        node = graph.get_node(nid)
        if not node:
            continue
        if node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT):
            continue
        n_in = graph.in_degree(nid)
        n_out = graph.out_degree(nid)
        if n_in == 0 and n_out > 0:
            timing_anomalies[nid] = "X_DRIVER"
        elif n_out == 0 and n_in > 0:
            timing_anomalies[nid] = "DANGLING"
        elif n_in == 0 and n_out == 0:
            timing_anomalies[nid] = "ORPHAN"

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

    # [P1 fix 2026-07-10] Generate DOT visualization of critical paths
    if dot_output:
        lines = ['digraph timing {']
        lines.append('  rankdir=LR;')
        anomaly_note = ""
        if timing_anomalies:
            anomaly_note = f"\\n⚠️  {len(timing_anomalies)} RTL anomalies (may truncate paths)"
        lines.append(f'  label="Critical Paths: {file or filelist}\\n({len(paths)} paths, deepest={max((p["depth"] for p in paths), default=0)}){anomaly_note}";')
        lines.append('  labelloc=t;')
        lines.append('  fontsize=14;')
        lines.append('  splines=polyline;')
        lines.append('  ranksep=1.0;')
        lines.append('  nodesep=0.4;')
        lines.append('')
        # Draw all paths with color-coded nodes/edges
        # Path 1 = red (deepest), others = blue
        for i, p in enumerate(paths, 1):
            is_critical = (i == 1)
            color = "#cc2222" if is_critical else "#226699"
            penwidth = 3 if is_critical else 1.5
            path_nodes = p["path"]
            for j, node in enumerate(path_nodes):
                short = node.split(".")[-1]
                # Is this a register?
                is_reg = node in p["registers"]
                fillcolor = "#4488cc" if is_reg else "#88bbdd"
                if is_critical:
                    fillcolor = "#cc4444" if is_reg else "#ee8866"
                lines.append(f'  "{node}" [label="{short}" shape=box style="rounded,filled" fillcolor="{fillcolor}" fontcolor="white" penwidth={penwidth}];')
            # Edges
            for j in range(len(path_nodes) - 1):
                lines.append(f'  "{path_nodes[j]}" -> "{path_nodes[j+1]}" [color="{color}" penwidth={penwidth}];')
            # Subgraph for path (force ranking)
            if path_nodes:
                quoted = " ".join(f'"{n}"' for n in path_nodes)
                lines.append(f'  {{ rank=same; {quoted} }}')

        # [FIX 2026-07-10] Add anomalies cluster so user can see what truncated paths
        if timing_anomalies:
            lines.append('  subgraph "cluster_timing_anomalies" {')
            lines.append(f'    label="RTL Anomalies ({len(timing_anomalies)} signals, may truncate paths)";')
            lines.append('    style="rounded,dashed";')
            lines.append('    color="#cc6600";')
            lines.append('    penwidth=2.5;')
            lines.append('    fontsize=11;')
            lines.append('    fontcolor="#cc6600";')
            lines.append('    fontname="Helvetica-Bold";')
            lines.append('    bgcolor="#fff5e6";')
            for n, kind in timing_anomalies.items():
                short = n.split(".")[-1]
                if kind == "X_DRIVER":
                    color = "#cc8800"
                elif kind == "DANGLING":
                    color = "#cc0000"
                else:
                    color = "#888888"
                lines.append(
                    f'    "{n}" [label="{short}\\n[{kind}]" shape=diamond style="filled,rounded" '
                    f'fillcolor="{color}" fontcolor="white" fontsize=10 fontname="Helvetica-Bold"];'
                )
            lines.append('  }')
        lines.append('}')
        Path(dot_output).write_text("\n".join(lines))
        typer.echo(f"✓ DOT: {dot_output} ({len(paths)} critical paths)")
        if timing_anomalies:
            typer.echo(f"  ⚠️  {len(timing_anomalies)} RTL anomalies detected (may truncate critical paths)", err=True)
        return

    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式输出
    display_file = file if file else (list(tracer._sources.keys())[0] if tracer._sources else filelist)
    print(f"{'=' * 70}")
    print(f"关键路径分析: {display_file}")
    print(f"{'=' * 70}")

    print(f"\n  节点统计: 总={total_nodes} | 寄存器={reg_count}")

    # [FIX 2026-07-10 方豆 feedback] Show RTL anomalies that may truncate critical paths
    if timing_anomalies:
        from collections import Counter
        counts = Counter(timing_anomalies.values())
        # [FIX 2026-07-10 方豆 feedback 16:14] low-confidence warning when SWAP > 2GB
        from trace.core.compiler import is_elaboration_incomplete
        confidence = "low confidence (elaboration incomplete)" if is_elaboration_incomplete() else "high confidence"
        print(f"  ⚠️  RTL 异常 ({confidence}): {dict(counts)} (可能导致 critical path 截断)")
        if is_elaboration_incomplete():
            print("     ⚠️  WARNING: SWAP > 2GB, graph incomplete — these may be false positives")
        for n, kind in list(timing_anomalies.items())[:5]:
            short = n.split(".")[-1]
            print(f"     - {short}: {kind}")
        if len(timing_anomalies) > 5:
            print(f"     ... and {len(timing_anomalies) - 5} more")

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
