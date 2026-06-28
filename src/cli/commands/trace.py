# ==============================================================================
# trace.py - trace fanin / fanout / impact subcommands
# ============================================================================
"""
Usage:
  python run_cli.py trace fanin top.clk -f top.sv
  python run_cli.py trace fanout top.data -f top.sv
  python run_cli.py trace impact top.changed_signal -f top.sv
"""

import json
import sys
from pathlib import Path

import typer

# 添加 src 到 path 以便 import trace
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.models import EdgeKind
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer

# [Stage 5] evidence helper (cdc/verify/risk/dataflow/controlflow 复用)
from cli._evidence_helpers import (  # noqa: E402
    build_resolver as _build_evidence_resolver,
    evidence_to_dict as _evidence_to_dict,
    snippet_to_dict as _snippet_to_dict,
    evidence_summary_line as _evidence_summary_line,
    format_fanin_human as _format_fanin_human,
    format_fanout_human as _format_fanout_human,
)


# JSON 输出格式化函数
def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict, human: bool = False, tree: bool = False) -> None:
    """纯文本输出

    Args:
        data: 命令返回的 dict
        human: True 时用人类友好箭头格式 (--human flag)
        tree: True 强制竖向 tree 输出 (--tree flag, 链 > 6 自动)
    """
    command = data.get("command", "")
    result = data.get("result", {})

    if command == "trace_fanin":
        signal = data.get("params", {}).get("signal", "")
        drivers = result.get("drivers", [])
        if human:
            ev = result.get("evidence")
            print(_format_fanin_human(signal, drivers, evidence_map={signal: ev} if ev else None, tree=tree))
        else:
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
        if human:
            ev = result.get("evidence")
            print(_format_fanout_human(signal, loads, evidence_map={signal: ev} if ev else None, tree=tree))
        else:
            print(f"Fanout of '{signal}':")
            if not loads:
                print("  (no loads)")
            for load in loads:
                dist = load.get("distance", "")
                kind = load.get("kind", "")
                print(f"  [{dist}] {load['id']} ({kind})")

    elif command == "trace_impact":
        if human:
            _output_impact_human(data, tree=tree)
        else:
            _output_impact_text(data)


def _output_impact_text(data: dict) -> None:
    """输出 impact 结果"""
    result = data.get("result", {})
    signal = data.get("params", {}).get("signal", "")
    paths = result.get("paths", [])
    modules = result.get("modules", [])
    high_risk = result.get("high_risk_count", 0)
    total_paths = result.get("total_paths", 0)

    print("=== Impact Summary ===")
    print(f"Signal: {signal}")
    print(f"Paths: {total_paths} total, {high_risk} high-risk")

    if not paths:
        print("\n  (no impact paths found)")
        return

    print(f"\nModules: {', '.join(modules) if modules else 'N/A'}")

    print(f"\n{'=' * 60}")

    for i, path in enumerate(paths, 1):
        risk = path.get("risk", "")
        risk_icon = "🔴" if risk == "HIGH" else ("🟡" if risk == "MEDIUM" else "✅")

        print(f"\n  {i}. {risk_icon} {risk} - {path.get('path_type', 'path')}")
        print(f"     Path: {' → '.join(path.get('path', []))}")
        print(f"     Fanout: {path.get('fanout', 0)} downstream loads")

        # 覆盖状态
        coverage = path.get("coverage", {})
        sva_status = coverage.get("sva", "NONE")
        cov_status = coverage.get("covergroup", "NONE")

        if sva_status == "covered" or cov_status == "covered":
            print("     Coverage: ✓ SVA covered" if sva_status == "covered" else "")
            print("     Coverage: ✓ Covergroup covered" if cov_status == "covered" else "")
        else:
            print(f"     ⚠️  No coverage (SVA: {sva_status}, Covergroup: {cov_status})")


def _output_impact_human(data: dict, tree: bool = False) -> None:
    """[Stage 6] impact 人类友好输出: 箭头链 + 风险 / 覆盖 tag

    tree: True 强制竖向 tree 输出 (--tree flag)
    """
    result = data.get("result", {})
    signal = data.get("params", {}).get("signal", "")
    paths = result.get("paths", [])
    modules = result.get("modules", [])
    high_risk = result.get("high_risk_count", 0)
    total_paths = result.get("total_paths", 0)

    # ANSI color re-import in this scope (避免乱动模块顶部 import)
    from cli._evidence_helpers import (
        _color, _ANSI_BOLD, _ANSI_DIM, _ANSI_CYAN, _ANSI_RED, _ANSI_YELLOW, _ANSI_GREEN, _ARROW
    )

    print(f"Impact of {_color(signal, _ANSI_BOLD)}")
    print(f"  {total_paths} paths, {high_risk} high-risk, {len(modules)} modules")
    if modules:
        print(f"  modules: {_color(', '.join(modules), _ANSI_DIM)}")
    print()

    if not paths:
        print(f"  {_color('(no impact paths)', _ANSI_DIM)}")
        return

    from cli._evidence_helpers import should_use_tree, render_signal_tree

    for i, path in enumerate(paths, 1):
        risk = (path.get("risk", "") or "").upper()
        if risk == "HIGH":
            risk_str = _color("HIGH", _ANSI_RED)
        elif risk == "MEDIUM":
            risk_str = _color("MEDIUM", _ANSI_YELLOW)
        else:
            risk_str = _color(risk or "LOW", _ANSI_GREEN)

        chain = path.get("path", [])
        cond = path.get("condition", "")
        cov = path.get("coverage", {})
        sva = cov.get("sva", "none")
        cg = cov.get("covergroup", "none")
        sug = path.get("suggestion", "")

        # tree 模式 / 自动转 tree
        if should_use_tree(len(chain), tree):
            print(f"  {i}. (tree)")
            tree_out = render_signal_tree(
                chain,
                title=None,
                risk_marker=risk if risk in ("HIGH", "MEDIUM") else None,
                terminal_meta=f"when {cond}" if cond else None,
            )
            for ln in tree_out.split("\n"):
                print(f"     {ln}")
        else:
            if chain:
                chain_str = " ".join(
                    [_color(chain[0], _ANSI_BOLD)] + [_ARROW] + [_color(s, _ANSI_CYAN) for s in chain[1:]]
                )
            else:
                chain_str = "(empty)"
            print(f"  {i}. {chain_str}  [{risk_str}]")

        cov_str = f"sva={sva}, covergroup={cg}"
        cond_str = f"  when {_color(cond, _ANSI_DIM)}" if cond else ""
        print(f"     {cov_str}  fanout={path.get('fanout', 0)}{cond_str}")
        if sug:
            print(f"     {_color('└─ ' + sug, _ANSI_DIM)}")

        # 条件/时钟信息
        if path.get("condition"):
            print(f"     Condition: {path['condition']}")
        if path.get("clock_domain"):
            print(f"     Clock: {path['clock_domain']}")

        # 建议
        suggestion = path.get("suggestion", "")
        if suggestion:
            print(f"     💡 {suggestion}")

    # 总结建议
    if high_risk > 0:
        print(f"\n{'=' * 60}")
        print(f"⚠️  High-risk: {high_risk} paths lack coverage")
        print("💡  Review these paths before making changes")


trace_app = typer.Typer(help="Trace signal drivers (fanin), loads (fanout), or impact analysis")


@trace_app.command()
def fanin(
    signal: str = typer.Argument(..., help="Signal to trace (e.g., top.clk)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    depth: int | None = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
    max_results: int | None = typer.Option(None, "--max-results", "-N", help="[C1 2026-06-28 LLM] Cap number of results (None=unlimited). Returns truncated=true if capped."),
) -> None:
    """Trace signal drivers (fanin)"""
    try:
        if filelist:
            tracer = UnifiedTracer(filelist=filelist, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        else:
            if file is None:
                raise ValueError("Either --file or --filelist must be provided")
            with open(str(file)) as f:
                source = f.read()
            tracer = UnifiedTracer(sources={str(file): source}, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        _ = tracer.build_graph()

        result = tracer.trace_fanin(signal, depth=depth)

        # 转换结果为可序列化格式
        drivers = []
        for d in result if hasattr(result, "__iter__") else []:
            if hasattr(d, "id"):
                drivers.append(
                    {
                        "id": d.id,
                        "kind": getattr(d, "kind", "UNKNOWN").name if hasattr(d, "kind") else "UNKNOWN",
                        "distance": getattr(d, "distance", 1) if hasattr(d, "distance") else 1,
                    }
                )

        # [C1 2026-06-28 LLM] Limit results to avoid context overflow
        truncated = False
        if max_results is not None and len(drivers) > max_results:
            drivers = drivers[:max_results]
            truncated = True

        data = {
            "ok": True,
            "command": "trace_fanin",
            "params": {"signal": signal, "file": str(file), "depth": depth, "max_results": max_results},
            "result": {"drivers": drivers, "truncated": truncated, "total_count": len(drivers)},
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data, human=human, tree=tree)

    except Exception as e:
        data = {"ok": False, "command": "trace_fanin", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@trace_app.command()
def fanout(
    signal: str = typer.Argument(..., help="Signal to trace (e.g., top.data)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    depth: int | None = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    include_clock: bool = typer.Option(False, "--include-clock", help="[Req-12] Include CLOCK edges (sensitivity list)"),
    include_reset: bool = typer.Option(False, "--include-reset", help="[Req-12] Include RESET edges"),
    include_control: bool = typer.Option(False, "--include-control", help="[Req-12] Include CONTROL edges (always block refs)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
    max_results: int | None = typer.Option(None, "--max-results", "-N", help="[C1 2026-06-28 LLM] Cap number of results (None=unlimited). Returns truncated=true if capped."),
) -> None:
    """Trace signal loads (fanout)

    [ADD 2026-06-11 Req-12 Issue 19] 默认只走 DRIVER+CONNECTION 边, 不含 CLOCK/RESET/CONTROL.
    用 --include-clock/reset/control flag 可加入. 完整视图请用 'visualize graph'.
    """
    try:
        if filelist:
            tracer = UnifiedTracer(filelist=filelist, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        else:
            if file is None:
                raise ValueError("Either --file or --filelist must be provided")
            with open(str(file)) as f:
                source = f.read()
            tracer = UnifiedTracer(sources={str(file): source}, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        _ = tracer.build_graph()

        result = tracer.trace_fanout(
            signal, depth=depth,
            include_clock=include_clock,
            include_reset=include_reset,
            include_control=include_control,
        )

        # 转换结果为可序列化格式
        loads = []
        for load in result if hasattr(result, "__iter__") else []:
            if hasattr(load, "id"):
                loads.append(
                    {
                        "id": load.id,
                        "kind": getattr(load, "kind", "UNKNOWN").name if hasattr(load, "kind") else "UNKNOWN",
                        "distance": getattr(load, "distance", 1) if hasattr(load, "distance") else 1,
                    }
                )

        # [C1 2026-06-28 LLM] Limit results to avoid context overflow
        truncated = False
        if max_results is not None and len(loads) > max_results:
            loads = loads[:max_results]
            truncated = True

        data = {
            "ok": True,
            "command": "trace_fanout",
            "params": {"signal": signal, "file": str(file), "depth": depth, "max_results": max_results},
            "result": {"loads": loads, "truncated": truncated, "total_count": len(loads)},
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data, human=human, tree=tree)

    except Exception as e:
        data = {"ok": False, "command": "trace_fanout", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@trace_app.command()
def impact(
    signal: str = typer.Argument(..., help="Signal to analyze impact (e.g., top.rst_ni)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    min_risk: float = typer.Option(30.0, "--min-risk", "-r", help="Minimum risk score for high-risk"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly arrow output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
) -> None:
    """Analyze impact of changing a signal

    Traces downstream loads (fanout) and assesses:
    - Impact paths and their risk levels
    - Coverage status (SVA/Covergroup)
    - Suggestions for safe modification
    """
    try:
        if filelist:
            tracer = UnifiedTracer(filelist=filelist, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        else:
            if file is None:
                raise ValueError("Either --file or --filelist must be provided")
            with open(str(file)) as f:
                source = f.read()
            tracer = UnifiedTracer(sources={str(file): source}, log_level="ERROR", strict=strict, preprocess_macros=preprocess_macros)
        graph = tracer.build_graph()

        # 提取 SVA 和 Coverage 信息
        # 当使用 filelist 时，从 tracer 的 compiler 获取已加载的源码
        if filelist:
            sources_for_extractors = tracer._get_compiler().sources()
        else:
            sources_for_extractors = {str(file): source}
        sva_extractor = SVAExtractor(sources_for_extractors)
        sva_data = sva_extractor.extract()
        cov_extractor = CovergroupExtractor(sources_for_extractors)
        cov_data = cov_extractor.extract()

        sva_signals = set()
        for prop in sva_data.properties.values():
            sva_signals.update(prop.signals)

        cov_signals = set()
        for cg in cov_data:
            for cp in cg.coverpoints:
                cov_signals.add(cp.signal)

        # 使用 trace_fanout 获取所有负载（下游被驱动的信号）
        # impact 关注"改变这个信号会影响哪些下游"
        load_nodes = tracer.trace_fanout(signal, depth=None)

        # 构建影响路径
        paths = _build_impact_paths(signal, load_nodes, graph, sva_signals, cov_signals, min_risk)

        # 提取涉及的模块
        modules = _extract_modules(paths)

        # 按风险排序
        risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        paths.sort(key=lambda x: risk_order.get(x.get("risk", "LOW"), 2))

        # 统计高风险路径数
        high_risk_count = sum(1 for p in paths if p.get("risk") == "HIGH")

        data = {
            "ok": True,
            "command": "trace_impact",
            "params": {"signal": signal, "file": str(file), "min_risk": min_risk},
            "result": {
                "total_paths": len(paths),
                "high_risk_count": high_risk_count,
                "modules": modules,
                "paths": paths,
            },
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data, human=human, tree=tree)

    except Exception as e:
        data = {"ok": False, "command": "trace_impact", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


def _build_impact_paths(
    signal: str, load_nodes: list, graph, sva_signals: set, cov_signals: set, min_risk: float
) -> list:
    """构建影响路径列表（从信号向下游追溯）

    Args:
        signal: 目标信号
        load_nodes: 下游负载节点列表（来自 trace_fanout）
        graph: 信号图
        sva_signals: 有 SVA 覆盖的信号集合
        cov_signals: 有 Covergroup 覆盖的信号集合
        min_risk: 最小风险分数（低于此值为 LOW）

    Returns:
        list: 影响路径列表
    """
    paths = []
    seen_paths = set()

    for node in load_nodes:
        node_id = node.id if hasattr(node, "id") else str(node)

        # 构建路径字符串
        path_nodes = [signal, node_id]

        # 递归向下追溯获取完整路径
        full_path = _get_full_load_path(node_id, graph, set())
        if len(full_path) > 1:
            path_nodes = [signal] + full_path

        path_key = " → ".join(path_nodes)
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)

        # 计算扇出
        downstream_fanout = len(
            [
                d
                for d in graph.successors(node_id)
                if graph.get_edge(node_id, d) and graph.get_edge(node_id, d).kind == EdgeKind.DRIVER
            ]
        )

        # 获取边的条件信息
        edge = graph.get_edge(signal, node_id)
        condition = edge.condition if edge and edge.condition else ""
        clock_domain = edge.clock_domain if edge and edge.clock_domain else ""
        assign_type = edge.assign_type if edge and edge.assign_type else ""

        # 计算风险分数
        risk_score = _calculate_risk(
            path_nodes, downstream_fanout, condition, clock_domain, sva_signals, cov_signals, signal
        )
        risk_level = _risk_to_level(risk_score, min_risk)

        # 检查覆盖状态
        target_covered = signal in sva_signals or signal in cov_signals
        node_covered = node_id in sva_signals or node_id in cov_signals

        coverage = {
            "sva": "covered" if node_id in sva_signals else "none",
            "covergroup": "covered" if node_id in cov_signals else "none",
        }

        # 生成建议
        suggestion = _generate_suggestion(path_nodes, risk_level, target_covered, node_covered, downstream_fanout)

        # 分类路径类型
        path_type = "combinational"
        if condition:
            path_type = "conditional"
        if assign_type == "nonblocking":
            path_type = "clocked"

        paths.append(
            {
                "path": path_nodes,
                "path_type": path_type,
                "risk": risk_level,
                "risk_score": risk_score,
                "fanout": downstream_fanout,
                "coverage": coverage,
                "condition": condition,
                "clock_domain": clock_domain,
                "suggestion": suggestion,
            }
        )

    return paths


def _get_full_load_path(signal_id: str, graph, visited: set) -> list:
    """递归获取完整的负载路径

    Args:
        signal_id: 当前信号 ID
        graph: 信号图
        visited: 已访问的节点集合（用于避免循环）

    Returns:
        list: 从当前信号开始的下游路径
    """
    if signal_id in visited:
        return []
    visited.add(signal_id)

    result = [signal_id]

    # 查找这个信号驱动的下游信号
    for succ in graph.successors(signal_id):
        edge = graph.get_edge(signal_id, succ)
        if edge and edge.kind == EdgeKind.DRIVER:
            sub_path = _get_full_load_path(succ, graph, visited)
            # 避免重复：只添加还没在 result 中的节点
            for node in sub_path[1:]:
                if node not in result:
                    result.append(node)

    return result


def _calculate_risk(
    path_nodes: list, fanout: int, condition: str, clock_domain: str, sva_signals: set, cov_signals: set, signal: str
) -> float:
    """计算路径风险分数

    Args:
        path_nodes: 路径节点列表
        fanout: 当前节点的扇出数
        condition: 驱动条件
        clock_domain: 时钟域
        sva_signals: SVA 覆盖的信号集合
        cov_signals: Covergroup 覆盖的信号集合
        signal: 目标信号

    Returns:
        float: 风险分数
    """
    score = 0.0

    # 路径长度风险
    score += len(path_nodes) * 5

    # 扇出风险
    score += fanout * 2

    # 无覆盖风险
    last_node = path_nodes[-1] if path_nodes else signal
    if last_node not in sva_signals and last_node not in cov_signals:
        score += 20

    # 高扇出风险
    if fanout > 10:
        score += 15
    elif fanout > 5:
        score += 10

    # 时钟/复位信号额外风险
    signal_name = signal.split(".")[-1].lower()
    if "clk" in signal_name or "clock" in signal_name:
        score += 20
    if "rst" in signal_name or "reset" in signal_name:
        score += 20

    # 驱动条件复杂性
    if condition:
        score += 10

    return score


def _risk_to_level(score: float, min_risk: float) -> str:
    """将风险分数转换为等级"""
    if score >= min_risk:
        return "HIGH"
    elif score >= min_risk * 0.6:
        return "MEDIUM"
    else:
        return "LOW"


def _generate_suggestion(path_nodes: list, risk: str, target_covered: bool, node_covered: bool, fanout: int) -> str:
    """生成优化建议"""
    suggestions = []

    signal_name = path_nodes[-1].split(".")[-1] if path_nodes else ""

    if risk == "HIGH":
        if not node_covered:
            suggestions.append("Add SVA or coverage for this critical path")
        if fanout > 10:
            suggestions.append(f"High fanout ({fanout}), consider local buffering")

    if "clk" in signal_name.lower() or "rst" in signal_name.lower():
        if fanout > 50:
            suggestions.append("Clock/reset network too heavy, consider clock gating or split reset")

    if not node_covered and len(path_nodes) > 2:
        suggestions.append("Long path without coverage, add intermediate checks")

    return "; ".join(suggestions)


def _extract_modules(paths: list) -> list:
    """提取所有涉及的模块"""
    modules = set()
    for path in paths:
        for node in path.get("path", []):
            parts = node.split(".")
            if len(parts) > 1:
                modules.add(parts[0])
    return sorted(list(modules))


# ==============================================================================
# Stage 3A: evidence 命令 - 召回 always/if 块完整源码
# ==============================================================================

@trace_app.command()
def evidence(
    signal: str = typer.Argument(..., help="Signal to query (e.g., top.q)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    chain: bool = typer.Option(False, "--chain", "-c", help="Show evidence for entire driver chain"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-friendly tree output (default off)"),
    tree: bool = typer.Option(False, "--tree", "-T", help="Tree-style vertical output (default off; auto for chains > 6)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments"),
) -> None:
    """展示信号的源码 evidence (enclosing always/if 块完整源码)"""
    try:
        # [Stage 5] 用公共 helper build resolver (其他 4 个命令也共用)
        resolver, _graph, _sem = _build_evidence_resolver(file=file, filelist=filelist, strict=strict, preprocess_macros=preprocess_macros)

        if chain:
            evidences = resolver.resolve_chain(signal)
            ev_dicts = [_evidence_to_dict(e) for e in evidences]
            data = {
                "ok": True,
                "command": "trace_evidence",
                "params": {"signal": signal, "file": str(file), "chain": True},
                "signal": signal,
                "evidence_chain": ev_dicts,
                "errors": [],
            }
        else:
            ev = resolver.resolve(signal)
            data = {
                "ok": True,
                "command": "trace_evidence",
                "params": {"signal": signal, "file": str(file), "chain": False},
                "signal": signal,
                "evidence": _evidence_to_dict(ev),
                "errors": [],
            }

        if json_output:
            output_json(data, pretty)
        else:
            if human and chain and isinstance(data.get("evidence_chain"), list):
                # [Stage 6 part 4] --human --tree: tree 模式渲染 chain
                from cli._evidence_helpers import render_signal_tree
                # chain list: [target, driver1, driver2, ...] (target 在前)
                chain_signals = [ev.get("signal", "?") for ev in data["evidence_chain"]]
                # 删掉开头的 target (因为我们要 append signal 在末尾, 避免重复)
                if chain_signals and chain_signals[0] == signal:
                    chain_signals = chain_signals[1:]
                # 倒序: source (最早 driver) 在前, signal (终点) 在最后
                chain_signals = list(reversed(chain_signals))
                chain_signals.append(signal)
                # 如果 source 在 chain_signals[0] 还是 signal (eg chain 只有 target 自己), 去重
                if len(chain_signals) > 1 and chain_signals[0] == chain_signals[-1]:
                    chain_signals = chain_signals[:-1]
                print(render_signal_tree(
                    chain_signals,
                    title=f"Evidence chain: {signal}",
                ))
            else:
                _output_evidence_text(data)

    except Exception as e:
        data = {"ok": False, "command": "trace_evidence", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


# [Stage 5] 移到 cli/_evidence_helpers.py,5 个命令共用


def _output_evidence_text(data: dict) -> None:
    """人友好文本输出"""
    signal = data.get("signal", "")
    print(f"Signal: {signal}")
    print("=" * 60)

    chain = data.get("evidence_chain")
    if chain is not None:
        # driver chain mode
        if not chain:
            print("  (no evidence found)")
            return
        for i, ev in enumerate(chain):
            print(f"\n[Step {i}] {ev.get('signal', '?')}")
            if ev.get("source_text"):
                print(f"  Source: {ev['source_text']!r}")
            if ev.get("enclosing_if"):
                loc = ev["enclosing_if"]
                print(f"\n  >>> Enclosing IF @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
            if ev.get("enclosing_always"):
                loc = ev["enclosing_always"]
                print(f"\n  >>> Enclosing ALWAYS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
            if ev.get("enclosing_class"):
                loc = ev["enclosing_class"]
                print(f"\n  >>> Enclosing CLASS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
            if ev.get("enclosing_constraint"):
                loc = ev["enclosing_constraint"]
                print(f"\n  >>> Enclosing CONSTRAINT @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
                for line in loc["text"].split("\n"):
                    print(f"  {line}")
        return

    ev = data.get("evidence", {})
    if not ev:
        print("  (no evidence found)")
        return
    if ev.get("source_text"):
        print(f"Source: {ev['source_text']!r}")
    if ev.get("enclosing_if"):
        loc = ev["enclosing_if"]
        print(f"\n>>> Enclosing IF @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    if ev.get("enclosing_always"):
        loc = ev["enclosing_always"]
        print(f"\n>>> Enclosing ALWAYS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    if ev.get("enclosing_class"):
        loc = ev["enclosing_class"]
        print(f"\n>>> Enclosing CLASS @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    if ev.get("enclosing_constraint"):
        loc = ev["enclosing_constraint"]
        print(f"\n>>> Enclosing CONSTRAINT @ {loc['file']}:{loc['line_start']}-{loc['line_end']}:")
        for line in loc["text"].split("\n"):
            print(line)
    chain_inner = ev.get("enclosing_chain", [])
    if chain_inner:
        print(f"\nFull chain ({len(chain_inner)} levels):")
        for i, snip in enumerate(chain_inner):
            if snip:
                preview = snip["text"][:60].replace("\n", "\\n")
                print(f"  [{i}] {snip['file']}:{snip['line_start']}-{snip['line_end']}  {preview!r}")
