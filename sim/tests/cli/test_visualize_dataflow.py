"""
test_visualize_dataflow.py - Golden test for `sv_query visualize dataflow`
======================================================================
[ADD 2026-07-03] Phase 4 (方豆要求: 3 命令加测试 + golden).

**测试目的 (核心)**:
  验证 `visualize dataflow` 命令生成的 DOT 图结构稳定.
  - 节点数量 (Data / Control / Clock)
  - 节点 label (signal 名称 + 类型 + 位宽)
  - 边 (data 蓝色实线 / control 橙色虚线)
  - DOT 结构 (rankdir / label / legend)

**Fixture**: `sim/tests/fixtures/strict_uart/filelist.f` (3 SV, 自洽)
  - 不依赖外部项目源码 (NaplesPU/OpenTitan 等)
  - 跨平台稳定 (无绝对路径 / 无行号)

**Golden 文件**: `sim/tests/golden/visualize_dataflow/strict_uart.dot`
  - 首次跑生成 baseline
  - 后续跑 diff 校验 (跟 test_coverage_gen_demo_golden.py 同样模式)
"""
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "visualize_dataflow"
GOLDEN_FILE = GOLDEN_DIR / "strict_uart.dot"


def _run_visualize_dataflow(dot_path: Path) -> tuple[int, str, str]:
    """Run `sv_query visualize dataflow` with filelist, return (rc, stdout, stderr)."""
    p = subprocess.run(
        [
            "sv_query", "visualize", "dataflow",
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
        # 首次跑: 生成 baseline
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        rc, _, _ = _run_visualize_dataflow(GOLDEN_FILE)
        assert rc == 0, f"baseline generation failed: rc={rc}"
    return GOLDEN_FILE.read_text()


def test_visualize_dataflow_generates_dot():
    """visualize dataflow 应该生成 DOT 文件."""
    tmp_dot = PROJECT_ROOT / "tmp_test_dataflow.dot"
    rc, stdout, stderr = _run_visualize_dataflow(tmp_dot)
    assert rc == 0, f"rc={rc}, stderr={stderr[:200]}"
    assert tmp_dot.exists(), "DOT file not generated"
    assert tmp_dot.stat().st_size > 100, "DOT file too small"
    assert "digraph dataflow" in tmp_dot.read_text(), "DOT file missing 'digraph dataflow'"
    tmp_dot.unlink()
    print("✅ visualize dataflow: 生成合法 DOT 文件")


def test_visualize_dataflow_node_counts():
    """visualize dataflow 应输出节点统计 (Data / Control / Clock) 到 stdout."""
    import re
    rc, stdout, stderr = _run_visualize_dataflow(PROJECT_ROOT / "tmp_test.dot")
    assert rc == 0
    # 节点统计 (Data / Control / Clock 在 stdout, ✓ DOT 在 stderr)
    combined = stdout + stderr
    data_match = re.search(r"Data nodes:\s*(\d+)", combined)
    control_match = re.search(r"Control nodes:\s*(\d+)", combined)
    clock_match = re.search(r"Clock nodes:\s*(\d+)", combined)
    assert data_match, f"no 'Data nodes' in output: stdout={stdout[:200]} stderr={stderr[:200]}"
    assert control_match, f"no 'Control nodes' in output"
    assert clock_match, f"no 'Clock nodes' in output"
    # 节点数应该 > 0
    assert int(data_match.group(1)) > 0, "no data nodes"
    assert int(control_match.group(1)) > 0, "no control nodes"
    (PROJECT_ROOT / "tmp_test.dot").unlink(missing_ok=True)
    print(f"✅ visualize dataflow: 节点统计 (Data={data_match.group(1)}, "
          f"Control={control_match.group(1)}, Clock={clock_match.group(1)})")


def test_visualize_dataflow_golden_match():
    """visualize dataflow DOT 输出应匹配 golden baseline.

    Golden 文件: `sim/tests/golden/visualize_dataflow/strict_uart.dot`
    首次跑自动生成, 后续跑 diff 校验 (项目纪律).

    Note: Golden 已 normalize 绝对路径 → PROJECT_ROOT/ 占位符.
    """
    tmp_dot = PROJECT_ROOT / "tmp_test_dataflow_golden.dot"
    rc, _, _ = _run_visualize_dataflow(tmp_dot)
    assert rc == 0, "visualize dataflow failed"
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
    print(f"✅ visualize dataflow: 匹配 golden ({len(golden)} chars)")


if __name__ == "__main__":
    tests = [
        test_visualize_dataflow_generates_dot,
        test_visualize_dataflow_node_counts,
        test_visualize_dataflow_golden_match,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} visualize dataflow tests passed!")
