#==============================================================================
# design.py - Plan B [Design Understanding B 2026-07-08]: IP-level design
#             high-order view that aggregates insights from cdc/protocol/
#             handshake/backpressure/dataflow/timing/risk sub-commands.
#
# Usage:
#   sv_query design show -f top.sv --target <top>           # human-readable
#   sv_query design show -f top.sv --target <top> --json    # JSON
#   sv_query design show --filelist <.f> --target <top>     # multi-file
#
# Design: not re-implementing analysis. Just CALLS the existing sub-commands
#         (cdc analyze, protocol detect, handshake scan, backpressure analyze,
#          dataflow analyze, timing analyze) and prints a unified summary.
#==============================================================================
"""
[Plan B 2026-07-08] 设计理解高阶 wrapper.

整合 sv_query 已有的子命令:
  - cdc analyze      → 时钟域交叉检测
  - protocol detect  → bus 协议识别 (AXI/TL-UL/...)
  - handshake scan   → ready/valid 握手分类
  - backpressure     → backpressure 链 + deadlock
  - dataflow analyze → 数据流路径
  - timing analyze   → critical path depth

目标: 一个命令看 IP-level 设计理解 (purpose, protocols, handshake, CDC, ...).
"""
import json
import sys
from pathlib import Path
from typing import Optional

import typer

design_app = typer.Typer(
    help="[Plan B 2026-07-08] IP-level design understanding (aggregates cdc/protocol/handshake/backpressure/dataflow/timing insights)",
    no_args_is_help=True,
)


def _section_header(title: str) -> str:
    """统一 section header 风格."""
    line = "=" * 60
    return f"\n{line}\n{title}\n{line}"


def _subsection_header(title: str) -> str:
    """子 section."""
    return f"\n  {title}\n  {'-' * 40}"


def _call_subcommand(args: list[str], timeout: int = 60, prepend_svq: bool = True) -> tuple[int, str, str]:
    """调用 sv_query sub-command. Returns (rc, stdout, stderr).

    Args:
        args: 命令参数
        timeout: 超时秒数
        prepend_svq: 是否在 args 前面加 'sv_query' (默认 True; 传 False 可调外部命令如 dot/mmdc)
    """
    import subprocess
    try:
        cmd = (["sv_query"] + args) if prepend_svq else args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"[TIMEOUT after {timeout}s]"
    except Exception as e:
        return -2, "", f"[ERROR: {e}]"


def _run_cdc(file: str | None, filelist: str | None, target: str, strict: bool) -> dict:
    """调用 cdc analyze, 返回 summary dict."""
    args = ["cdc", "analyze"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    if not strict:
        args.append("--no-strict")
    rc, out, err = _call_subcommand(args, timeout=120)
    return {
        "available": rc == 0,
        "raw_output": out,
        "stderr": err,
        "exit_code": rc,
    }


def _run_protocol(file: str | None, filelist: str | None, target: str, strict: bool) -> dict:
    """调用 protocol detect."""
    args = ["protocol", "detect"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    args.extend(["--module", target])
    if not strict:
        args.append("--no-strict")
    rc, out, err = _call_subcommand(args, timeout=120)
    return {
        "available": rc == 0,
        "raw_output": out,
        "stderr": err,
        "exit_code": rc,
    }


def _run_handshake(file: str | None, filelist: str | None, target: str, strict: bool) -> dict:
    """调用 handshake scan."""
    args = ["handshake", "scan"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    if not strict:
        args.append("--no-strict")
    rc, out, err = _call_subcommand(args, timeout=120)
    return {
        "available": rc == 0,
        "raw_output": out,
        "stderr": err,
        "exit_code": rc,
    }


def _run_backpressure(file: str | None, filelist: str | None, target: str, strict: bool) -> dict:
    """调用 backpressure analyze (不需 --module, 自动 scan).

    Note: backpressure analyze 不支持 --no-strict, 所以不管 strict 传不传都跳过.
    """
    args = ["backpressure", "analyze"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    # backpressure analyze 不接受 --no-strict
    rc, out, err = _call_subcommand(args, timeout=120)
    return {
        "available": rc == 0,
        "raw_output": out,
        "stderr": err,
        "exit_code": rc,
    }


def _run_dataflow(file: str | None, filelist: str | None, target: str, strict: bool,
                  from_signal: str = "", to_signal: str = "") -> dict:
    """调用 dataflow analyze (需要 FROM/TO signal).

    If not provided, use first input port as FROM and first output port as TO.
    """
    if not from_signal or not to_signal:
        # 试自动推断: 用 first input → first output
        # fallback: 常见 IP signals
        from_signal = from_signal or f"{target}.phy_tx_start"
        to_signal = to_signal or f"{target}.result_i"
    args = ["dataflow", "analyze", from_signal, to_signal]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    if not strict:
        args.append("--no-strict")
    rc, out, err = _call_subcommand(args, timeout=120)
    return {
        "available": rc == 0,
        "raw_output": out,
        "stderr": err,
        "exit_code": rc,
        "from_signal": from_signal,
        "to_signal": to_signal,
    }


def _run_timing(file: str | None, filelist: str | None, target: str, strict: bool) -> dict:
    """调用 timing analyze."""
    args = ["timing", "analyze"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    if not strict:
        args.append("--no-strict")
    rc, out, err = _call_subcommand(args, timeout=120)
    return {
        "available": rc == 0,
        "raw_output": out,
        "stderr": err,
        "exit_code": rc,
    }


def _generate_graphs(file: str | None, filelist: str | None, target: str, strict: bool,
                     output_dir: str) -> dict:
    """[Plan B 2026-07-08] 生成可视化图 (dataflow / pipeline / backpressure).

    Calls visualize dataflow / visualize pipeline / backpressure analyze,
    saves outputs as DOT/Mermaid files, then renders to PNG/SVG if possible.

    Returns dict of {graph_name: {dot_path, png_path, status}}.
    """
    import os
    from pathlib import Path

    os.makedirs(output_dir, exist_ok=True)
    graphs = {}

    # 1. visualize dataflow
    dot_path = f"{output_dir}/dataflow.dot"
    args = ["visualize", "dataflow"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    if not strict:
        args.append("--no-strict")
    args.extend(["--dot", dot_path])
    rc, out, err = _call_subcommand(args, timeout=180)
    graphs["dataflow"] = {
        "dot_path": dot_path if os.path.exists(dot_path) else None,
        "exit_code": rc,
        "stderr": err[:200] if err else "",
    }
    # try render DOT -> PNG
    if graphs["dataflow"]["dot_path"]:
        png_path = f"{output_dir}/dataflow.png"
        rc2, out2, err2 = _call_subcommand(
            ["dot", "-Tpng", "-Gdpi=60", dot_path, "-o", png_path],
            timeout=300,
            prepend_svq=False,  # dot is external command, not sv_query sub
        )
        if rc2 == 0 and os.path.exists(png_path):
            graphs["dataflow"]["png_path"] = png_path
        else:
            graphs["dataflow"]["png_path"] = None
            graphs["dataflow"]["render_error"] = err2[:200] if err2 else ""

    # 2. visualize pipeline
    dot_path = f"{output_dir}/pipeline.dot"
    args = ["visualize", "pipeline"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    if not strict:
        args.append("--no-strict")
    args.extend(["--dot", dot_path])
    rc, out, err = _call_subcommand(args, timeout=180)
    graphs["pipeline"] = {
        "dot_path": dot_path if os.path.exists(dot_path) else None,
        "exit_code": rc,
        "stderr": err[:200] if err else "",
    }
    if graphs["pipeline"]["dot_path"]:
        png_path = f"{output_dir}/pipeline.png"
        rc2, out2, err2 = _call_subcommand(
            ["dot", "-Tpng", "-Gdpi=60", dot_path, "-o", png_path],
            timeout=300,
            prepend_svq=False,  # dot is external command
        )
        if rc2 == 0 and os.path.exists(png_path):
            graphs["pipeline"]["png_path"] = png_path
        else:
            graphs["pipeline"]["png_path"] = None
            graphs["pipeline"]["render_error"] = err2[:200] if err2 else ""

    # 3. backpressure analyze (Mermaid)
    mmd_path = f"{output_dir}/backpressure.mmd"
    args = ["backpressure", "analyze"]
    if filelist:
        args.extend(["--filelist", filelist])
    elif file:
        args.extend(["-f", file])
    args.extend(["-o", mmd_path])
    rc, out, err = _call_subcommand(args, timeout=180)
    graphs["backpressure"] = {
        "mmd_path": mmd_path if os.path.exists(mmd_path) else None,
        "exit_code": rc,
        "stderr": err[:200] if err else "",
    }
    # try render Mermaid -> SVG (mmdc)
    if graphs["backpressure"]["mmd_path"]:
        svg_path = f"{output_dir}/backpressure.svg"
        rc2, out2, err2 = _call_subcommand(
            ["mmdc", "-i", mmd_path, "-o", svg_path],
            timeout=60,
            prepend_svq=False,  # mmdc is external command
        )
        if rc2 == 0 and os.path.exists(svg_path):
            graphs["backpressure"]["svg_path"] = svg_path
        else:
            graphs["backpressure"]["svg_path"] = None

    return graphs


def _extract_cdc_summary(cdc_raw: str) -> str:
    """从 cdc analyze 原始输出提取关键 insights."""
    lines = cdc_raw.split("\n")
    insights = []
    in_summary = False
    for line in lines:
        if "时钟域" in line or "Clock Domain" in line.lower() or "CDC" in line:
            in_summary = True
        if in_summary:
            # 提取关键行 (含中文/数字/风险标记)
            if any(marker in line for marker in [
                "总计", "高风险", "低风险", "未发现", "domain",
                "总计", "高风险", "🟢", "🔴", "🟡",
            ]):
                insights.append(line.strip())
    if not insights:
        # 退而求其次, 提取最后 10 行
        return "\n".join(lines[-15:])
    return "\n".join(insights[:10])


def _extract_protocol_summary(protocol_raw: str) -> str:
    """从 protocol detect 原始输出提取关键 insights."""
    lines = protocol_raw.split("\n")
    insights = []
    for line in lines:
        if any(marker in line for marker in [
            "Detected:", "confidence", "Channel", "AXI", "TL-UL",
            "AHB", "Wishbone", "APB", "Score",
        ]):
            insights.append(line.strip())
    if not insights:
        return "\n".join(lines[-15:])
    return "\n".join(insights[:10])


def _extract_handshake_summary(handshake_raw: str) -> str:
    """从 handshake scan 提取关键 insights."""
    lines = handshake_raw.split("\n")
    insights = []
    for line in lines:
        if any(marker in line.lower() for marker in [
            "ready", "valid", "handshake", "pair", "score", "type",
        ]):
            insights.append(line.strip())
    if not insights:
        return "\n".join(lines[-15:])
    return "\n".join(insights[:10])


def _extract_backpressure_summary(bp_raw: str) -> str:
    """从 backpressure analyze 提取关键 insights."""
    lines = bp_raw.split("\n")
    insights = []
    for line in lines:
        if any(marker in line.lower() for marker in [
            "backpressure", "chain", "deadlock", "path", "topology",
        ]):
            insights.append(line.strip())
    if not insights:
        return "\n".join(lines[-15:])
    return "\n".join(insights[:10])


def _extract_dataflow_summary(df_raw: str) -> str:
    """从 dataflow analyze 提取关键 insights."""
    lines = df_raw.split("\n")
    insights = []
    for line in lines:
        if any(marker in line.lower() for marker in [
            "dataflow", "path", "depth", "cycles", "register",
        ]):
            insights.append(line.strip())
    if not insights:
        return "\n".join(lines[-15:])
    return "\n".join(insights[:10])


def _extract_timing_summary(timing_raw: str) -> str:
    """从 timing analyze 提取关键 insights."""
    lines = timing_raw.split("\n")
    insights = []
    for line in lines:
        if any(marker in line.lower() for marker in [
            "timing", "critical", "depth", "path", "register", "dag",
        ]):
            insights.append(line.strip())
    if not insights:
        return "\n".join(lines[-15:])
    return "\n".join(insights[:10])


@design_app.command(name="show")
def show(
    file: str | None = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str | None = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    target: str = typer.Option("top", "--target", "-t", help="Target module name (default: top)"),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default: --no-strict for partial AST)"),
    output_json: bool = typer.Option(False, "--json", help="Output JSON format (programmatic access)"),
    graph: bool = typer.Option(False, "--graph", help="[Plan B+ 2026-07-08] Auto-generate visualization graphs (dataflow/pipeline/backpressure)"),
    graph_dir: str = typer.Option("/tmp/sv_query_design_graphs", "--graph-dir", help="Output directory for --graph images"),
    skip: list[str] = typer.Option([], "--skip", help="Skip sub-commands: cdc,protocol,handshake,backpressure,dataflow,timing"),
):
    """[Plan B 2026-07-08] IP-level design understanding (aggregates insights from
    cdc/protocol/handshake/backpressure/dataflow/timing sub-commands).

    例子:
      sv_query design show -f top.sv --target <top>
      sv_query design show --filelist=project.f --target <top> --no-strict
      sv_query design show --filelist=project.f --target <top> --json
      sv_query design show -f top.sv --target <top> --skip cdc --skip timing
    """
    if not file and not filelist:
        typer.echo("Error: need --file or --filelist", err=True)
        raise typer.Exit(1)

    skip_set = set(skip)
    source_label = filelist if filelist else file

    if not output_json:
        # ============ IP-Level Overview ============
        print(_section_header("IP-Level Design Understanding"))
        print(f"  Target:    {target}")
        print(f"  Source:    {source_label}")
        print(f"  Strict:    {strict}")
        print(f"  Skip:      {', '.join(sorted(skip_set)) if skip_set else 'none'}")

    # ============ 跑 sub-commands ============
    results = {}

    if "cdc" not in skip_set:
        results["cdc"] = _run_cdc(file, filelist, target, strict)
    if "protocol" not in skip_set:
        results["protocol"] = _run_protocol(file, filelist, target, strict)
    if "handshake" not in skip_set:
        results["handshake"] = _run_handshake(file, filelist, target, strict)
    if "backpressure" not in skip_set:
        results["backpressure"] = _run_backpressure(file, filelist, target, strict)
    if "dataflow" not in skip_set:
        results["dataflow"] = _run_dataflow(file, filelist, target, strict)
    if "timing" not in skip_set:
        results["timing"] = _run_timing(file, filelist, target, strict)

    if output_json:
        # JSON 模式: 输出 raw_output + summary
        output = {
            "target": target,
            "source": source_label,
            "strict": strict,
            "skipped": sorted(skip_set),
            "results": {
                k: {
                    "available": v["available"],
                    "exit_code": v["exit_code"],
                    "summary": _extract_summary_for_key(k, v["raw_output"]),
                    "raw": v["raw_output"][:2000] if v["raw_output"] else "",  # cap size
                }
                for k, v in results.items()
            },
        }
        if graph:
            output["graphs"] = _generate_graphs(file, filelist, target, strict, graph_dir)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Human-readable 模式
        for sub_name in ["cdc", "protocol", "handshake", "backpressure", "dataflow", "timing"]:
            if sub_name not in results:
                continue
            r = results[sub_name]
            section_title = {
                "cdc": "CDC (Clock Domain Crossing) Analysis",
                "protocol": "Bus Protocol Detection",
                "handshake": "Handshake (ready/valid) Classification",
                "backpressure": "Backpressure Topology",
                "dataflow": "Dataflow Critical Paths",
                "timing": "Timing Critical Path Analysis",
            }[sub_name]
            print(_section_header(section_title))
            if not r["available"]:
                print(f"  ⚠️  Sub-command failed (exit={r['exit_code']})")
                if r["stderr"]:
                    print(f"  stderr: {r['stderr'][:200]}")
            summary = _extract_summary_for_key(sub_name, r["raw_output"])
            print(summary)

        print(_section_header("End of Design Summary"))
        print("  Use --json for programmatic access.")
        print("  Use --skip <name> to skip a sub-command (cdc/protocol/handshake/backpressure/dataflow/timing).")

        if graph:
            print(_section_header("Generating Visualization Graphs"))
            print(f"  Output dir: {graph_dir}")
            graphs = _generate_graphs(file, filelist, target, strict, graph_dir)
            for gname, ginfo in graphs.items():
                if ginfo.get("exit_code") != 0:
                    print(f"  ⚠️  {gname}: sub-command failed (exit={ginfo['exit_code']})")
                    if ginfo.get("stderr"):
                        print(f"      stderr: {ginfo['stderr'][:200]}")
                    continue
                png = ginfo.get("png_path") or ginfo.get("svg_path")
                if png:
                    print(f"  ✅ {gname}: {png}")
                else:
                    print(f"  ⚠️  {gname}: DOT/MMD generated but PNG/SVG render failed")


def _extract_summary_for_key(key: str, raw: str) -> str:
    """Dispatch summary extractor."""
    extractors = {
        "cdc": _extract_cdc_summary,
        "protocol": _extract_protocol_summary,
        "handshake": _extract_handshake_summary,
        "backpressure": _extract_backpressure_summary,
        "dataflow": _extract_dataflow_summary,
        "timing": _extract_timing_summary,
    }
    if key in extractors:
        return extractors[key](raw)
    return raw[-500:] if raw else "(no output)"


@design_app.callback(invoke_without_command=True)
def _design_default(ctx: typer.Context):
    """Default: show help if no subcommand."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        ctx.exit()