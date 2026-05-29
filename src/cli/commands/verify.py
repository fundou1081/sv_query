#==============================================================================
# verify.py - 验证缺口检测命令
#==============================================================================
"""
验证缺口检测：找出高风险但无 SVA/Coverage 的信号，形成完整的验证优先级报告。

Usage:
  python run_cli.py verify gap -f top.sv
  python run_cli.py verify gap -f top.sv --json
  python run_cli.py verify gap -f top.sv --top 20
"""
import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
_project_root = _src_dir.parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import typer
import warnings
warnings.filterwarnings("ignore")

from trace.unified_tracer import UnifiedTracer
from trace.core.sva_extractor import SVAExtractor
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.graph.models import NodeKind

verify_app = typer.Typer(help="Verification gap detection: find high-risk signals without SVA/Coverage")


@verify_app.command(name="gap")
def gap(
    file: str = typer.Option(..., "--file", "-f", help="SystemVerilog source file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    top_n: int = typer.Option(20, "--top", "-n", help="Show top N high-risk signals"),
    min_risk: float = typer.Option(20.0, "--min-risk", "-r", help="Minimum risk score threshold"),
) -> None:
    """
    验证缺口检测：
    1. 基于信号图计算双维度风险
    2. 合并 SVA 覆盖和 Coverage 覆盖
    3. 输出高风险但无验证的信号清单
    """
    with open(file) as f:
        source = f.read()

    tracer = UnifiedTracer(sources={file: source})
    graph = tracer.build_graph()
    sva = SVAExtractor({file: source}).extract()
    cov_list = CovergroupExtractor({file: source}).extract()

    # ===== 1. 收集覆盖信息 =====
    # SVA 覆盖的信号
    sva_signals = set()
    for prop in sva.properties.values():
        sva_signals.update(prop.signals)
    for seq in sva.sequences.values():
        sva_signals.update(seq.signals)
    for a in sva.assertions:
        sva_signals.update(a.signals)

    # Coverage 覆盖的信号（coverpoint 关联的信号）
    cov_signals = set()
    cov_detail = {}  # signal -> list of bins
    for cg in cov_list:
        for cp in cg.coverpoints:
            sig = cp.signal
            cov_signals.add(sig)
            if sig not in cov_detail:
                cov_detail[sig] = []
            cov_detail[sig].extend([b.name for b in cp.bins])

    # 时钟信号
    clock_signals = set()
    for prop in sva.properties.values():
        if prop.clock:
            clock_signals.add(prop.clock)

    # ===== 2. 分类所有数据信号 =====
    data_signals = {}  # node_id -> info
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        name = node_id.split('.')[-1]

        # 排除时钟/复位
        if name in ('clk', 'clock', 'clk_i', 'rst_n', 'rst', 'reset', 'resetn'):
            continue
        if node.is_clock or node.is_reset:
            continue

        if node.kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.REG, NodeKind.SIGNAL):
            data_signals[node_id] = {
                'name': name,
                'kind': str(node.kind),
                'node': node,
            }

    # ===== 3. 计算风险 + 覆盖状态 =====
    def compute_risk(node_id, info):
        node = info['node']
        fan_in = graph.in_degree(node_id)
        fan_out = graph.out_degree(node_id)
        width_bits = max(1, node.width[1] - node.width[0] + 1) if node.width else 1
        is_reg = node.kind == NodeKind.REG
        name = info['name']

        func = fan_in * 3 + fan_out * 2 + width_bits * 0.3
        func += 15 if fan_in >= 3 else 0
        func += 10 if fan_out >= 3 else 0

        timing = 15 if is_reg else 0
        timing += fan_in * 2

        return func, timing

    results = []
    for node_id, info in data_signals.items():
        name = info['name']
        func_s, timing_s = compute_risk(node_id, info)

        has_sva = name in sva_signals
        has_cov = name in cov_signals

        # 覆盖状态
        if has_sva and has_cov:
            cover_status = 'BOTH'
        elif has_sva:
            cover_status = 'SVA'
        elif has_cov:
            cover_status = 'COV'
        else:
            cover_status = 'NONE'

        results.append({
            'node_id': node_id,
            'name': name,
            'kind': info['kind'],
            'fan_in': graph.in_degree(node_id),
            'fan_out': graph.out_degree(node_id),
            'func_score': round(func_s, 1),
            'timing_score': round(timing_s, 1),
            'total_risk': round(func_s + timing_s, 1),
            'has_sva': has_sva,
            'has_cov': has_cov,
            'cover_status': cover_status,
            'cov_bins': cov_detail.get(name, []),
        })

    # 按 total_risk 排序
    results.sort(key=lambda x: x['total_risk'], reverse=True)

    # 过滤高风险但无覆盖的
    gap_signals = [r for r in results if r['total_risk'] >= min_risk and r['cover_status'] == 'NONE']
    all_signals = results[:top_n]

    # ===== 4. 输出 =====
    if json_output:
        import json
        print(json.dumps({
            'ok': True, 'command': 'verify gap',
            'file': file,
            'summary': {
                'total_data_signals': len(results),
                'sva_covered': len([r for r in results if r['has_sva']]),
                'cov_covered': len([r for r in results if r['has_cov']]),
                'both_covered': len([r for r in results if r['has_sva'] and r['has_cov']]),
                'uncovered': len([r for r in results if r['cover_status'] == 'NONE']),
                'high_risk_uncovered': len(gap_signals),
            },
            'top_signals': all_signals,
            'gap_signals': gap_signals,
        }, indent=2, ensure_ascii=False))
        return

    # 文本输出
    print(f"{'='*80}")
    print(f"验证缺口分析: {file}")
    print(f"{'='*80}")

    # 摘要
    total = len(results)
    sva_cnt = len([r for r in results if r['has_sva']])
    cov_cnt = len([r for r in results if r['has_cov']])
    both_cnt = len([r for r in results if r['has_sva'] and r['has_cov']])
    none_cnt = len([r for r in results if r['cover_status'] == 'NONE'])
    gap_cnt = len(gap_signals)

    print(f"\n  📊 信号统计:")
    print(f"     总数据信号: {total}")
    print(f"     SVA 覆盖: {sva_cnt} ({sva_cnt/total*100:.1f}%)")
    print(f"     Coverage 覆盖: {cov_cnt} ({cov_cnt/total*100:.1f}%)")
    print(f"     两者都有: {both_cnt}")
    print(f"     完全没有: {none_cnt} ({none_cnt/total*100:.1f}%)")

    print(f"\n  🚨 高风险缺口 (风险≥{min_risk} 且无覆盖): {gap_cnt}")

    # 状态图例
    print(f"\n  图例: ✓=SVA覆盖  🟡=Coverage覆盖  ✓🟡=两者都有  ✗=无覆盖")

    # 高风险缺口详情
    if gap_signals:
        print(f"\n  【需要优先补充验证的信号】")
        print(f"  {'排名':4s} {'信号':25s} {'类型':6s} {'功能分':7s} {'时序分':7s} {'覆盖'}")
        print(f"  {'─'*4} {'─'*25} {'─'*6} {'─'*7} {'─'*7} {'─'*6}")
        for i, r in enumerate(gap_signals[:10], 1):
            kind_short = {'PORT_IN': 'IN', 'PORT_OUT': 'OUT', 'REG': 'REG', 'SIGNAL': 'SIG'}.get(r['kind'], '?')
            status_icon = '✓' if r['has_sva'] else ('🟡' if r['has_cov'] else '✗')
            level = '🔴' if r['total_risk'] >= 40 else ('🟠' if r['total_risk'] >= 25 else '🟡')
            print(f"  {i:4d} {r['name']:25s} {kind_short:6s} {level}{r['func_score']:5.1f} {r['timing_score']:5.1f} {status_icon}")
        if len(gap_signals) > 10:
            print(f"  ... 还有 {len(gap_signals) - 10} 个高风险信号")

    # 完整 top N 列表
    print(f"\n  【Top {min(top_n, len(all_signals))} 高风险信号详情】")
    print(f"  {'排名':4s} {'信号':25s} {'类型':6s} {'fan_in':6s} {'fan_out':7s} {'功能分':6s} {'时序分':6s} {'覆盖'}")
    print(f"  {'─'*4} {'─'*25} {'─'*6} {'─'*6} {'─'*7} {'─'*6} {'─'*6} {'─'*6}")

    for i, r in enumerate(all_signals, 1):
        kind_short = {'PORT_IN': 'IN', 'PORT_OUT': 'OUT', 'REG': 'REG', 'SIGNAL': 'SIG'}.get(r['kind'], '?')
        if r['cover_status'] == 'BOTH':
            status_icon = '✓🟡'
        elif r['cover_status'] == 'SVA':
            status_icon = '✓'
        elif r['cover_status'] == 'COV':
            status_icon = '🟡'
        else:
            status_icon = '✗'

        level_f = '🔴' if r['func_score'] >= 40 else ('🟠' if r['func_score'] >= 25 else ('🟡' if r['func_score'] >= 15 else '🟢'))
        level_t = '🔴' if r['timing_score'] >= 40 else ('🟠' if r['timing_score'] >= 25 else ('🟡' if r['timing_score'] >= 15 else '🟢'))
        print(f"  {i:4d} {r['name']:25s} {kind_short:6s} {r['fan_in']:6d} {r['fan_out']:7d} {level_f}{r['func_score']:5.1f} {level_t}{r['timing_score']:5.1f} {status_icon}")

    # Coverage 详情
    if cov_detail:
        print(f"\n  【Coverage bins 详情】")
        for sig, bins in sorted(cov_detail.items()):
            print(f"    {sig}: {', '.join(bins)}")


if __name__ == "__main__":
    typer.run(gap)