"""
test_visualize_pipeline.py - Golden test for `sv_query visualize pipeline`
=====================================================================
[ADD 2026-07-03] Phase 4 (方豆要求: 3 命令加测试 + golden).

**测试目的 (核心)**:
  验证 `visualize pipeline` 命令生成的 DOT 图结构稳定.
  - Stage 数量 (自动检测 pipeline 结构)
  - State regs 数量
  - Pipeline regs 数量
  - 节点 label (signal + 类型)
  - DOT 结构 (rankdir=LR 时间流)

**Fixture**: `sim/tests/fixtures/strict_uart/filelist.f` (3 SV, 自洽)
  - 不依赖外部项目源码
  - 跨平台稳定

**Golden 文件**: `sim/tests/golden/visualize_pipeline/strict_uart.dot`
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "visualize_pipeline"
GOLDEN_FILE = GOLDEN_DIR / "strict_uart.dot"


def _run_visualize_pipeline(dot_path: Path) -> tuple[int, str, str]:
    """Run `sv_query visualize pipeline` with filelist, return (rc, stdout, stderr)."""
    p = subprocess.run(
        [
            "sv_query", "visualize", "pipeline",
            "--filelist", STRICT_UART_FILELIST,
            "-d", str(dot_path),
            "--no-strict",
        ],
        capture_output=True, text=True, timeout=60,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


def _normalize_dot(text: str) -> str:
    """Normalize DOT for cross-platform golden comparison.

    去掉:
      - 绝对路径前缀: /Users/.../sv_query/  →  PROJECT_ROOT/
    """
    import re
    text = re.sub(
        r"/Users/[^/]+/my_dv_proj/sv_query/",
        "PROJECT_ROOT/",
        text,
    )
    text = re.sub(
        r"/home/[^/]+/my_dv_proj/sv_query/",
        "PROJECT_ROOT/",
        text,
    )
    return text


def _read_golden() -> str:
    """Read golden DOT file. Auto-create on first run."""
    if not GOLDEN_FILE.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        rc, _, _ = _run_visualize_pipeline(GOLDEN_FILE)
        assert rc == 0, f"baseline generation failed: rc={rc}"
    return GOLDEN_FILE.read_text()


def test_visualize_pipeline_generates_dot():
    """visualize pipeline 应该生成 DOT 文件."""
    tmp_dot = PROJECT_ROOT / "tmp_test_pipeline.dot"
    rc, stdout, stderr = _run_visualize_pipeline(tmp_dot)
    assert rc == 0, f"rc={rc}, stderr={stderr[:200]}"
    assert tmp_dot.exists()
    assert tmp_dot.stat().st_size > 100
    assert "digraph pipeline" in tmp_dot.read_text(), "missing 'digraph pipeline'"
    tmp_dot.unlink()
    print("✅ visualize pipeline: 生成合法 DOT 文件")


def test_visualize_pipeline_stage_counts():
    """visualize pipeline 应输出 stage + register 统计 (stdout + stderr)."""
    import re
    rc, stdout, stderr = _run_visualize_pipeline(PROJECT_ROOT / "tmp_test.dot")
    assert rc == 0
    combined = stdout + stderr
    stages_match = re.search(r"Stages:\s*(\d+)", combined)
    pipeline_regs = re.search(r"Pipeline regs?:\s*(\d+)", combined)
    state_regs = re.search(r"State regs?:\s*(\d+)", combined)
    assert stages_match, f"no 'Stages' in output: stdout={stdout[:200]} stderr={stderr[:200]}"
    assert pipeline_regs, f"no 'Pipeline regs' in output"
    assert state_regs, f"no 'State regs' in output"
    assert int(stages_match.group(1)) >= 1, "no stages detected"
    (PROJECT_ROOT / "tmp_test.dot").unlink(missing_ok=True)
    print(f"✅ visualize pipeline: stages={stages_match.group(1)}, "
          f"pipeline_regs={pipeline_regs.group(1)}, state_regs={state_regs.group(1)}")


def test_visualize_pipeline_uses_lr_layout():
    """visualize pipeline 应使用 LR (左→右) 布局, 表示时间流方向."""
    tmp_dot = PROJECT_ROOT / "tmp_test.dot"
    rc, _, _ = _run_visualize_pipeline(tmp_dot)
    assert rc == 0
    content = tmp_dot.read_text()
    assert "rankdir=LR" in content, "pipeline should use LR layout (time flow)"
    tmp_dot.unlink()
    print("✅ visualize pipeline: LR 布局 (时间流方向)")


def test_visualize_pipeline_golden_match():
    """visualize pipeline DOT 输出应匹配 golden baseline.

    Note: Golden 已 normalize 绝对路径 → PROJECT_ROOT/ 占位符.
    """
    tmp_dot = PROJECT_ROOT / "tmp_test_pipeline_golden.dot"
    rc, _, _ = _run_visualize_pipeline(tmp_dot)
    assert rc == 0, "visualize pipeline failed"
    actual = _normalize_dot(tmp_dot.read_text())
    golden = _normalize_dot(_read_golden())
    if actual != golden:
        import difflib
        diff = "\n".join(difflib.unified_diff(
            golden.splitlines(),
            actual.splitlines(),
            lineterm="",
            fromfile="golden (normalized)",
            tofile="actual (normalized)",
            n=3,
        ))
        tmp_dot.unlink(missing_ok=True)
        pytest.fail(f"Golden mismatch:\n{diff[:2000]}")
    tmp_dot.unlink(missing_ok=True)
    print(f"✅ visualize pipeline: 匹配 golden ({len(golden)} chars)")


if __name__ == "__main__":
    tests = [
        test_visualize_pipeline_generates_dot,
        test_visualize_pipeline_stage_counts,
        test_visualize_pipeline_uses_lr_layout,
        test_visualize_pipeline_golden_match,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} visualize pipeline tests passed!")
