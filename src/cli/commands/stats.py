# ==============================================================================
# stats.py - graph statistics command
# ============================================================================

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli._common import (
    FILE_OPTION,
    FILELIST_OPTION,
    LOG_LEVEL_OPTION,
    STRICT_OPTION,
    PREPROCESS_OPTION,
    _build_tracer,
    handle_compilation_error,
)
from trace.core.compiler import CompilationError
from trace.core.graph.models import EdgeKind
from trace.unified_tracer import UnifiedTracer


def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict) -> None:
    """纯文本输出"""
    result = data.get("result", {})
    nodes = result.get("nodes", {})
    edges = result.get("edges", {})
    modules = result.get("modules", [])

    print("=== Graph Statistics ===")
    print(f"  Total nodes: {result.get('total_nodes', 0)}")
    print(f"  Total edges: {result.get('total_edges', 0)}")

    # [ADD 2026-06-11 Req-14] elaboration error 计数 + partial result 提示
    elaboration_errors = result.get("elaboration_errors", [])
    if elaboration_errors:
        print(f"\n  [WARNING] {len(elaboration_errors)} elaboration error(s), partial graph shown")
        # 列出前 5 个错误 (file:line: code)
        for e in elaboration_errors[:5]:
            file_short = e.get("file", "?")
            if "/" in file_short:
                file_short = file_short.split("/")[-1]
            print(f"    - {file_short}:{e.get('line', '?')}: {e.get('code', '?')}")
        if len(elaboration_errors) > 5:
            print(f"    ... and {len(elaboration_errors) - 5} more")

    print("\n  Node kinds:")
    for kind, count in nodes.items():
        print(f"    {kind}: {count}")

    print("\n  Edge kinds:")
    for kind, count in edges.items():
        print(f"    {kind}: {count}")

    print(f"\n  Modules ({len(modules)}):")
    for m in modules[:10]:
        print(f"    - {m}")
    if len(modules) > 10:
        print(f"    ... and {len(modules) - 10} more")


def output_fanout_rank(data: dict, top_n: int = 20) -> None:
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


def stats(
    file: Path = FILE_OPTION,
    filelist: str = FILELIST_OPTION,
    strict: bool = STRICT_OPTION,
    log_level: str = LOG_LEVEL_OPTION,
    preprocess_macros: bool = PREPROCESS_OPTION,
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    fanout_rank: bool = typer.Option(False, "--fanout-rank", help="Show fanout ranking"),
    top_n: int = typer.Option(20, "--top", "-n", help="Number of top signals to show"),
) -> None:
    """Show graph statistics

    [ADD 2026-06-11 Req-9] 支持 --filelist 跑多文件项目.
    [ADD 2026-06-11 任务3] elaboration error 统一 catch, 错误信息干净.
    """
    try:
        if not file and not filelist:
            raise ValueError("Either --file or --filelist must be provided")
        tracer = _build_tracer(
            file=file, filelist=filelist, strict=strict, log_level=log_level, preprocess_macros=preprocess_macros
        )
        graph = tracer.build_graph()

        # 转换 NodeKind/EdgeKind enum 为字符串
        nodes = {}
        for n in graph.nodes():
            node = graph.get_node(n)
            if node:
                kind = node.kind.name if hasattr(node.kind, "name") else str(node.kind)
                nodes[kind] = nodes.get(kind, 0) + 1

        edges = {}
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge:
                kind = edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind)
                edges[kind] = edges.get(kind, 0) + 1

        # 获取模块列表
        modules = list(graph.modules) if hasattr(graph, "modules") else []

        data = {
            "ok": True,
            "command": "stats",
            "params": {
                "file": str(file) if file else None,
                "filelist": filelist,
                "fanout_rank": fanout_rank,
                "top_n": top_n,
            },
            "result": {
                "total_nodes": len(graph.nodes()),
                "total_edges": len(graph.edges()),
                "nodes": nodes,
                "edges": edges,
                "modules": modules,
                # [ADD 2026-06-11 Req-14] 带上 elaboration errors 让用户知道是 partial result
                "elaboration_errors": tracer.get_elaboration_errors(),
            },
            "errors": [],
        }

        # 扇出排行榜计算
        if fanout_rank:
            fanout_data = _compute_fanout_rank(graph)
            data["result"].update(fanout_data)

        if json_output:
            output_json(data, pretty)
        else:
            if fanout_rank:
                output_fanout_rank(data, top_n)
            else:
                output_text(data)

    except CompilationError as e:
        # [ADD 2026-06-11 任务3] 统一 catch, 不暴露 Python traceback
        handle_compilation_error(e, strict=strict)
    except Exception as e:
        data = {"ok": False, "command": "stats", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


def _compute_fanout_rank(graph) -> dict:
    """计算扇出排行榜

    Returns:
        dict: 包含 fanout_rank 列表, clock_fanout, reset_fanout
    """
    # 计算每个信号的扇出（下游负载数）
    fanout_map = {}  # signal_id -> fanout_count

    for src, dst in graph.edges():
        # 只计算 DRIVER 边作为有效扇出
        edge = graph.get_edge(src, dst)
        if edge and edge.kind == EdgeKind.DRIVER:
            if src not in fanout_map:
                fanout_map[src] = {"count": 0, "kind": "", "loads": []}
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
