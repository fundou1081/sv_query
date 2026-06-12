# ==============================================================================
# verify.py - 验证缺口检测命令
# ==============================================================================
"""
验证缺口检测：找出高风险但无 SVA/Coverage 的信号，形成完整的验证优先级报告。

Usage:
  python run_cli.py verify gap -f top.sv
  python run_cli.py verify gap -f top.sv --json
  python run_cli.py verify gap -f top.sv --top 20
  python run_cli.py verify gap -f top.sv --dot /tmp/gap.dot --mmd /tmp/gap.mmd
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

# [Stage 5] evidence helper (可选 --evidence flag)
from cli._evidence_helpers import (  # noqa: E402
    make_resolver as _make_evidence_resolver,
    evidence_to_dict,
    evidence_summary_indented,
)

verify_app = typer.Typer(help="Verification gap detection: find high-risk signals without SVA/Coverage")


@verify_app.command(name="gap")
def gap(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图 (供分析不完整项目用)"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. Use --no-preprocess 退回 pyslang 内置处理 (供不跨文件 define 的小项目用)"),

    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    top_n: int = typer.Option(20, "--top", "-n", help="Show top N high-risk signals"),
    min_risk: float = typer.Option(20.0, "--min-risk", "-r", help="Minimum risk score threshold"),
    dot_output: str = typer.Option(None, "--dot", "-d", help="Output DOT file path"),
    mmd_output: str = typer.Option(None, "--mmd", "-m", help="Output Mermaid file path"),
    evidence: bool = typer.Option(False, "--evidence", "-e", help="Include source evidence for each signal (optional)"),
) -> None:
    """
    验证缺口检测：
    1. 基于信号图计算双维度风险
    2. 合并 SVA 覆盖和 Coverage 覆盖
    3. 输出高风险但无验证的信号清单
    4. 可选输出 DOT/Mermaid 图
    """
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
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        return
    sources = tracer._sources
    sva = SVAExtractor(sources, strict=strict).extract()
    cov_list = CovergroupExtractor(sources, strict=strict).extract()

    # ===== 1. 收集覆盖信息 =====
    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)
    for seq in sva.sequences.values():
        sva_signals.update(seq.signals)
    for a in sva.assertions:
        sva_signals.update(a.signals)

    cov_signals = set()
    cov_detail = {}
    for cg in cov_list:
        for cp in cg.coverpoints:
            sig = cp.signal
            cov_signals.add(sig)
            if sig not in cov_detail:
                cov_detail[sig] = []
            cov_detail[sig].extend([b.name for b in cp.bins])

    clock_signals = set()
    for prop in sva.properties.values():
        if prop.clock:
            clock_signals.add(prop.clock)

    # ===== 2. 分类所有数据信号 =====
    data_signals = {}
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        name = node_id.split(".")[-1]

        if name in ("clk", "clock", "clk_i", "rst_n", "rst", "reset", "resetn"):
            continue
        if node.is_clock or node.is_reset:
            continue

        if node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.REG, NodeKind.SIGNAL):
            data_signals[node_id] = {
                "name": name,
                "kind": str(node.kind),
                "node": node,
            }

    # ===== 3. 计算风险 + 覆盖状态 =====
    def compute_risk(node_id, info):
        node = info["node"]
        fan_in = graph.in_degree(node_id)
        fan_out = graph.out_degree(node_id)
        width_bits = max(1, node.width[1] - node.width[0] + 1) if node.width else 1
        is_reg = node.kind == NodeKind.REG
        info["name"]

        func = fan_in * 3 + fan_out * 2 + width_bits * 0.3
        func += 15 if fan_in >= 3 else 0
        func += 10 if fan_out >= 3 else 0

        timing = 15 if is_reg else 0
        timing += fan_in * 2

        return func, timing

    results = []
    for node_id, info in data_signals.items():
        name = info["name"]
        func_s, timing_s = compute_risk(node_id, info)

        has_sva = name in sva_signals
        has_cov = name in cov_signals

        if has_sva and has_cov:
            cover_status = "BOTH"
        elif has_sva:
            cover_status = "SVA"
        elif has_cov:
            cover_status = "COV"
        else:
            cover_status = "NONE"

        results.append(
            {
                "node_id": node_id,
                "name": name,
                "kind": info["kind"],
                "fan_in": graph.in_degree(node_id),
                "fan_out": graph.out_degree(node_id),
                "func_score": round(func_s, 1),
                "timing_score": round(timing_s, 1),
                "total_risk": round(func_s + timing_s, 1),
                "has_sva": has_sva,
                "has_cov": has_cov,
                "cover_status": cover_status,
                "cov_bins": cov_detail.get(name, []),
            }
        )

    results.sort(key=lambda x: x["total_risk"], reverse=True)

    gap_signals = [r for r in results if r["total_risk"] >= min_risk and r["cover_status"] == "NONE"]
    all_signals = results[:top_n]

    # ===== 3.5. (可选) evidence 召回 =====
    evidence_resolver = None
    if evidence:
        evidence_resolver = _make_evidence_resolver(graph, tracer._get_adapter())
        # [Stage 5] 批量给 top_signals + gap_signals 补 evidence 字段
        for r in all_signals:
            r["evidence"] = evidence_to_dict(evidence_resolver.resolve(r["node_id"]))
        for r in gap_signals:
            r["evidence"] = evidence_to_dict(evidence_resolver.resolve(r["node_id"]))

    # ===== 4. JSON 输出 =====
    if json_output:
        import json

        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "verify gap",
                    "file": file,
                    "summary": {
                        "total_data_signals": len(results),
                        "sva_covered": len([r for r in results if r["has_sva"]]),
                        "cov_covered": len([r for r in results if r["has_cov"]]),
                        "both_covered": len([r for r in results if r["has_sva"] and r["has_cov"]]),
                        "uncovered": len([r for r in results if r["cover_status"] == "NONE"]),
                        "high_risk_uncovered": len(gap_signals),
                    },
                    "top_signals": all_signals,
                    "gap_signals": gap_signals,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    # ===== 5. 生成图输出 =====
    if dot_output or mmd_output:
        _generate_gap_graph(results, gap_signals, cov_detail, dot_output, mmd_output)

    # ===== 6. 文本输出 =====
    # [ADD 2026-06-11 Req-9] 统一 file/filelist 模式输出
    display_file = file if file else (list(tracer._sources.keys())[0] if tracer._sources else filelist)
    print(f"{'=' * 80}")
    print(f"验证缺口分析: {display_file}")
    print(f"{'=' * 80}")

    total = len(results)
    sva_cnt = len([r for r in results if r["has_sva"]])
    cov_cnt = len([r for r in results if r["has_cov"]])
    both_cnt = len([r for r in results if r["has_sva"] and r["has_cov"]])
    none_cnt = len([r for r in results if r["cover_status"] == "NONE"])
    gap_cnt = len(gap_signals)

    print("\n  📊 信号统计:")
    print(f"     总数据信号: {total}")
    print(f"     SVA 覆盖: {sva_cnt} ({sva_cnt / total * 100:.1f}%)")
    print(f"     Coverage 覆盖: {cov_cnt} ({cov_cnt / total * 100:.1f}%)")
    print(f"     两者都有: {both_cnt}")
    print(f"     完全没有: {none_cnt} ({none_cnt / total * 100:.1f}%)")

    print(f"\n  🚨 高风险缺口 (风险≥{min_risk} 且无覆盖): {gap_cnt}")
    print("\n  图例: ✓=SVA覆盖  🟡=Coverage覆盖  ✓🟡=两者都有  ✗=无覆盖")

    if gap_signals:
        print("\n  【需要优先补充验证的信号】")
        print(f"  {'排名':4s} {'信号':25s} {'类型':6s} {'功能分':7s} {'时序分':7s} {'覆盖'}")
        print(f"  {'─' * 4} {'─' * 25} {'─' * 6} {'─' * 7} {'─' * 7} {'─' * 6}")
        for i, r in enumerate(gap_signals[:10], 1):
            kind_short = {"PORT_IN": "IN", "PORT_OUT": "OUT", "REG": "REG", "SIGNAL": "SIG"}.get(r["kind"], "?")
            status_icon = "✓" if r["has_sva"] else ("🟡" if r["has_cov"] else "✗")
            level = "🔴" if r["total_risk"] >= 40 else ("🟠" if r["total_risk"] >= 25 else "🟡")
            print(
                f"  {i:4d} {r['name']:25s} {kind_short:6s} {level}{r['func_score']:5.1f} {r['timing_score']:5.1f} {status_icon}"
            )
            # [Stage 5] 可选 evidence 1 行摘要
            if evidence and r.get("evidence"):
                summary = evidence_summary_indented(r["evidence"])
                if summary:
                    print(summary)
        if len(gap_signals) > 10:
            print(f"  ... 还有 {len(gap_signals) - 10} 个高风险信号")

    print(f"\n  【Top {min(top_n, len(all_signals))} 高风险信号详情】")
    print(f"  {'排名':4s} {'信号':25s} {'类型':6s} {'fan_in':6s} {'fan_out':7s} {'功能分':6s} {'时序分':6s} {'覆盖'}")
    print(f"  {'─' * 4} {'─' * 25} {'─' * 6} {'─' * 6} {'─' * 7} {'─' * 6} {'─' * 6} {'─' * 6}")

    for i, r in enumerate(all_signals, 1):
        kind_short = {"PORT_IN": "IN", "PORT_OUT": "OUT", "REG": "REG", "SIGNAL": "SIG"}.get(r["kind"], "?")
        if r["cover_status"] == "BOTH":
            status_icon = "✓🟡"
        elif r["cover_status"] == "SVA":
            status_icon = "✓"
        elif r["cover_status"] == "COV":
            status_icon = "🟡"
        else:
            status_icon = "✗"

        level_f = (
            "🔴"
            if r["func_score"] >= 40
            else ("🟠" if r["func_score"] >= 25 else ("🟡" if r["func_score"] >= 15 else "🟢"))
        )
        level_t = (
            "🔴"
            if r["timing_score"] >= 40
            else ("🟠" if r["timing_score"] >= 25 else ("🟡" if r["timing_score"] >= 15 else "🟢"))
        )
        print(
            f"  {i:4d} {r['name']:25s} {kind_short:6s} {r['fan_in']:6d} {r['fan_out']:7d} {level_f}{r['func_score']:5.1f} {level_t}{r['timing_score']:5.1f} {status_icon}"
        )
        # [Stage 5] 可选 evidence 1 行摘要
        if evidence and r.get("evidence"):
            summary = evidence_summary_indented(r["evidence"])
            if summary:
                print(summary)

    if cov_detail:
        print("\n  【Coverage bins 详情】")
        for sig, bins in sorted(cov_detail.items()):
            print(f"    {sig}: {', '.join(bins)}")

    if dot_output:
        print(f"\n  ✓ DOT 图已输出: {dot_output}")
        print(f"    渲染: dot -Tpng {dot_output} -o output.png")
    if mmd_output:
        print(f"\n  ✓ Mermaid 图已输出: {mmd_output}")


def _generate_gap_graph(results, gap_signals, cov_detail, dot_output, mmd_output):
    """生成验证缺口的 DOT 和 Mermaid 图"""
    import re

    risk_colors = {"CRITICAL": "#ff0000", "HIGH": "#ff8800", "MEDIUM": "#ffcc00", "LOW": "#00cc00"}
    cover_colors = {"BOTH": "#00aa00", "SVA": "#0088ff", "COV": "#ffaa00", "NONE": "#ff0000"}

    # DOT 输出
    if dot_output:
        dot_lines = [
            "digraph verification_gap {",
            "  rankdir=TB;",
            '  node [shape=box style="rounded,filled" fontname="Helvetica"];',
            '  label="Verification Gap Analysis\\nRed=Uncovered, Green=Covered";',
            "",
            "  subgraph cluster_summary {",
            '    style=dashed; color=gray; label="Summary";',
        ]

        total = len(results)
        gap_cnt = len(gap_signals)
        sva_cnt = len([r for r in results if r["has_sva"]])
        cov_cnt = len([r for r in results if r["has_cov"]])

        dot_lines.append(f'    total[label="Total: {total}" shape=ellipse];')
        dot_lines.append(f'    gap_count[label="Gap: {gap_cnt}" shape=ellipse color=red];')
        dot_lines.append(f'    sva_cov[label="SVA: {sva_cnt} Coverage: {cov_cnt}" shape=ellipse color=blue];')
        dot_lines.append("  }")
        dot_lines.append("")

        dot_lines.append("  subgraph cluster_high_risk {")
        dot_lines.append('    style=filled; color="#ffeeee"; label="High Risk Gaps"; fontname="Helvetica";')
        for r in gap_signals[:15]:
            name_safe = re.sub(r"[^a-zA-Z0-9_]", "_", r["name"])
            func_s = r["func_score"]
            timing_s = r["timing_score"]
            risk_lvl = "CRITICAL" if func_s >= 40 else ("HIGH" if func_s >= 25 else "MEDIUM")
            color = risk_colors.get(risk_lvl, "#888888")
            cov_color = cover_colors.get(r["cover_status"], "#888888")
            label = f"{r['name']}\\nF={func_s:.0f} T={timing_s:.0f}\\n{r['cover_status']}"
            dot_lines.append(f'    gap_{name_safe}[label="{label}" color="{cov_color}" fillcolor="{color}22"];')
        dot_lines.append("  }")
        dot_lines.append("")

        covered = [r for r in results if r["cover_status"] != "NONE"][:20]
        if covered:
            dot_lines.append("  subgraph cluster_covered {")
            dot_lines.append('    style=filled; color="#eeffee"; label="Covered Signals"; fontname="Helvetica";')
            for r in covered:
                name_safe = re.sub(r"[^a-zA-Z0-9_]", "_", r["name"])
                func_s = r["func_score"]
                timing_s = r["timing_score"]
                cov_color = cover_colors.get(r["cover_status"], "#888888")
                label = f"{r['name']}\\nF={func_s:.0f} T={timing_s:.0f}\\n{r['cover_status']}"
                dot_lines.append(f'    cov_{name_safe}[label="{label}" color="{cov_color}" fillcolor="#ccffcc"];')
            dot_lines.append("  }")

        dot_lines.append("}")

        with open(dot_output, "w") as f:
            f.write("\n".join(dot_lines))

    # Mermaid 输出
    if mmd_output:
        sva_count = len([r for r in results if r["has_sva"]])
        cov_count = len([r for r in results if r["has_cov"]])
        mmd_lines = [
            "flowchart TB",
            "    direction TB",
            '    subgraph Summary["📊 统计"]',
            f'    S1["总信号: {len(results)}"]',
            f'    S2["🚨 缺口: {len(gap_signals)}"]',
            f'    S3["SVA覆盖: {sva_count}  Cov覆盖: {cov_count}"]',
            "    end",
            "",
            '    subgraph HighRisk["🚨 高风险缺口 (Top 15)"]',
        ]

        for r in gap_signals[:15]:
            name_safe = re.sub(r"[^a-zA-Z0-9_]", "_", r["name"])
            func_s = r["func_score"]
            timing_s = r["timing_score"]
            risk_lvl = "CRITICAL" if func_s >= 40 else ("HIGH" if func_s >= 25 else "MEDIUM")
            icon = "🔴" if risk_lvl == "CRITICAL" else ("🟠" if risk_lvl == "HIGH" else "🟡")
            mmd_lines.append(f'    G_{name_safe}["{icon} {r["name"]}\\nF={func_s:.0f} T={timing_s:.0f} ✗"]')

        mmd_lines.append("    end")
        mmd_lines.append("")
        mmd_lines.append('    subgraph Covered["✓ 已覆盖信号 (Top 20)"]')

        covered = [r for r in results if r["cover_status"] != "NONE"][:20]
        if not covered:
            mmd_lines.append('    CN["(无已覆盖信号)"]')
        else:
            for r in covered:
                name_safe = re.sub(r"[^a-zA-Z0-9_]", "_", r["name"])
                func_s = r["func_score"]
                status_icon = "✓🟡" if r["cover_status"] == "BOTH" else ("✓" if r["cover_status"] == "SVA" else "🟡")
                mmd_lines.append(f'    C_{name_safe}["{status_icon} {r["name"]}\\nF={func_s:.0f} {r["cover_status"]}"]')

        mmd_lines.append("    end")
        mmd_lines.append("")
        mmd_lines.append('    subgraph Legend["📖 图例"]')
        mmd_lines.append('    L1["🔴 CRITICAL ≥40"]')
        mmd_lines.append('    L2["🟠 HIGH ≥25"]')
        mmd_lines.append('    L3["🟡 MEDIUM ≥15"]')
        mmd_lines.append('    L4["🟢 LOW <15"]')
        mmd_lines.append('    L5["✓ SVA覆盖"]')
        mmd_lines.append('    L6["🟡 Coverage覆盖"]')
        mmd_lines.append('    L7["✗ 无覆盖"]')
        mmd_lines.append("    end")

        with open(mmd_output, "w") as f:
            f.write("\n".join(mmd_lines))


if __name__ == "__main__":
    typer.run(gap)
