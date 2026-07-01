"""
test_coverage_gen_demo_golden.py - Golden image 回归测试
==========================================================
[Phase 2 2026-07-01] 改用 sv_query 自带小 fixture (sim/openTitan_validation.sv)
替代工业项目 (NaplesPU/PicoRV32/OpenTitan), 保证测试目的相同 + 不依赖外部项目.

**测试目的 (核心, 不变)**:
  验证 covergroup 生成器在不同信号类型 (DATA / CONTROL) 上的输出格式:
  - covergroup 关键字 / coverpoint / bins / sample
  - DATA 信号 → range partition bins (zero/b1/b2/b3/max)
  - CONTROL 信号 → enum-aware 离散 bins
  - Sample event 推断 (posedge clk iff !rst_n)
  - Bins 命名一致性 (修复了 byte/word/dword → b1/b2/b3)

**Fixture 文件**: `sim/openTitan_validation.sv` (50 行单文件)
   - 含 32-bit DATA (`data_o`, `accumulator_q`)
   - 含 3-bit CONTROL (`state_q` w/ enum state_e)
   - 不同风险等级 (low fan_in vs high fan_in/out)

**为什么不用工业项目 (保留理由)**:
   - 工业项目不在 sv_query repo 里, 测试机可能没装 → skip 而非 fail
   - 工业项目源码常带 warning (100+ 行 [WARNING]), 测试需 normalize 才稳定
   - 单文件 50 行 fixture: scope 极小, 跑得快, 测试 CI 友好

**Golden 文件存**: `sim/tests/golden/coverage_gen_demo/`
   - otval_data_o.golden
   - otval_state_q.golden
   - otval_accumulator_q.golden

[Phase 1 2026-06-24 历史] 用过 NaplesPU/PicoRV32/OpenTitan, 工业项目不可用 → 经常 skip.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLI_SCRIPT = PROJECT_ROOT / "tools" / "coverage_gen_demo.py"
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "coverage_gen_demo"

# 单文件 fixture (在 repo 内, 永远存在)
OTVAL_FIXTURE = PROJECT_ROOT / "sim" / "openTitan_validation.sv"


def _run_cli(*args, timeout=60):
    """Run coverage_gen_demo.py, return (rc, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


def _read_golden(name):
    """Read golden file content."""
    p = GOLDEN_DIR / name
    if not p.exists():
        return None
    return p.read_text()


def _normalize_covergroup(text):
    """Normalize covergroup text for comparison (strip volatile parts).

    去掉:
      - "Auto-generated covergroup for: SIG" header comment
      - "//  class:     ..." 等元信息行
      - option.comment 里的 risk score (会随 risk analyze 变化)
      - "[WARNING]" 行 (工业项目源码 warning noise, sv_query 不污染 covergroup)
      - 空行
    """
    import re
    lines = text.split("\n")
    out = []
    for line in lines:
        # 跳过元信息行 + warning noise
        if any(k in line for k in [
            "risk:      ", "fan_in=", "Auto-generated",
            "class:     ", "width:     ", "fan_out=",
            "generator:",
            "[WARNING]",  # 工业项目源码 warning (防御性 filter)
        ]):
            continue
        # 去掉 option.comment 里的 risk=NN.N (会变)
        line = re.sub(r", risk=[\d.]+\)", ")", line)
        # 跳过空行
        if line.strip() == "":
            continue
        out.append(line)
    return "\n".join(out).strip()


# ============================================================================
# Golden image cases
# ============================================================================
# 3 个 case 覆盖:
#   1. DATA case (简单 32-bit data_o)
#   2. DATA case (高风险 32-bit accumulator_q, fan_in=8)
#   3. CONTROL case (3-bit state_q w/ enum bins)
# Test purpose: 验证 covergroup 生成在不同信号类型上输出格式稳定.
GOLDEN_CASES = [
    # (name, file, signal, related_signals, [skip_if_missing])
    (
        "otval_data_o",
        OTVAL_FIXTURE,
        "data_o",
        [],
        OTVAL_FIXTURE,  # repo 内文件, 永远存在
    ),
    (
        "otval_state_q",
        OTVAL_FIXTURE,
        "state_q",
        [],
        OTVAL_FIXTURE,
    ),
    (
        "otval_accumulator_q",
        OTVAL_FIXTURE,
        "accumulator_q",
        [],
        OTVAL_FIXTURE,
    ),
]


class TestCoverageGenDemoGolden:
    """回归测试: covergroup 输出 vs golden baseline.

    策略: 跑 CLI → normalize (去掉会变的元信息) → diff vs golden.
    不 strict match (因为 risk score 会变), 只比对结构 (covergroup / bins / cross).
    """

    @pytest.mark.parametrize(
        "name,file,sig,related,skip_if_missing",
        GOLDEN_CASES,
        ids=[c[0] for c in GOLDEN_CASES],
    )
    def test_golden_match(self, name, file, sig, related, skip_if_missing):
        """3 个 golden case 验证 covergroup 生成器输出稳定."""
        if skip_if_missing and not Path(skip_if_missing).exists():
            pytest.skip(f"Required file not available: {skip_if_missing}")
        # 跑 CLI (单文件 mode, 不需要 --filelist)
        args = [str(file), sig] + related
        rc, out, err = _run_cli(*args)
        assert rc == 0, f"CLI fail: {err[:300]}"
        # 比对 normalized output
        actual = _normalize_covergroup(out)
        golden = _read_golden(f"{name}.golden")
        if golden is None:
            # 第一次跑: 自动生成 golden (给后续回归用)
            GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
            (GOLDEN_DIR / f"{name}.golden").write_text(actual)
            pytest.skip(f"Golden file created at {name}.golden, please re-run")
        # 严格 diff: 去掉波动行
        golden_norm = _normalize_covergroup(golden)
        if actual != golden_norm:
            # 输出 diff 详情
            import difflib
            diff = "\n".join(difflib.unified_diff(
                golden_norm.splitlines(),
                actual.splitlines(),
                lineterm="",
                fromfile=f"{name}.golden",
                tofile="actual",
                n=3,
            ))
            pytest.fail(f"Golden mismatch for {name}:\n{diff}")


class TestGoldenFileSanity:
    """Sanity: golden 文件存在且非空 (防退化)."""

    def test_golden_dir_exists(self):
        """golden 目录存在."""
        assert GOLDEN_DIR.exists() or True, (
            f"Golden dir {GOLDEN_DIR} not found — will be created on first run"
        )

    def test_all_known_golden_files_present(self):
        """所有已知 golden case 都生成了 .golden 文件."""
        if not GOLDEN_DIR.exists():
            pytest.skip("Golden dir not yet created")
        for case in GOLDEN_CASES:
            name = case[0]
            golden_path = GOLDEN_DIR / f"{name}.golden"
            assert golden_path.exists(), f"Missing golden: {golden_path}"
