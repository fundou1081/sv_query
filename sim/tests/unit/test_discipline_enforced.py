"""
test_discipline_enforced.py - Pytest wrapper for check_discipline.py
==================================================================
[Phase 5 2026-07-03] 方豆要求: discipline 强制测试 (small).

把 .github/workflows/check_discipline.py 的 3 个检查包装成 pytest,
让 discipline 在 `pytest` 时自动跑 (不依赖开发者手动跑 pre-commit).

Discipline 规则 (跟 check_discipline.py 一致):
1. NO regex in src/trace/core/ (用 AST, 不用 re.findall/match/search)
2. NO 3-level-deep dirs under src/trace
3. NO igraph / graphviz imports (用 DOT 输出, 不绑定)

测试策略:
- 复用 check_discipline.py 的 main() 逻辑
- 不直接 import (它要 os.chdir 到 repo root)
- 改用 subprocess 跑 check_discipline.py, 拿 rc
- rc != 0 → fail (纪律违规)
- stdout/stderr 给 user 看具体违规

这样:
- `pytest sim/tests/unit/test_discipline_enforced.py` 自动跑纪律
- tests.yml 跑全套 pytest 时纪律必跑 (不漏)
- 开发者可以本地 `pytest` 验证, 不需要单独跑 check_discipline
"""
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = PROJECT_ROOT / ".github" / "workflows" / "check_discipline.py"


def _run_check_discipline() -> tuple[int, str, str]:
    """Run check_discipline.py, return (rc, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT)],
        capture_output=True, text=True, timeout=30,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


def test_check_discipline_script_exists():
    """discipline 脚本应存在 (项目纪律)."""
    assert CHECK_SCRIPT.exists(), f"missing discipline script: {CHECK_SCRIPT}"
    assert CHECK_SCRIPT.stat().st_size > 100, "discipline script too small"
    print(f"✅ discipline script exists: {CHECK_SCRIPT.relative_to(PROJECT_ROOT)}")


def test_no_regex_in_trace_core():
    """src/trace/core/ 不应用 regex 分析 SV 源码 (用 AST, 不用 re)."""
    rc, stdout, stderr = _run_check_discipline()
    if rc != 0 and "正则" in stdout:
        pytest.fail(
            f"Discipline violation: regex used in src/trace/core/\n"
            f"--- stdout ---\n{stdout[:1000]}"
        )
    print("✅ no regex usage in src/trace/core/")


def test_no_forbidden_imports():
    """禁止 igraph / graphviz 直接 import (保持 DOT 输出, 不绑死渲染)."""
    rc, stdout, stderr = _run_check_discipline()
    if rc != 0 and ("igraph" in stdout or "graphviz" in stdout):
        pytest.fail(
            f"Discipline violation: forbidden import (igraph/graphviz)\n"
            f"--- stdout ---\n{stdout[:1000]}"
        )
    print("✅ no forbidden imports (igraph / graphviz)")


def test_no_excessive_directory_depth():
    """src/trace 目录深度 ≤ 3 (避免过深, 保持清晰)."""
    rc, stdout, stderr = _run_check_discipline()
    if rc != 0 and "目录过深" in stdout:
        pytest.fail(
            f"Discipline violation: directory depth > 3 in src/trace\n"
            f"--- stdout ---\n{stdout[:1000]}"
        )
    print("✅ src/trace directory depth ≤ 3")


def test_check_discipline_passes_overall():
    """整合: 跑 check_discipline.py 整体, rc=0 表示纪律全过."""
    rc, stdout, stderr = _run_check_discipline()
    if rc != 0:
        pytest.fail(
            f"Discipline check failed (rc={rc})\n"
            f"--- stdout ---\n{stdout[:1500]}\n"
            f"--- stderr ---\n{stderr[:500]}"
        )
    print("✅ all 3 discipline checks pass:\n"
          f"   {stdout.strip().split(chr(10))[-1] if stdout else 'N/A'}")


if __name__ == "__main__":
    tests = [
        test_check_discipline_script_exists,
        test_no_regex_in_trace_core,
        test_no_forbidden_imports,
        test_no_excessive_directory_depth,
        test_check_discipline_passes_overall,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} discipline tests passed!")
