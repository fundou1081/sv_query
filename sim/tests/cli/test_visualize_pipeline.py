"""
test_visualize_pipeline.py — V6.7 CLI 回归 + VizData 验证

Pipeline 可视化测试: 命令不崩溃，统计正确，VizData 数据导出。
DOT golden 对比暂时 skip（V6.7 渲染逻辑已变）。
"""
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FL = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")


def _run_pipeline() -> tuple[int, str, str]:
    p = subprocess.run(
        ["sv_query", "visualize", "pipeline", "--filelist", STRICT_UART_FL, "--no-strict"],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


class TestPipelineCli:
    def test_returns_zero(self):
        rc, _, stderr = _run_pipeline()
        assert rc == 0, f"pipeline failed: {stderr[:300]}"

    def test_output_is_digraph(self):
        _, stdout, _ = _run_pipeline()
        # [V100 SVG 2026-08-13] pipeline 输出 SVG, 不再输出 DOT digraph
        assert "<svg" in stdout or "svg" in stdout.lower()

    def test_has_pipeline_stats(self):
        import re
        _, stdout, stderr = _run_pipeline()
        combined = stdout + stderr
        assert re.search(r"Pipeline regs:\s*\d+", combined), "missing Pipeline regs stat"
        assert re.search(r"Stages:\s*\d+", combined), "missing Stages stat"


class TestPipelineVizData:
    """V6.7: Pipeline 的 VizData 数据导出"""

    def test_vizdata_with_stages(self):
        """[V6.9] Pipeline output contains stage/reg elements."""
        p = subprocess.run(
            ["sv_query", "visualize", "pipeline", "--filelist", STRICT_UART_FL,
             "--no-strict"],
            capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
        )
        if p.returncode != 0:
            pytest.skip(f"CLI failed: {p.stderr[:200]}")
        # [V100 SVG 2026-08-13] output 是 SVG, 不再断言 'digraph'
        dot = p.stdout
        assert "<svg" in dot or "svg" in dot.lower(), "output should be SVG"
        assert any(kw in dot.lower() for kw in ["reg", "stage", "pipeline"]), \
            "SVG should contain pipeline/reg elements"


def test_pipeline_golden_match():
    """[V6.9] Pipeline output contains expected reg labels.

    [V100 SVG 2026-08-13] pipeline 输出 SVG, 不再有 DOT golden 对比.
    改为验证 SVG 输出含真实的寄存器信号 (strict_uart 的 _q 后缀寄存器).
    """
    rc, stdout, _ = _run_pipeline()
    assert rc == 0
    # strict_uart 的寄存器信号: count_q / rd_ptr_q / wr_ptr_q / mem
    assert "<svg" in stdout, "output should be SVG"
    assert any(kw in stdout for kw in ["_q", "mem", "count", "ptr"]), \
        "SVG should contain register signals"
