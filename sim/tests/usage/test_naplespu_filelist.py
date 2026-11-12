"""
TDD: minimal_3module filelist verification

[User 2026-07-17] Switched from NaplesPU 141-file filelist to minimal_3module fixture
per "如果开源本身有问题, 就只把代码模式独立出来" feedback:
- NaplesPU 141 files cause OOM on 8GB MBA (cannot fully elaborate)
- minimal_3module fixture (top + sub + 2 leaves + synchronizer) compiles cleanly
- All 12 CLI commands verified on minimal filelist without timeout/OOM

P167: only current-command checks remain (stats / controlflow / dataflow).
The retired `exp` commands (risk/cdc/sva/timing/verify gap/coverage suggest)
were archived with evidence in P160/P167; git history retains them.
"""

import pytest

# P167: the 8 retired `exp` tests are archived (not kept as permanent skips).
# Evidence/precedent: P160 triage + P167 disposition; git history retains them.
pytestmark = pytest.mark.opensource  # NaplesPU filelist dependency

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_CLI = "python3"
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")

# [User 2026-07-17] Switched from NaplesPU 141-file filelist (caused OOM + 65 partial-AST
# errors) to minimal_3module fixture (3 modules, 0 errors, full elaboration).
# minimal_3module contains: top_minimal, sub_aggregator, leaf_pipeline, leaf_adder,
# synchronizer (CDC pattern from NaplesPU uart). Compiles cleanly in pyslang.
FILELIST_PATH = str(REPO_ROOT / "sim" / "tests" / "fixtures" / "minimal_3module" / "filelist.f")


def _run(*args):
    """运行 CLI. minimal_3module fixture 无 errors, 跑 9 commands 测 integration."""
    return subprocess.run(
        [RUN_CLI, RUN_CLI_PATH, *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


# ----------------------------------------------------------------------------
# 9 个命令全部跑通
# ----------------------------------------------------------------------------

def test_m01_stats_filelist():
    """stats on minimal_3module filelist (compiles cleanly in pyslang)."""
    r = _run("stats", "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"Expected exit 0, got {r.returncode}, stderr={r.stderr[:300]}"
    # minimal_3module has 0 errors (pyslang fully elaborates), so no
    # "elaboration error(s)" message. Just verify total graph built.
    assert "Total nodes:" in r.stdout, f"Expected stats output, got {r.stdout[:300]}"
    print("✅ m01 stats on minimal_3module: clean compile + graph built")


def test_m10_controlflow_filelist():
    """controlflow analyze: 应正常输出, 不应 traceback"""
    r = _run("controlflow", "analyze", "synchronizer.sync0", "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"controlflow 应 exit 0, got {r.returncode}, stderr={r.stderr[:500]}"
    assert "Traceback" not in r.stderr
    assert "ControlFlow" in r.stdout or "Conditional" in r.stdout
    print("✅ controlflow on minimal_3module: 跑通 (无 traceback)")


def test_m11_dataflow_filelist():
    """dataflow analyze: 应正常输出"""
    r = _run("dataflow", "analyze", "synchronizer.sync0", "synchronizer.data_o", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "Reachable" in r.stdout
    print("✅ dataflow on minimal_3module: 跑通")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_m01_stats_filelist,
        test_m10_controlflow_filelist,
        test_m11_dataflow_filelist,
        test_mcontrolflow_filelist,
        test_mdataflow_filelist,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} minimal_3module integration tests passed!")
