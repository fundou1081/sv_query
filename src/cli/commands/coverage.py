#==============================================================================
# coverage.py - 控制覆盖度生成命令
#
# Usage:
#   python run_cli.py coverage suggest -f top.sv --signal top.x
#   python run_cli.py coverage suggest -f top.sv --signal top.x --max-signals 5
#   python run_cli.py coverage suggest -f top.sv --signals "x, a, b"
#==============================================================================
"""
覆盖率分解 CLI - 根据条件驱动关系, 递归展开信号到原子信号.

V1 范围:
- 单个信号输入
- 字符串表达式解析 (含位选)
- Markdown 输出
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

from trace.core.covergroup_analyzer import CovergroupAnalyzer, CoverageGap
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.coverage_generator import ControlCoverageGenerator

coverage_app = typer.Typer(
    help="Control coverage generation: decompose signals to atomic signals"
)


@coverage_app.command(name="suggest")
def suggest(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图 (供分析不完整项目用)"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. Use --no-preprocess 退回 pyslang 内置处理 (供不跨文件 define 的小项目用)"),

    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    signal: str = typer.Option(None, "--signal", "-s", help="Single signal to decompose (e.g., top.x)"),
    signals: str = typer.Option(None, "--signals", help="Comma-separated signals (V2.B: multi-signal decomposition, merged with dedup)"),
    max_signals: int = typer.Option(5, "--max-signals", help="Max signal tree size"),
    max_depth: int = typer.Option(10, "--max-depth", help="Max driver chain depth"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output (programmatic)"),
) -> None:
    """分解信号到原子信号, 生成控制覆盖度建议"""
    from trace.unified_tracer import UnifiedTracer

    # 解析输入信号
    if signal:
        target_signals = [signal]
    elif signals:
        target_signals = [s.strip() for s in signals.split(",") if s.strip()]
    else:
        print("ERROR: 必须指定 --signal 或 --signals", file=sys.stderr)
        raise typer.Exit(code=1)

    try:
        tracer_log_level = "ERROR" if json_output else None
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
            log_level=tracer_log_level,
        
            preprocess_macros=preprocess_macros,
        )
        graph = tracer.build_graph()

        gen = ControlCoverageGenerator(graph=graph)
        result = gen.decompose(
            target_signals,
            max_signals=max_signals,
            max_depth=max_depth,
        )

        # 输出报告 (JSON 或 Markdown, 互斥)
        if json_output:
            print(result.to_json(indent=2))
        else:
            print(gen.generate_coverage_markdown(result))

        if result.truncated or result.error:
            raise typer.Exit(code=1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        raise typer.Exit(code=1) from e


@coverage_app.command(name="gap")
def gap(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode (default): elaboration error 立即 raise. Use --no-strict 优雅降级存部分图 (供分析不完整项目用)"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. Use --no-preprocess 退回 pyslang 内置处理 (供不跨文件 define 的小项目用)"),
    log_level: str = typer.Option("WARNING", "--log-level", help="Compiler log level (DEBUG/INFO/WARNING/ERROR)"),
    class_filter: str = typer.Option(None, "--class", "-c", help="Filter analysis to a specific class (e.g. packet)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output (programmatic)"),
    fail_on_gap: bool = typer.Option(False, "--fail-on-gap", help="Exit code 1 if any gap is detected (CI-friendly)"),
) -> None:
    """检测 covergroup ↔ constraint 一致性缺口.

    自动检测 3 类覆盖缺口:
      - missing_cross         条件约束引用变量对, 但 covergroup 缺少 cross
      - missing_illegal_bins  cross 已定义但缺少 illegal_bins 标记非法组合
      - missing_bins          (预留)

    Examples:
      python run_cli.py coverage gap -f top.sv
      python run_cli.py coverage gap -f top.sv --class packet
      python run_cli.py coverage gap -f top.sv --json --fail-on-gap
    """
    import json as _json

    try:
        tracer_log_level = "ERROR" if json_output else None
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
            log_level=tracer_log_level,
            preprocess_macros=preprocess_macros,
        )
        graph = tracer.build_graph()

        # 1. 提取 covergroups (使用 tracer 的 sources, 跟 graph 保持一致)
        sources = tracer.sources if hasattr(tracer, "sources") else {}
        extractor = CovergroupExtractor(sources=sources, strict=strict)
        covergroups = extractor.extract()

        # 2. 一致性分析
        analyzer = CovergroupAnalyzer(graph=graph, cgs=covergroups)
        gaps = analyzer.analyze(class_name=class_filter)

        # 3. 输出
        if json_output:
            payload = {
                "summary": {
                    "total_gaps": len(gaps),
                    "by_kind": {
                        k: sum(1 for g in gaps if g.kind == k)
                        for k in {"missing_bins", "missing_cross", "missing_illegal_bins"}
                    },
                    "covergroup_count": len(covergroups),
                    "class_filter": class_filter,
                },
                "gaps": [
                    {
                        "kind": g.kind,
                        "variable": g.variable,
                        "description": g.description,
                        "constraint_block": g.constraint_block,
                        "severity": g.severity,
                    }
                    for g in gaps
                ],
            }
            print(_json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            # Markdown 输出
            print(f"=== Covergroup ↔ Constraint Coverage Gaps ===")
            print(f"Covergroups found: {len(covergroups)}")
            if class_filter:
                print(f"Class filter: {class_filter}")
            print(f"Total gaps: {len(gaps)}")
            print()
            if not gaps:
                print("✅ No coverage gaps detected.")
            else:
                # 按 kind 分组
                by_kind: dict[str, list[CoverageGap]] = {}
                for g in gaps:
                    by_kind.setdefault(g.kind, []).append(g)
                for kind, gs in by_kind.items():
                    print(f"### {kind} ({len(gs)})")
                    for g in gs:
                        print(f"  - [{g.severity}] {g.variable}: {g.description}")
                        if g.constraint_block:
                            print(f"      ↳ constraint: {g.constraint_block}")
                    print()

        if gaps and fail_on_gap:
            raise typer.Exit(code=1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=1) from e



# ==============================================================================
# [Phase 2 2026-06-24] coverage generate - 自动生成 SystemVerilog covergroup
# ==============================================================================
# 复用 tools/coverage_gen_demo.py 的核心函数 (sys.path 加 tools/).
# 目标信号 + related signals + source file → 完整 covergroup (含 sample 条件, bins, cross).
# 策略: data (范围分 bin) vs control (离散/enum bin), sample 条件保守推断.
@coverage_app.command(name="generate")
def generate(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    signal: str = typer.Option(..., "--signal", "-s", help="Target signal to generate covergroup for (e.g. top.data_o)"),
    related: list[str] = typer.Option(None, "--related", "-r", help="Related signals for cross coverpoint (repeatable, e.g. --related mode_i --related valid_i)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    include: str = typer.Option(None, "--include", "-I", help="Include directories (comma-separated)"),
    module: str = typer.Option(None, "--module", help="限定 multi-module 文件里具体 module name"),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default: --no-strict, 适合工业多文件项目)"),
    output: str = typer.Option(None, "--output", "-o", help="Write covergroup to .sv file (default: stdout)"),
    no_header: bool = typer.Option(False, "--no-header", help="Skip 元信息 header (for golden image diff)"),
) -> None:
    """[Phase 2] 自动生成 SystemVerilog covergroup (含 sample 条件, bins, cross).

    用 sv_query 拿 signal metadata + 走 pyslang API 拿真实 width (包括  派生 +
    package typedef), 生成 covergroup.

    Examples:
        svq coverage generate -f sim/openTitan_validation.sv -s state_q -r mode_i -r valid_i
        svq coverage generate --filelist=project.f -f top.sv -s data_o -I /path/inc
        svq coverage generate -f sim/openTitan_validation.sv -s state_q -o cg_state.sv
    """
    _tools_dir = Path(__file__).resolve().parents[3] / "tools"
    if str(_tools_dir) not in sys.path:
        sys.path.insert(0, str(_tools_dir))
    from coverage_gen_demo import generate_covergroup

    related = related or []

    try:
        cg = generate_covergroup(
            file=file,
            target_signal=signal,
            related_signals=related,
            filelist=filelist,
            module_name=module,
            strict=strict,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from e

    if no_header:
        lines = cg.split(chr(10))
        out_lines = []
        for line in lines:
            if any(k in line for k in [
                "Auto-generated", "class:     ", "width:     ", "risk:      ",
                "fan_in=", "fan_out=", "generator:",
            ]):
                continue
            if line.startswith("// ===="):
                continue
            out_lines.append(line)
        cg = chr(10).join(out_lines).strip() + chr(10)

    if output:
        Path(output).write_text(cg)
        print(f"Written {len(cg)} bytes to {output}", file=sys.stderr)
    else:
        print(cg)


if __name__ == "__main__":
    typer.run(coverage_app)
