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

warnings.filterwarnings("ignore")

from trace.core.coverage_generator import ControlCoverageGenerator

coverage_app = typer.Typer(
    help="Control coverage generation: decompose signals to atomic signals"
)


@coverage_app.command(name="suggest")
def suggest(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    signal: str = typer.Option(None, "--signal", "-s", help="Single signal to decompose (e.g., top.x)"),
    signals: str = typer.Option(None, "--signals", help="Comma-separated signals"),
    max_signals: int = typer.Option(5, "--max-signals", help="Max signal tree size"),
    max_depth: int = typer.Option(10, "--max-depth", help="Max driver chain depth"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output (TODO)"),
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
        with open(file) as f:
            source = f.read()

        tracer = UnifiedTracer(sources={file: source})
        graph = tracer.build_graph()

        gen = ControlCoverageGenerator(graph=graph)
        result = gen.decompose(
            target_signals,
            max_signals=max_signals,
            max_depth=max_depth,
        )

        # 输出 Markdown 报告
        if json_output:
            # TODO: JSON 输出
            print("JSON output not implemented yet, falling back to markdown")
        md = gen.generate_coverage_markdown(result)
        print(md)

        if result.truncated or result.error:
            raise typer.Exit(code=1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    typer.run(coverage_app)
