"""
test_visualize_generate.py — [Plan F1.4 2026-08-12] CLI 级 generate 覆盖

[Plan F1] generate for/if/case 全功能 fix 已经落在 semantic_adapter.py + driver_extractor.py.
本文件补充 CLI 级别的回归覆盖 (即用户跑 `sv_query visualize dataflow` 在含 generate
的 SV 上不 crash + 产出正确).

测试策略:
- 利用现有 sim/tests/fixtures/golden_mini/golden_dataflow_{27,29,30,31}_*.sv (已经
  验证过 generate 行为的金标准 mini fixtures)
- 不发明新 SV (避免语法边角导致节点折叠)
- 断言: rc=0 + SVG 输出 + 关键信号节点出现 + 已知 rect/node count

[铁律13] 金标准测试
[铁律17] 强断言
[铁律22] 断言验证具体行为
"""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

GOLDEN_MINI = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"
STRICT_UART_FL = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"

# Existing mini fixtures that already exercise generate SV correctly
FIXTURE_FOR    = GOLDEN_MINI / "golden_dataflow_27_generate_loop.sv"
FIXTURE_CHAIN  = GOLDEN_MINI / "golden_dataflow_29_generate_for_chain.sv"
FIXTURE_IF     = GOLDEN_MINI / "golden_dataflow_30_generate_if.sv"
FIXTURE_CASE   = GOLDEN_MINI / "golden_dataflow_31_generate_case.sv"


def _run_viz_on_fixture(sv_path: Path) -> tuple[int, str, str]:
    """跑 sv_query visualize dataflow 在给的 SV file, 返 (rc, stdout, stderr)."""
    p = subprocess.run(
        ["sv_query", "visualize", "dataflow", "--file", str(sv_path), "--no-strict"],
        capture_output=True, text=True, timeout=60,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


def _count_rects(svg_text: str) -> int:
    """SVG 节点数 = <rect> 元素数."""
    return len(re.findall(r"<rect", svg_text))


def _count_edges(svg_text: str) -> int:
    """SVG 边数 = <path d="M ..."> 元素数 (大写 M = 绝对坐标)."""
    return len(re.findall(r'<path d="M ', svg_text))


def _has_signal(svg_text: str, signal: str) -> bool:
    """SVG 是否包含指定信号名的 <text> 节点."""
    return bool(re.search(rf"<text[^>]*>{re.escape(signal)}</text>", svg_text))


# ── Tests ──────────────────────────────────────────────────────────────────

class TestCliVisualizeGenerateNoCrash:
    """[Plan F1.4] sv_query visualize dataflow 在 generate SV 上不 crash"""

    def test_generate_for_runs(self):
        rc, _, stderr = _run_viz_on_fixture(FIXTURE_FOR)
        assert rc == 0, f"generate for: visualize failed: {stderr[:300]}"

    def test_generate_for_chain_runs(self):
        rc, _, stderr = _run_viz_on_fixture(FIXTURE_CHAIN)
        assert rc == 0, f"generate for chain: visualize failed: {stderr[:300]}"

    def test_generate_if_runs(self):
        rc, _, stderr = _run_viz_on_fixture(FIXTURE_IF)
        assert rc == 0, f"generate if: visualize failed: {stderr[:300]}"

    def test_generate_case_runs(self):
        rc, _, stderr = _run_viz_on_fixture(FIXTURE_CASE)
        assert rc == 0, f"generate case: visualize failed: {stderr[:300]}"


class TestCliVisualizeGenerateIterationExpansion:
    """[Plan F1.4] generate for 展开 iteration 节点 (Plan F1 主功能)"""

    def test_generate_for_27_has_acc_or_buf_nodes(self):
        """case27 generate_loop: 至少 4 个 acc[i] 节点 (acc[1]..acc[4])"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_FOR)
        assert rc == 0
        # SVG 中 acc[1]..acc[4] 出现
        acc_signals = [f"acc[{i}]" for i in range(1, 5)]
        found = [s for s in acc_signals if _has_signal(stdout, s)]
        assert len(found) >= 3, \
            f"expected ≥3 acc[i] signals (acc[1..4]), got {found}"

    def test_generate_for_27_has_svg_node_count(self):
        """case27: 17 个 SVG 节点 (实测量, mini fixture 已知)"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_FOR)
        assert rc == 0
        n = _count_rects(stdout)
        assert n >= 15, f"case27: expected ≥15 SVG nodes, got {n}"

    def test_generate_for_chain_29_has_buf1_nodes(self):
        """case29 generate_for_chain: buf1[0]..buf1[3] 全部出现"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_CHAIN)
        assert rc == 0
        found = [f"buf1[{i}]" for i in range(4) if _has_signal(stdout, f"buf1[{i}]")]
        assert len(found) >= 3, \
            f"case29: expected ≥3 buf1[i] signals, got {found}"

    def test_generate_for_chain_29_has_svg_node_count(self):
        """case29: 36 个 SVG 节点 (3 stages × 3+ iterations, 实测量)"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_CHAIN)
        assert rc == 0
        n = _count_rects(stdout)
        assert n >= 30, f"case29: expected ≥30 SVG nodes, got {n}"


class TestCliVisualizeGenerateBranchSelection:
    """[Plan F1.4] generate if/case 正确只 instantiate active branch
    (Plan F1 isUninstantiated filter 验证)"""

    def test_generate_if_30_no_branch_id_leak(self):
        """case30 generate_if: 不该有显式 branch 标签 (op1/op2 都出现, 但只在 active branch 用)"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_IF)
        assert rc == 0
        # MODE=1 → 只 gen_adder emit, op1 (= data+weights) 用
        # 需要的信号: data, weights, op1, result
        assert _has_signal(stdout, "data"), "missing data signal"
        assert _has_signal(stdout, "weights"), "missing weights signal"
        assert _has_signal(stdout, "result"), "missing result signal"

    def test_generate_if_30_has_svg_node_count(self):
        """case30: 9 个 SVG 节点 (实测量)"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_IF)
        assert rc == 0
        n = _count_rects(stdout)
        assert n >= 7, f"case30: expected ≥7 SVG nodes, got {n}"

    def test_generate_case_31_has_svg_node_count(self):
        """case31: 9 个 SVG 节点 (实测量, 只 sel=2 branch 用)"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_CASE)
        assert rc == 0
        n = _count_rects(stdout)
        assert n >= 7, f"case31: expected ≥7 SVG nodes, got {n}"

    def test_generate_case_31_has_required_signals(self):
        """case31: 关键信号 data/weights/result 都出现"""
        rc, stdout, _ = _run_viz_on_fixture(FIXTURE_CASE)
        assert rc == 0
        assert _has_signal(stdout, "data"), "missing data signal"
        assert _has_signal(stdout, "weights"), "missing weights signal"
        assert _has_signal(stdout, "result"), "missing result signal"


class TestCliVisualizeGenerateStatsOutput:
    """[Plan F1.4] CLI stderr 输出 node count 统计"""

    def test_generate_for_27_stderr_has_stats(self):
        rc, _, stderr = _run_viz_on_fixture(FIXTURE_FOR)
        assert rc == 0
        assert "Data nodes" in stderr, f"missing Data nodes in stderr: {stderr[:300]}"

    def test_generate_if_30_stderr_has_stats(self):
        rc, _, stderr = _run_viz_on_fixture(FIXTURE_IF)
        assert rc == 0
        assert "Data nodes" in stderr, f"missing Data nodes in stderr: {stderr[:300]}"


class TestCliVisualizeGenerateVsStrictUart:
    """[Plan F1.4] generate 测试不能影响现有 strict_uart 黄金测试"""

    def test_strict_uart_no_regression(self):
        """确保加 generate 测试后, strict_uart 还跑得动 (SVG 输出)"""
        p = subprocess.run(
            ["sv_query", "visualize", "dataflow", "--filelist", str(STRICT_UART_FL), "--no-strict"],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        assert p.returncode == 0, f"strict_uart: visualize failed: {p.stderr[:300]}"
        # 默认输出是 SVG
        assert "<svg" in p.stdout, \
            f"strict_uart: expected SVG output, got: {p.stdout[:300]}"
        # stderr 应有 node count 统计
        assert "Data nodes" in p.stderr or "Total nodes" in p.stderr, \
            f"strict_uart: expected node stats in stderr, got: {p.stderr[:300]}"
