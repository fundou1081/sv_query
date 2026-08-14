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
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / 'src'))

from cli._viz_common import build_viz_tracer  # noqa: E402
from trace.core.graph.analyzer.signal_classifier import classify_graph  # noqa: E402
from trace.core.graph.viz import VizBuildOptions, build_viz_data  # noqa: E402
from trace.core.graph.viz.checker import check_viz_render  # noqa: E402
from trace.core.graph.viz.elk_bridge import _build_elk_for_viz, run_elk_layout  # noqa: E402
from trace.core.graph.viz.viz_engine import render_dataflow  # noqa: E402

from .extract_target import extract_target  # noqa: E402

DEFAULT_DIR = Path('sim/tests/fixtures/golden_mini')


def _run_case(fix: Path, level: str, dump_dir: Path | None = None) -> tuple[bool, str]:
    """跑单个 case, 返 (passed, short_message).

    [2026-08-13] 加 dump_dir 参数: 若提供, 落盘 4 份产物 (viz/elk/layout/svg)
    便于逐 case review (图 + 代码 对照).
    """
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

        # [2026-08-13] 落盘 elk 链路各阶段产物
        if dump_dir is not None:
            dump_dir.mkdir(parents=True, exist_ok=True)
            case_name = fix.stem.replace("golden_dataflow_", "case")
            # 1. VizData (build_viz_data 输出)
            viz_json = _viz_to_jsonable(viz)
            (dump_dir / f"{case_name}.viz.json").write_text(
                json.dumps(viz_json, indent=2, default=str)
            )

        # 2. ELK JSON (elk_bridge 输出)
        elk = _build_elk_for_viz(viz)
        if dump_dir is not None:
            (dump_dir / f"{case_name}.elk.json").write_text(
                json.dumps(elk, indent=2, default=str)
            )

        # 3. ELK layout (elk_layout.js 输出)
        layout = run_elk_layout(elk)
        if dump_dir is not None:
            (dump_dir / f"{case_name}.layout.json").write_text(
                json.dumps(layout, indent=2, default=str)
            )

        # 4. SVG 最终输出
        svg = render_dataflow(viz)
        if dump_dir is not None:
            (dump_dir / f"{case_name}.svg").write_text(svg)

        report = check_viz_render(viz, layout=layout, svg=svg, level=level)
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


def _viz_to_jsonable(viz) -> dict:
    """把 VizData 转成可 JSON 序列化的 dict (用于 dump)。"""
    def _node_to_dict(n):
        # [V16 Plan Phase 3.1 2026-08-14] dump 字段补全:
        # label, full_path, cluster_id, instance_path, module_type,
        # def_name, depth, is_port, is_function, class_ (修正 Python class 冲突),
        # class_confidence, risk_level, risk_score, cover_status,
        # stage_id, cycle, is_input, is_output, is_critical
        d = {"id": str(getattr(n, "id", ""))}
        for attr in ("name", "label", "full_path", "module", "module_type",
                     "kind", "class_", "class_confidence",
                     "width", "file", "line",
                     "def_name", "depth",
                     "port_side", "cluster_id", "instance_path",
                     "risk_level", "risk_score", "cover_status"):
            v = getattr(n, attr, None)
            if v is not None and v != "" and v != 0:
                d[attr] = str(v) if not isinstance(v, (int, float, bool, list, dict)) else v
        # bool 字段 (过滤默认值 False)
        for attr in ("is_port", "is_function", "is_input", "is_output", "is_critical"):
            v = getattr(n, attr, None)
            if v is not None and v is not False:
                d[attr] = bool(v)
        # stage_id/cycle 是 int? 类型, 默认 None (过滤)
        for attr in ("stage_id", "cycle"):
            v = getattr(n, attr, None)
            if v is not None:
                d[attr] = int(v)
        return d
    def _edge_to_dict(e):
        # [V16 Plan Phase 3.1 2026-08-14] dump 字段补全:
        # effective_condition, condition_chain, is_port_connection, port_name,
        # is_control_edge, edge_cycle_delta, source_signal, source_op,
        # source_bit_start, source_bit_end, confidence, reset_condition
        d = {}
        for attr in ("src", "dst", "kind", "expression", "bit_slice",
                     "assign_type", "clock_domain",
                     "effective_condition", "source_signal", "source_op",
                     "source_operand_side", "source_casts",
                     "confidence", "reset_condition", "port_name"):
            v = getattr(e, attr, None)
            if v is not None and v != "" and v != []:
                d[attr] = str(v) if not isinstance(v, (int, float, bool, list, dict)) else v
        # condition_chain (list[str], 过滤空 list)
        cc = getattr(e, "condition_chain", None)
        if cc:
            d["condition_chain"] = list(cc)
        # bool 字段
        for attr in ("is_port_connection", "is_control_edge", "source_is_decomposed"):
            v = getattr(e, attr, None)
            if v is not None and v is not False:
                d[attr] = bool(v)
        # int 字段
        for attr in ("source_bit_start", "source_bit_end", "edge_cycle_delta"):
            v = getattr(e, attr, None)
            if v is not None:
                d[attr] = int(v)
        return d
    return {
        "nodes": [_node_to_dict(n) for n in getattr(viz, "nodes", [])],
        "edges": [_edge_to_dict(e) for e in getattr(viz, "edges", [])],
        "expr_trees": getattr(viz, "expr_trees", []),
        "const_map": getattr(viz, "const_map", {}),
    }


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
    parser.add_argument(
        '--dump', type=Path, default=None,
        help='落盘 elk 链路各阶段产物 (viz/elk/layout/svg) 到指定目录 (供逐 case review)',
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
        ok, msg = _run_case(fix, args.level, dump_dir=args.dump)
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