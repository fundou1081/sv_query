# ==============================================================================
# main.py - CLI entry point
# ==============================================================================
"""
Usage:
  python -m cli.main dataflow --help
  python src/cli/main.py dataflow --help
"""

import sys
from pathlib import Path

# 设置 sys.path - 允许直接运行或作为模块运行
# 找到 src/ 目录的父目录并添加到 path
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent  # src/cli/
_project_root = _src_dir.parent.parent  # 项目根目录

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import typer

# [C-Flaky-3b 2026-06-27] 条件式 reclaim: 只在 swap > 2GB (内存压力)
# 时跑, 避免 pytest test runner 里多次 reclaim 累积 OOM.
from trace.unified_tracer import reclaim_memory_if_needed
reclaim_memory_if_needed()

from src.cli._common import (
    _build_tracer,
    handle_compilation_error,
)
from src.cli.commands.cdc import cdc_app
from src.cli.commands.controlflow import controlflow_app
from src.cli.commands.coverage import coverage_app
from src.cli.commands.dataflow import dataflow_app
from src.cli.commands.diff import diff_app
from src.cli.commands.risk import risk_app
from src.cli.commands.snapshot import snapshot_app
from src.cli.commands.sva import sva_app
from src.cli.commands.timing import timing_app
from src.cli.commands.backpressure import backpressure_app
from src.cli.commands.handshake import handshake_app
from src.cli.commands.protocol import protocol_app
from src.cli.commands.trace import trace_app
from src.cli.commands.verify import verify_app
from src.cli.commands.visualize import vis_app
from src.cli.commands.arch import arch_app
from src.cli.commands.fix import fix_app
from src.cli.commands.search import search

app = typer.Typer(
    name="svq",
    help="SystemVerilog signal tracer and graph diff tool",
    add_completion=False,
)

# 注册子命令组
app.add_typer(trace_app, name="trace")
app.add_typer(diff_app, name="diff")
app.add_typer(snapshot_app, name="snapshot")
app.add_typer(dataflow_app, name="dataflow")
app.add_typer(controlflow_app, name="controlflow")
app.add_typer(risk_app, name="risk")
app.add_typer(sva_app, name="sva")
app.add_typer(timing_app, name="timing")
app.add_typer(cdc_app, name="cdc")
app.add_typer(coverage_app, name="coverage")
app.add_typer(verify_app, name="verify")
app.add_typer(backpressure_app, name="backpressure")
app.add_typer(handshake_app, name="handshake")
app.add_typer(protocol_app, name="protocol")
app.add_typer(vis_app, name="visualize")
app.add_typer(arch_app, name="arch")
app.add_typer(fix_app, name="fix")

# stats 是单独命令，不需要子 Typer
# 动态导入避免循环依赖


def stats_callback(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    fanout_rank: bool = typer.Option(False, "--fanout-rank", help="Show fanout ranking"),
    top_n: int = typer.Option(20, "--top", "-n", help="Number of top signals to show"),
) -> None:
    """Show graph statistics

    [ADD 2026-06-11 Req-9] 支持 --filelist 跑多文件项目.
    [ADD 2026-06-11 任务3] elaboration error 统一 catch, 错误信息干净.
    """
    from trace.core.compiler import CompilationError
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
        )
        graph = tracer.build_graph()

        nodes_count = {}
        for n in graph.nodes():
            node = graph.get_node(n)
            if node:
                kind = node.kind.name if hasattr(node.kind, "name") else str(node.kind)
                nodes_count[kind] = nodes_count.get(kind, 0) + 1

        edges_count = {}
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge:
                kind = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)
                edges_count[kind] = edges_count.get(kind, 0) + 1

        modules = list(graph.modules) if hasattr(graph, "modules") else []

        data = {
            "ok": True,
            "command": "stats",
            "params": {
                "file": file,
                "filelist": filelist,
                "fanout_rank": fanout_rank,
                "top_n": top_n,
            },
            "result": {
                "total_nodes": len(graph.nodes()),
                "total_edges": len(graph.edges()),
                "nodes": nodes_count,
                "edges": edges_count,
                "modules": modules,
                # [ADD 2026-06-11 Req-14] elaboration errors 让用户知道是 partial result
                "elaboration_errors": tracer.get_elaboration_errors(),
            },
            "errors": [],
        }

        # 扇出排行榜计算
        if fanout_rank:
            fanout_data = _compute_fanout_rank(graph)
            data["result"].update(fanout_data)

        if json_output:
            import json as json_mod

            indent = 2 if pretty else None
            print(json_mod.dumps(data, indent=indent, ensure_ascii=False))
        else:
            if fanout_rank:
                _output_fanout_rank(data, top_n)
            else:
                print("=== Graph Statistics ===")
                print(f"  Total nodes: {len(graph.nodes())}")
                print(f"  Total edges: {len(graph.edges())}")
                # [ADD 2026-06-11 Req-14] elaboration error 计数 + partial result 提示
                elaboration_errors = data["result"].get("elaboration_errors", [])
                if elaboration_errors:
                    print(f"\n  [WARNING] {len(elaboration_errors)} elaboration error(s), partial graph shown")
                    for e in elaboration_errors[:5]:
                        file_short = e.get("file", "?")
                        if "/" in file_short:
                            file_short = file_short.split("/")[-1]
                        print(f"    - {file_short}:{e.get('line', '?')}: {e.get('code', '?')}")
                    if len(elaboration_errors) > 5:
                        print(f"    ... and {len(elaboration_errors) - 5} more")
                print("\n  Node kinds:")
                for kind, count in nodes_count.items():
                    print(f"    {kind}: {count}")
                print("\n  Edge kinds:")
                for kind, count in edges_count.items():
                    print(f"    {kind}: {count}")
                print(f"\n  Modules ({len(modules)}):")
                for m in modules[:10]:
                    print(f"    - {m}")
    except CompilationError as e:
        # [ADD 2026-06-11 任务3] 统一 catch, 不暴露 Python traceback
        handle_compilation_error(e, strict=strict)


def _compute_fanout_rank(graph) -> dict:
    """计算扇出排行榜

    注意：过滤掉 CONST 节点（字面量），因为它们不是真正的驱动源
    """
    from trace.core.graph.models import EdgeKind, NodeKind

    # 计算每个信号的扇出（下游 DRIVER 负载数）
    fanout_map = {}  # signal_id -> {"count": int, "kind": str, "loads": []}

    for src, dst in graph.edges():
        edge = graph.get_edge(src, dst)
        if edge and edge.kind == EdgeKind.DRIVER:
            # 跳过 CONST 节点（字面量如 1'b0, 4'b1 等）
            node = graph.get_node(src)
            if node and node.kind == NodeKind.CONST:
                continue

            if src not in fanout_map:
                fanout_map[src] = {"count": 0, "kind": "", "loads": [], "is_clock": False, "is_reset": False}
            fanout_map[src]["count"] += 1
            fanout_map[src]["loads"].append(dst)

    # 获取节点类型信息
    for signal_id in fanout_map:
        node = graph.get_node(signal_id)
        if node:
            fanout_map[signal_id]["kind"] = node.kind.name if hasattr(node.kind, "name") else str(node.kind)
            fanout_map[signal_id]["is_clock"] = getattr(node, "is_clock", False)
            fanout_map[signal_id]["is_reset"] = getattr(node, "is_reset", False)

    # 生成排行榜
    fanout_list = []
    clock_fanout = 0
    reset_fanout = 0

    for signal_id, info in fanout_map.items():
        fanout = info["count"]
        kind = info["kind"]

        # 统计时钟/复位扇出
        if info.get("is_clock", False):
            clock_fanout = max(clock_fanout, fanout)
        if info.get("is_reset", False):
            reset_fanout = max(reset_fanout, fanout)

        # 生成建议
        suggestion = _generate_suggestion(signal_id, fanout, kind, info)

        fanout_list.append(
            {
                "signal": signal_id,
                "fanout": fanout,
                "kind": kind,
                "suggestion": suggestion,
                "loads": info["loads"],
            }
        )

    # 按扇出数排序
    fanout_list.sort(key=lambda x: x["fanout"], reverse=True)

    return {
        "fanout_rank": fanout_list,
        "clock_fanout": clock_fanout,
        "reset_fanout": reset_fanout,
    }


def _generate_suggestion(signal_id: str, fanout: int, kind: str, info: dict) -> str:
    """生成扇出建议"""
    signal_name = signal_id.split(".")[-1] if "." in signal_id else signal_id

    # 时钟信号
    if info.get("is_clock", False) or "clk" in signal_name.lower():
        if fanout > 100:
            return "🔴 时钟网络过重，建议 clock gating"
        elif fanout > 50:
            return "🟠 时钟扇出较大，考虑优化"

    # 复位信号
    if info.get("is_reset", False) or "rst" in signal_name.lower() or "reset" in signal_name.lower():
        if fanout > 100:
            return "🔴 复位网络过重，建议分模块复位"
        elif fanout > 50:
            return "🟠 复位扇出较大，考虑分时复位"

    # 高扇出数据信号
    if fanout > 50:
        return "🟠 高扇出信号，检查是否需要拆分"

    # 使能/有效信号
    if "en" in signal_name.lower() or "valid" in signal_name.lower() or "ready" in signal_name.lower():
        if fanout > 20:
            return "🟡 使能信号扇出较大"

    return ""


def _output_fanout_rank(data: dict, top_n: int = 20) -> None:
    """扇出排行榜输出"""
    result = data.get("result", {})
    fanout_list = result.get("fanout_rank", [])
    clock_fanout = result.get("clock_fanout", 0)
    reset_fanout = result.get("reset_fanout", 0)

    print("=== Fanout Statistics ===")
    print(f"  Clock fanout: {clock_fanout} (建议 > 50 考虑 clock gating)")
    print(f"  Reset fanout: {reset_fanout} (建议 > 50 考虑分时复位)")

    print(f"\n  High Fanout Signals (TOP {top_n}):")
    print(f"  {'Rank':<6} {'Fanout':<8} {'Signal':<40} {'Kind':<12} {'Suggestion'}")
    print(f"  {'-' * 6} {'-' * 8} {'-' * 40} {'-' * 12} {'-' * 20}")

    for i, entry in enumerate(fanout_list[:top_n], 1):
        signal = entry.get("signal", "")
        fanout = entry.get("fanout", 0)
        kind = entry.get("kind", "")
        suggestion = entry.get("suggestion", "")

        # 截断过长的信号名
        if len(signal) > 38:
            signal = signal[:35] + "..."

        print(f"  {i:<6} {fanout:<8} {signal:<40} {kind:<12} {suggestion}")

    print(f"\n  总计 {len(fanout_list)} 个信号有下游负载")


# 注册 stats 为独立命令
app.command(name="stats", help="Show graph statistics")(stats_callback)
app.command(name="search", help="Grep-like keyword search across .sv/.v files")(search)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """SystemVerilog signal tracer and graph diff tool"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
