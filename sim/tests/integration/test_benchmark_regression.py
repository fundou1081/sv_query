"""
test_benchmark_regression.py
==============================
[PR6 2026-06-15] benchmark regression check 工具测试.

PR6 目标: check_regression.py 对比 current vs baseline JSON, 输出 regression 报告.
验证:
- 工具能跑通
- 同样的数据自己比自己 PASS
- 模拟 regression (50% nodes drop) FAIL
- 模拟 flakiness (deterministic_ratio 降到 0.5) FAIL
- [iter_226] 新增: L1/L4 跌 35% (> 30% 新阈值) 触发 ⚠️ 警告 (退出码仍 0 — 本工具历史语义)
- 模拟 acceptable drop (10% nodes) PASS
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.opensource

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHECK = PROJECT_ROOT / "tools" / "benchmark" / "check_regression.py"
BASELINE_DIR = PROJECT_ROOT / "tools" / "benchmark" / "baselines"
PICO_BASELINE = BASELINE_DIR / "picorv32.json"
# [iter_187] picorv32 自包含 → IM=0, "IM 下跌" 场景在它上退化 (0 的 50% 还是 0)。
# 需要非零 IM 的 baseline 来做比例派生 → 用 verilog-axi (IM=6) / pr5_wrap (IM=516)。
VERILOG_AXI_BASELINE = BASELINE_DIR / "verilog_axi.json"


def _make_variant(baseline_path: Path, **overrides) -> Path:
    """Create a variant of baseline with specific field overrides."""
    with open(baseline_path) as f:
        data = json.load(f)
    for path, value in overrides.items():
        keys = path.split(".")
        cur = data
        for k in keys[:-1]:
            cur = cur[k]
        cur[keys[-1]] = value
    out = Path("/tmp/bench_variant.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    return out


def _make_scaled_variant(baseline_path: Path, **factors: float) -> Path:
    """[iter_187] 按 baseline 的**比例**派生 variant (不再硬编码旧数值)。

    过去这里写死 "baseline 708 nodes → 354" 之类, baseline 一重生成数值就全错
    (实测: baseline 更新到 438 后, 写死的 354 变成 -19% 而非 -50% → 测试假失败)。
    比例派生让测试只依赖"阈值语义", 不依赖当时的具体数值。
    """
    with open(baseline_path) as f:
        data = json.load(f)
    for path, factor in factors.items():
        keys = path.split(".")
        cur = data
        for k in keys[:-1]:
            cur = cur[k]
        orig = cur[keys[-1]]
        cur[keys[-1]] = max(0, int(round(orig * factor)))
    out = Path("/tmp/bench_variant_scaled.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    return out


def _run_check(current: Path, baseline: Path = None, baseline_dir: Path = None) -> subprocess.CompletedProcess:
    args = [sys.executable, str(CHECK), "--current", str(current)]
    if baseline:
        args.extend(["--baseline", str(baseline)])
    if baseline_dir:
        args.extend(["--baseline-dir", str(baseline_dir)])
    return subprocess.run(args, capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT)


class TestCheckRegressionBasics:
    """check_regression.py 基础功能."""

    def test_self_comparison_passes(self):
        """baseline 跟自己比应该 PASS."""
        result = _run_check(PICO_BASELINE, baseline=PICO_BASELINE)
        assert result.returncode == 0, f"self-comparison should pass: {result.stdout}\n{result.stderr}"
        assert "✅ All checks PASSED" in result.stdout

    def test_baseline_dir_lookup(self):
        """--baseline-dir 模式下自动找 <target>.json."""
        result = _run_check(PICO_BASELINE, baseline_dir=BASELINE_DIR)
        assert result.returncode == 0, f"baseline-dir lookup failed: {result.stderr}"
        assert "✅" in result.stdout

    def test_missing_current_fails(self, tmp_path):
        """不存在的 current 文件应该 fail."""
        result = subprocess.run(
            [sys.executable, str(CHECK),
             "--current", str(tmp_path / "nonexistent.json"),
             "--baseline", str(PICO_BASELINE)],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT,
        )
        assert result.returncode != 0, "should fail for missing current"

    def test_missing_baseline_fails(self):
        """没指定 baseline 应该 fail."""
        result = subprocess.run(
            [sys.executable, str(CHECK), "--current", str(PICO_BASELINE)],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT,
        )
        assert result.returncode != 0, "should fail without baseline"


class TestRegressionDetection:
    """Regression 检测 (FAIL 场景)."""

    def test_node_drop_50_pct_fails(self):
        """L2 nodes 跌 50% 应该 FAIL (阈值 30%)。"""
        variant = _make_scaled_variant(PICO_BASELINE, **{"L2_graph_topology.nodes": 0.5})
        result = _run_check(variant, baseline=PICO_BASELINE)
        assert result.returncode != 0, "should fail on 50% nodes drop"
        assert "❌ L2_nodes" in result.stdout
        assert "Some checks FAILED" in result.stdout

    def test_im_drop_50_pct_fails(self):
        """L2 IM 跌 50% 应该 FAIL (阈值 30%)。

        [iter_187] 用 verilog-axi baseline (IM=6→3): picorv32 的 IM=0, "跌 50%"
        在它上面退化 (0→0), 测不出检测能力。
        """
        variant = _make_scaled_variant(
            VERILOG_AXI_BASELINE, **{"L2_graph_topology.instantiated_modules": 0.5}
        )
        result = _run_check(variant, baseline=VERILOG_AXI_BASELINE)
        assert result.returncode != 0, "should fail on IM drop 50%"
        assert "❌ L2_im" in result.stdout

    def test_flakiness_drop_below_threshold_fails(self):
        """deterministic_ratio 降到 0.5 应该 FAIL (iter_226 阈值 = 1.0)."""
        variant = _make_variant(PICO_BASELINE, **{"flakiness.deterministic_ratio_im": 0.5})
        result = _run_check(variant, baseline=PICO_BASELINE)
        assert result.returncode != 0, "should fail on flakiness drop"
        assert "❌ flakiness" in result.stdout


class TestAcceptableChange:
    """Acceptable change (PASS 场景)."""

    def test_10_pct_node_drop_passes(self):
        """L2 nodes 跌 10% (< 30%) 应该 PASS。"""
        variant = _make_scaled_variant(PICO_BASELINE, **{"L2_graph_topology.nodes": 0.9})
        result = _run_check(variant, baseline=PICO_BASELINE)
        assert result.returncode == 0, (
            f"10% drop should pass: {result.stdout}\n{result.stderr}"
        )
        assert "✅ L2_nodes" in result.stdout

    def test_25_pct_edge_drop_passes(self):
        """L2 edges 跌 25% (< 30%) 应该 PASS。"""
        variant = _make_scaled_variant(PICO_BASELINE, **{"L2_graph_topology.edges": 0.75})
        result = _run_check(variant, baseline=PICO_BASELINE)
        assert result.returncode == 0, (
            f"25% edge drop should pass: {result.stdout}\n{result.stderr}"
        )

    def test_l1_35_pct_drop_warns_with_tightened_threshold(self):
        """[iter_226] L1 跌 35% (> 30% 新阈值, 旧阈值 50% 下不会报) → ⚠️ 警告, 退出码 0.

        verilog_axi 的 L1 instance_count=6 (>0), 用它派生 65% 变体。
        ⚠️ 本工具的 L1/L4 越界**只警告不改退出码** (历史语义: 当年受 flakiness
        影响, 误报会打断 CI) — 这里同时锁定"新阈值生效"和"仍是警告级"。
        """
        variant = _make_scaled_variant(
            VERILOG_AXI_BASELINE, **{"L1_module_extraction.instance_count": 0.65})
        result = _run_check(variant, baseline=VERILOG_AXI_BASELINE)
        assert "⚠️  L1_instances: dropped" in result.stdout, result.stdout
        assert "max_drop=30.0%" in result.stdout, result.stdout
        assert result.returncode == 0, "L1 越界历史上只警告, 不应改退出码"

    def test_l4_35_pct_drop_warns_with_tightened_threshold(self):
        """[iter_226] L4 跌 35% (> 30%) → ⚠️ 警告 (同上, verilog_axi L4=146)."""
        variant = _make_scaled_variant(
            VERILOG_AXI_BASELINE, **{"L4_cross_instance_edges.edge_count": 0.65})
        result = _run_check(variant, baseline=VERILOG_AXI_BASELINE)
        assert "⚠️  L4_edges: dropped" in result.stdout, result.stdout
        assert "max_drop=30.0%" in result.stdout, result.stdout
        assert result.returncode == 0

    def test_l1_self_compare_passes(self):
        """picorv32 L1=0 → 该维度跳过, 自比照常 PASS (原 test_l1_40_pct_drop_warns_only 的本意)."""
        result = _run_check(PICO_BASELINE, baseline=PICO_BASELINE)
        assert result.returncode == 0


class TestCheckRegressionCLI:
    """CLI 行为."""

    def test_check_exits_with_correct_code_on_pass(self):
        """PASS 退出码 0."""
        result = _run_check(PICO_BASELINE, baseline=PICO_BASELINE)
        assert result.returncode == 0

    def test_check_exits_with_code_1_on_fail(self):
        """FAIL 退出码 1."""
        variant = _make_variant(PICO_BASELINE, **{"L2_graph_topology.nodes": 100})
        result = _run_check(variant, baseline=PICO_BASELINE)
        assert result.returncode == 1
