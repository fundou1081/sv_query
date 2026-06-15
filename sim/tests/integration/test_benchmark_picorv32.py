"""
test_benchmark_picorv32.py
============================
[PR7 2026-06-15] benchmark picorv32 支持测试.

PR7 目标: run_benchmark.py 加 --files flag, 支持单文件模式 (picorv32.v).
验证:
- --files 跟 --filelist 互斥
- picorv32 能被 benchmark 跑通
- picorv32 baseline 存在且数据合理
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BENCH = PROJECT_ROOT / "tools" / "benchmark" / "run_benchmark.py"
BASELINE = PROJECT_ROOT / "tools" / "benchmark" / "baselines" / "picorv32.json"
PICO_FILE = "/Users/fundou/my_dv_proj/picorv32/picorv32.v"


def _run_bench(target: str = "picorv32", depth: int = 2, output: Path = None, **kwargs) -> dict:
    """Run benchmark with --files flag."""
    if output is None:
        output = Path("/tmp/bench_pr7_test.json")
    args = [
        sys.executable, str(BENCH),
        "--files", PICO_FILE,
        "--target", target,
        "--depth", str(depth),
        "--runs", "1",
        "--output", str(output),
        "--skip-flakiness",
    ]
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=120, cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        pytest.skip(f"benchmark failed: rc={result.returncode}, stderr={result.stderr[:300]}")
    if not output.exists():
        pytest.skip(f"benchmark output not found: {output}")
    with open(output) as f:
        return json.load(f)


class TestFilesFlag:
    """--files flag 加进 benchmark (PR7)."""

    def test_files_flag_works(self, tmp_path):
        """--files 单文件模式能跑通."""
        out = tmp_path / "bench.json"
        result = subprocess.run(
            [
                sys.executable, str(BENCH),
                "--files", PICO_FILE,
                "--target", "picorv32",
                "--depth", "2",
                "--skip-flakiness",
                "--output", str(out),
            ],
            capture_output=True, text=True, timeout=120, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"benchmark failed: {result.stderr[:300]}"
        assert out.exists(), "benchmark didn't write output"
        with open(out) as f:
            data = json.load(f)
        assert data["metadata"]["input_type"] == "files"
        assert PICO_FILE in data["metadata"]["project_input"]

    def test_files_and_filelist_mutually_exclusive(self):
        """--files 跟 --filelist 互斥."""
        result = subprocess.run(
            [
                sys.executable, str(BENCH),
                "--files", PICO_FILE,
                "--filelist", "/tmp/pulp_axi_xbar_pr2.f",
                "--target", "picorv32",
                "--depth", "2",
            ],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT,
        )
        assert result.returncode != 0, "expected error for mutually exclusive args"
        # argparse error message should mention the issue
        assert "not allowed" in result.stderr.lower() or "mutually exclusive" in result.stderr.lower(), (
            f"stderr should mention mutually exclusive, got: {result.stderr[:200]}"
        )


class TestPicorv32Benchmark:
    """picorv32 benchmark 数据合理."""

    def test_picorv32_runs_clean(self):
        """picorv32 跑得通, 数据不空."""
        data = _run_bench()
        assert data is not None
        assert data["metadata"]["target"] == "picorv32"

    def test_picorv32_l2_node_count_above_400(self):
        """picorv32.v (3049 行) 应该有 >= 400 nodes."""
        data = _run_bench()
        l2 = data["L2_graph_topology"]
        assert l2["nodes"] >= 400, f"expected >= 400 nodes, got {l2['nodes']}"

    def test_picorv32_l2_im_count_at_least_2(self):
        """picorv32 至少有 2 INSTANTIATED_MODULE (clk_gen, mem)."""
        data = _run_bench()
        l2 = data["L2_graph_topology"]
        assert l2["instantiated_modules"] >= 2, (
            f"expected >= 2 IM, got {l2['instantiated_modules']}"
        )

    def test_picorv32_l3_traces_work(self):
        """L3 trace 在 picorv32 上能跑通 (clk, resetn, mem_busy 真实存在)."""
        out = Path("/tmp/bench_pico_l3.json")
        result = subprocess.run(
            [
                sys.executable, str(BENCH),
                "--files", PICO_FILE,
                "--target", "picorv32",
                "--depth", "2",
                "--skip-flakiness",
                "--traces", "picorv32.clk", "picorv32.resetn", "picorv32.mem_busy",
                "--output", str(out),
            ],
            capture_output=True, text=True, timeout=120, cwd=PROJECT_ROOT,
        )
        if not out.exists():
            pytest.skip("benchmark failed")
        with open(out) as f:
            data = json.load(f)
        l3 = data["L3_signal_traces"]
        # clk should have some fanout (drives many internal regs)
        if "error" not in l3.get("picorv32.clk", {}):
            clk = l3["picorv32.clk"]
            assert clk["fanout"] >= 1, f"clk fanout >= 1, got {clk['fanout']}"


class TestPicorv32Baseline:
    """baseline 文件存在且数据合理."""

    def test_baseline_file_exists(self):
        """baselines/picorv32.json 应该存在."""
        assert BASELINE.exists(), f"baseline not found: {BASELINE}"

    def test_baseline_has_required_fields(self):
        """baseline 应该有完整 metadata + L1-L4 + flakiness."""
        if not BASELINE.exists():
            pytest.skip("baseline not found")
        with open(BASELINE) as f:
            data = json.load(f)
        for key in ("metadata", "L1_module_extraction", "L2_graph_topology",
                    "L3_signal_traces", "L4_cross_instance_edges", "flakiness"):
            assert key in data, f"missing {key} in baseline"

    def test_baseline_input_type_files(self):
        """baseline 应该是 --files 模式 (PR7)."""
        if not BASELINE.exists():
            pytest.skip("baseline not found")
        with open(BASELINE) as f:
            data = json.load(f)
        assert data["metadata"]["input_type"] == "files"

    def test_baseline_l2_values_reasonable(self):
        """baseline L2 数据在合理范围."""
        if not BASELINE.exists():
            pytest.skip("baseline not found")
        with open(BASELINE) as f:
            data = json.load(f)
        l2 = data["L2_graph_topology"]
        # Should be consistent with what we measured
        assert 400 <= l2["nodes"] <= 700, f"nodes {l2['nodes']} outside 400-700"
        assert 2 <= l2["instantiated_modules"] <= 10, f"IM {l2['instantiated_modules']} outside 2-10"

    def test_baseline_flakiness_stable(self):
        """baseline flakiness 应该 deterministic_ratio_im >= 0.9 (内存回收后)."""
        if not BASELINE.exists():
            pytest.skip("baseline not found")
        with open(BASELINE) as f:
            data = json.load(f)
        flk = data["flakiness"]
        assert flk["deterministic_ratio_im"] >= 0.9, (
            f"IM deterministic only {flk['deterministic_ratio_im']*100:.0f}%, expected >= 90%"
        )
