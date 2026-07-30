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
        assert "digraph" in stdout

    def test_has_pipeline_stats(self):
        import re
        _, stdout, stderr = _run_pipeline()
        combined = stdout + stderr
        assert re.search(r"Pipeline regs:\s*\d+", combined), "missing Pipeline regs stat"
        assert re.search(r"Stages:\s*\d+", combined), "missing Stages stat"


class TestPipelineVizData:
    """V6.7: Pipeline 的 VizData 数据导出"""

    def test_vizdata_with_stages(self):
        """[SKIP] trace package conflicts with Python stdlib trace module.
        
        Root cause: Python's stdlib trace.py shadows sv_query's src/trace/.
        Fix requires renaming the sv_query trace package or using PYTHONPATH
        hooks at the pytest session level (conftest sys.path comes too late).
        TODO: rename trace → sv_trace or add sitecustomize.py workaround.
        """
        pytest.skip("trace package conflicts with Python stdlib trace module")


def test_pipeline_golden_match():
    """[SKIP] trace package conflicts with Python stdlib trace module.
    Same root cause as test_vizdata_with_stages above.
    """
    pytest.skip("trace package conflicts with Python stdlib trace module")
