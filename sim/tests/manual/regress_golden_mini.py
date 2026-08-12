"""regress_golden_mini.py — case1-28 全量 strict regression

[Plan 2026-08-12] 用 extract_target() 自动找 target_module, 跑所有
golden_mini fixture 的 strict 模式, 报告 pass/fail.

用法:
    # 全量回归
    python3 -m sim.tests.manual.regress_golden_mini

    # 指定子目录
    python3 -m sim.tests.manual.regress_golden_mini --dir sim/tests/integration/dataflow_fixtures

    # 标准模式 (而不是 strict)
    python3 -m sim.tests.manual.regress_golden_mini --level standard

    # 单文件
    python3 -m sim.tests.manual.regress_golden_mini --files foo.sv bar.sv

退出码:
    0  — 全部 pass
    1  — 有 fail 或 EXCEPTION
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / 'src'))

from cli._viz_common import build_viz_tracer  # noqa: E402
from trace.core.graph.analyzer.signal_classifier import classify_graph  # noqa: E402
from trace.core.graph.viz import VizBuildOptions, build_viz_data  # noqa: E402
from trace.core.graph.viz.checker import check_viz_render  # noqa: E402
from trace.core.graph.viz.viz_engine import render_dataflow  # noqa: E402

from .extract_target import extract_target  # noqa: E402

DEFAULT_DIR = Path('sim/tests/fixtures/golden_mini')


def _run_case(fix: Path, level: str) -> tuple[bool, str]:
    """跑单个 case, 返 (passed, short_message)."""
    try:
        target = extract_target(fix)
    except Exception as e:
        return False, f'EXTRACT_TARGET: {e}'

    try:
        _, graph = build_viz_tracer(
            file=str(fix), filelist=None, include=None,
            strict=True, target_module=target)
        classification = classify_graph(graph)
        viz = build_viz_data(graph, VizBuildOptions(
            target_module=target, include_edge_expression=True,
            classification=classification, include_node_class=True))
        svg = render_dataflow(viz)
        report = check_viz_render(viz, layout=None, svg=svg, level=level)
        ok = all(
            r.passed for r in (
                report.layer_a + report.layer_b + report.layer_c + report.layer_d
            )
        )
        if ok:
            return True, target
        # 抓第一个失败 reason
        for layer in (report.layer_a, report.layer_b, report.layer_c, report.layer_d):
            for r in layer:
                if not r.passed and r.errors:
                    return False, f'{target}: {r.errors[0][:80]}'
        return False, f'{target}: <no error message>'
    except Exception as e:
        return False, f'{target}: EXCEPTION {type(e).__name__}: {str(e)[:80]}'


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='golden_mini fixture strict regression',
    )
    parser.add_argument(
        '--dir', type=Path, default=DEFAULT_DIR,
        help=f'fixture 目录 (默认: {DEFAULT_DIR})',
    )
    parser.add_argument(
        '--level', choices=('basic', 'standard', 'strict'), default='strict',
        help='check_viz_render level (默认 strict)',
    )
    parser.add_argument(
        '--files', nargs='*', type=Path, default=None,
        help='指定子集 fixture (默认 = --dir 下所有 golden_dataflow_*.sv)',
    )
    parser.add_argument(
        '--quiet', action='store_true',
        help='只打印 fail 和最终统计',
    )
    args = parser.parse_args(argv)

    # 收 fixture 列表
    if args.files:
        fixes = sorted(args.files)
    else:
        if not args.dir.exists():
            print(f'ERROR: fixture dir 不存在: {args.dir}', file=sys.stderr)
            return 1
        fixes = sorted(args.dir.glob('golden_dataflow_*.sv'))
    if not fixes:
        print(f'ERROR: 没找到 fixture (检查 --dir 或 --files)', file=sys.stderr)
        return 1

    passed = 0
    failed = 0
    fails: list[tuple[str, str]] = []
    for fix in fixes:
        ok, msg = _run_case(fix, args.level)
        if ok:
            passed += 1
            if not args.quiet:
                print(f'  PASS {fix.stem.replace("golden_dataflow_", "case")} ({msg})')
        else:
            failed += 1
            fails.append((fix.stem, msg))
            print(f'  FAIL {fix.stem}: {msg}')

    total = passed + failed
    print()
    print(f'PASSED: {passed} / {total}')
    if failed:
        print('FAILED:')
        for name, msg in fails:
            print(f'  {name}: {msg[:80]}')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(_cli())