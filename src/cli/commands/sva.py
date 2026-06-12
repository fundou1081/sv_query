# ==============================================================================
# sva.py - SVA 分析命令
# ==============================================================================
"""
Usage:
  python run_cli.py sva extract top.sv
  python run_cli.py sva extract top.sv --json
  python run_cli.py sva coverage top.sv
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

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.models import NodeKind
from trace.core.sva_extractor import SVAExtractor
from trace.unified_tracer import UnifiedTracer

sva_app = typer.Typer(help="SVA (SystemVerilog Assertions) analysis: extract properties, assertions, coverage gaps")


@sva_app.command(name="extract")
def extract(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图 (供分析不完整项目用)"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. Use --no-preprocess 退回 pyslang 内置处理 (供不跨文件 define 的小项目用)"),

    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """Extract SVA structures: sequences, properties, assertions"""
    # [ADD 2026-06-11 Req-9] 读 source: --filelist 走 _read_filelist, --file 走 open
    from cli._common import _read_filelist
    if filelist:
        sources = _read_filelist(filelist, base_dir=Path.cwd())
    elif file:
        with open(file) as f:
            sources = {file: f.read()}
    else:
        typer.echo("Error: --file or --filelist is required", err=True)
        raise typer.Exit(code=1)

    sva = SVAExtractor(sources, strict=strict).extract()

    if json_output:
        import json

        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "sva extract",
                    "result": {
                        "sequences": {
                            pid: {
                                "signals": p.signals,
                                "timing_ops": p.timing_ops,
                                "clock": p.clock,
                            }
                            for pid, p in sva.sequences.items()
                        },
                        "properties": {
                            pid: {
                                "signals": p.signals,
                                "operators": p.operators,
                                "clock": p.clock,
                                "disable_iff": p.disable_iff,
                            }
                            for pid, p in sva.properties.items()
                        },
                        "assertions": [
                            {
                                "id": a.id,
                                "kind": a.kind,
                                "property_ref": a.property_ref,
                                "signals": a.signals,
                            }
                            for a in sva.assertions
                        ],
                        "signal_refs": dict(sva.signal_refs),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式输出
    display_file = file if file else (list(sources.keys())[0] if sources else filelist)
    print(f"{'=' * 80}")
    print(f"SVA 提取: {display_file}")
    print(f"{'=' * 80}")

    print(f"\n  序列 (Sequences): {len(sva.sequences)}")
    for sid, seq in sva.sequences.items():
        print(f"    {sid}:")
        print(f"      信号: {seq.signals}")
        print(f"      时序: {seq.timing_ops}")
        print(f"      时钟: {seq.clock}")

    print(f"\n  属性 (Properties): {len(sva.properties)}")
    for pid, prop in sva.properties.items():
        print(f"    {pid}:")
        print(f"      信号: {prop.signals}")
        print(f"      操作符: {prop.operators}")
        print(f"      时钟: {prop.clock}")
        if prop.disable_iff:
            print(f"      disable iff: {prop.disable_iff}")

    print(f"\n  断言 (Assertions): {len(sva.assertions)}")
    for a in sva.assertions:
        print(f"    {a.id} [{a.kind}]:")
        print(f"      引用: {a.property_ref}")
        print(f"      信号: {a.signals}")

    print("\n  信号关联索引:")
    for sig, refs in sva.signal_refs.items():
        print(f"    {sig}: {refs}")


@sva_app.command(name="coverage")
def coverage(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图 (供分析不完整项目用)"),

    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. Use --no-preprocess 退回 pyslang 内置处理"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """Analyze SVA coverage: which signals have assertions, which don't"""
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
        graph = tracer.build_graph()
        sources = tracer._sources
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return
    sva = SVAExtractor(sources, strict=strict).extract()
    cov_list = CovergroupExtractor(sources, strict=strict).extract()

    # SVA 覆盖信号
    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)
    for seq in sva.sequences.values():
        sva_signals.update(seq.signals)

    # Coverage 覆盖信号
    cov_signals = set()
    for cg in cov_list:
        for cp in cg.coverpoints:
            cov_signals.add(cp.signal)

    # 所有数据信号（排除时钟）
    clock_signals = set()
    for prop in sva.properties.values():
        if prop.clock:
            clock_signals.add(prop.clock)

    data_signals = []
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node and node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.REG, NodeKind.SIGNAL):
            sn = node_id.split(".")[-1]
            if sn not in clock_signals and sn not in ("clk", "clk_i", "rst_n", "rst"):
                data_signals.append(sn)

    covered = sva_signals & set(data_signals)
    uncovered = set(data_signals) - sva_signals

    if json_output:
        import json

        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "sva coverage",
                    "result": {
                        "total_signals": len(data_signals),
                        "sva_covered": len(covered),
                        "cov_covered": len(cov_signals),
                        "uncovered_signals": sorted(uncovered),
                        "coverage_ratio": len(covered) / len(data_signals) if data_signals else 0,
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式输出
    display_file = file if file else (list(sources.keys())[0] if sources else filelist)
    print(f"{'=' * 80}")
    print(f"SVA 覆盖分析: {display_file}")
    print(f"{'=' * 80}")

    ratio = len(covered) / len(data_signals) if data_signals else 0
    print(f"\n  覆盖率: {len(covered)}/{len(data_signals)} ({ratio * 100:.1f}%)")

    if uncovered:
        print(f"\n  ⚠ 未覆盖信号 ({len(uncovered)}):")
        for sig in sorted(uncovered):
            print(f"    - {sig}")

    print(f"\n  已覆盖信号 ({len(covered)}):")
    for sig in sorted(covered):
        print(f"    ✓ {sig}")

    if cov_signals:
        print(f"\n  Coverage 覆盖 ({len(cov_signals)}):")
        for sig in sorted(cov_signals):
            print(f"    🟡 {sig}")


@sva_app.command(name="timing")
def timing(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图 (供分析不完整项目用)"),

    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. Use --no-preprocess 退回 pyslang 内置处理"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
) -> None:
    """Compare SVA timing declarations with signal graph timing depth"""
    from trace.core.graph.models import NodeKind

    def timing_depth(graph, target_id, max_comb_depth=3):
        from collections import deque

        node = graph.get_node(target_id)
        if node is None:
            return -1
        reg_nodes = set()
        for nid in graph.nodes():
            n = graph.get_node(nid)
            if n and n.kind == NodeKind.REG:
                reg_nodes.add(nid)
        primary_inputs = set()
        for nid in graph.nodes():
            n = graph.get_node(nid)
            if n and n.kind == NodeKind.PORT_IN:
                if not n.is_clock and not n.is_reset:
                    sn = nid.split(".")[-1]
                    if sn not in ("clk", "clk_i", "rst_n", "rst"):
                        primary_inputs.add(nid)
        if target_id in primary_inputs:
            return 0
        visited = set()
        queue = deque([(pi, 0) for pi in primary_inputs])
        for pi in queue:
            visited.add(pi[0])
        max_d, found = 0, False
        while queue:
            cur, depth = queue.popleft()
            if cur == target_id:
                max_d = max(max_d, depth)
                found = True
                continue
            for succ in graph.successors(cur):
                if succ in visited:
                    continue
                sn = graph.get_node(succ)
                if sn is None or sn.is_clock or sn.is_reset:
                    continue
                nd = depth + (1 if succ in reg_nodes else 0)
                visited.add(succ)
                queue.append((succ, nd))
        return max_d if found else 0

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
        graph = tracer.build_graph()
        sources = tracer._sources
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return
    sva = SVAExtractor(sources, strict=strict).extract()

    results = []
    for pid, prop in sva.properties.items():
        op = "|=>" if "|=>" in prop.operators else "|->"
        inferred_depth = 1 if op == "|=>" else 0
        results.append(
            {
                "property": pid,
                "signals": prop.signals,
                "operator": op,
                "sva_declared_depth": inferred_depth,
                "signal_depths": {},
            }
        )
        for sig in prop.signals:
            matches = [n for n in graph.nodes() if n.endswith(f".{sig}")]
            if matches:
                depth = timing_depth(graph, matches[0])
                results[-1]["signal_depths"][sig] = depth

    if json_output:
        import json

        print(json.dumps({"ok": True, "command": "sva timing", "result": results}, indent=2))
        return

    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式输出
    display_file = file if file else (list(sources.keys())[0] if sources else filelist)
    print(f"{'=' * 80}")
    print(f"SVA 时序比对: {display_file}")
    print(f"{'=' * 80}")

    print("""
  ┌──────────────────────────────┬────────────┬────────────┬───────────────────────┐
  │ Property                    │ SVA 声明   │ 推断深度   │ 信号实际深度          │
  ├──────────────────────────────┼────────────┼────────────┼───────────────────────┤""")

    for r in results:
        print(
            f"  │ {r['property']:28s} │ {r['operator']:10s} │ {r['sva_declared_depth']:10d} │ {str(r['signal_depths']):25s} │"
        )

    print("  └──────────────────────────────┴────────────┴────────────┴───────────────────────┘")


if __name__ == "__main__":
    typer.run(extract)
