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
)


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
        for load in loads:
            dist = load.get("distance", "")
            kind = load.get("kind", "")
            print(f"  [{dist}] {load['id']} ({kind})")

    elif command == "trace_impact":
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
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    depth: int | None = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Trace signal drivers (fanin)"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
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

        data = {
            "ok": True,
            "command": "trace_fanin",
            "params": {"signal": signal, "file": str(file), "depth": depth},
            "result": {"drivers": drivers},
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

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
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    depth: int | None = typer.Option(None, "--depth", "-d", help="Max trace depth (None=unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Trace signal loads (fanout)"""
    try:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source})
        _ = tracer.build_graph()

        result = tracer.trace_fanout(signal, depth=depth)

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

        data = {
            "ok": True,
            "command": "trace_fanout",
            "params": {"signal": signal, "file": str(file), "depth": depth},
            "result": {"loads": loads},
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

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
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    min_risk: float = typer.Option(30.0, "--min-risk", "-r", help="Minimum risk score for high-risk"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Analyze impact of changing a signal

    Traces downstream loads (fanout) and assesses:
    - Impact paths and their risk levels
    - Coverage status (SVA/Covergroup)
    - Suggestions for safe modification
    """
    try:
        with open(str(file)) as f:
            source = f.read()

        tracer = UnifiedTracer(sources={str(file): source})
        graph = tracer.build_graph()

        # 提取 SVA 和 Coverage 信息
        sva_extractor = SVAExtractor({str(file): source})
        sva_data = sva_extractor.extract()
        cov_extractor = CovergroupExtractor({str(file): source})
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
            output_text(data)

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
    file: Path = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    chain: bool = typer.Option(False, "--chain", "-c", help="Show evidence for entire driver chain"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """展示信号的源码 evidence (enclosing always/if 块完整源码)"""
    try:
        # [Stage 5] 用公共 helper build resolver (其他 4 个命令也共用)
        resolver, _graph, _sem = _build_evidence_resolver(file)

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
