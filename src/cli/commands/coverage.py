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

from trace.core.coverage_generator import ControlCoverageGenerator

coverage_app = typer.Typer(
    help="Control coverage generation: decompose signals to atomic signals"
)


@coverage_app.command(name="suggest")
def suggest(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file (单文件模式)"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"),
    strict: bool = typer.Option(False, "--strict", help="Strict mode: elaboration error 立即 raise (默认 non-strict)"),
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


if __name__ == "__main__":
    typer.run(coverage_app)
