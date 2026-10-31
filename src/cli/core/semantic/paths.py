"""
core/semantic/paths.py — [iter_237] 跨模块路径查询 (`svq paths <src> <dst>`)

与 `dataflow analyze` 的分工:
  - `dataflow analyze`: 工程语境下的源→目标路径分析 (边语义/条件/风险)
  - `paths`          : **图上的路径枚举**, 含**跨模块端口映射跳转**
                       (进模块 top.u.a→sub.a; 出模块 sub.y→top.u.y)

数据源: `PathResolver` (SignalGraph + ModuleInstanceGraph)。
[iter_237] 同时修了 PathResolver 的跨模块缺陷 (旧实现只"进模块"不"出模块" → 跨模块路径恒为 None)。
"""
from __future__ import annotations

from pathlib import Path

import typer

from cli.core.semantic._bit_args import normalize_endpoint, parse_bits
from cli.core.semantic._common import build_tracer, emit, fail
from cli.core.semantic.trace_common import edge_evidence_dict


def paths_cmd(
    src: str = typer.Argument(..., help="起点信号 id (如 inst_demo.in_a)"),
    dst: str = typer.Argument(..., help="终点信号 id (如 inst_demo.add_out)"),
    all_paths: bool = typer.Option(False, "--all", "-a", help="枚举全部简单路径 (默认只给一条)"),
    directed: bool = typer.Option(
        False, "--directed", "-d",
        help="[iter_268] 只沿数据流方向搜索 (与 `dataflow analyze` 同一张有向图); "
             "默认无向 = 结构连通性 (逆流也能找到)"),
    evidence: bool = typer.Option(False, "--evidence",
                                  help="[iter_333] attach per-hop edge evidence (file/line/condition)"),
    max_paths: int = typer.Option(50, "--max", "-n", help="--all 时的路径数上限"),
    bits: str = typer.Option(
        None, "--bits",
        help="[iter_309 P15] 位级端点: 两个逗号分隔位索引（src_bit,dst_bit）；"
             "位节点缺失时回落总线并在 JSON 标 coarse_fallback"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """图上从 src 到 dst 的路径 (跨模块端口可跳转)。

    默认**无向** (结构连通性: 逆着数据流也能找到)；
    `--directed` 只沿数据流方向 (与 `dataflow analyze` 一致, iter_268 起两者结论一致)。

    例: svq paths inst_demo.in_a inst_demo.add_out --filelist project.f --json
        svq paths in_a add_out --directed --filelist project.f --json
    """
    tracer = build_tracer(file, filelist, log_level)
    if tracer is None:
        return

    resolver = tracer.get_path_resolver()
    if resolver is None:
        fail("path resolver unavailable (graph not built?)", json_output, pretty)

    graph = tracer.get_graph()
    try:
        spec = parse_bits(bits, names=("src", "dst"))
        if not spec.named and spec.positional and len(spec.positional) != 2:
            raise ValueError("--bits 需要两个值（src,dst；示例 --bits 1,5 或 7:4,3:0）")
        src_info = normalize_endpoint(graph, src, spec.get(0, "src"))
        dst_info = normalize_endpoint(graph, dst, spec.get(1, "dst"))
    except ValueError as e:
        fail(str(e), json_output, pretty)
        return
    src_id, dst_id = src_info["resolved"], dst_info["resolved"]
    bit_info = {"src": src_info, "dst": dst_info}
    coarse = bool(src_info["coarse_fallback"] or dst_info["coarse_fallback"])
    # 位/范围节点缺失 → 总线结果，显式告知调用方（不静默）
    bit_info["coarse_fallback"] = coarse

    known = set(graph.nodes()) if graph is not None else set()
    unknown = [x for x in (src_id, dst_id) if x not in known]
    if unknown:
        fail("signal id not found in graph", json_output, pretty, unknown=unknown,
             hint="用 `svq graph nodes --json` 列出可用 id")

    def _edge_ev(path):
        out = []
        for a, b in zip(path, path[1:]):
            edges = graph.get_edges(a, b)
            out.append(edge_evidence_dict(edges[0]) if edges else None)
        return out

    if all_paths:
        found = resolver.find_all_paths(src_id, dst_id, max_paths=max_paths, directed=directed)
        data = {"ok": True, "src": src, "dst": dst, "src_resolved": src_id,
                "dst_resolved": dst_id, "bits": bit_info, "directed": directed,
                "count": len(found), "truncated": len(found) >= max_paths,
                "all_paths": found}
        if evidence:
            data["edge_evidence"] = [_edge_ev(p) for p in found]
        emit(data, json_output, pretty)
        return

    one = resolver.find_path(src_id, dst_id, directed=directed)
    data = {"ok": True, "src": src, "dst": dst, "src_resolved": src_id,
            "dst_resolved": dst_id, "bits": bit_info, "directed": directed,
            "found": one is not None,
            "hop_count": (len(one) - 1) if one else None, "path": one}
    if evidence and one:
        data["edge_evidence"] = _edge_ev(one)
    emit(data, json_output, pretty)
