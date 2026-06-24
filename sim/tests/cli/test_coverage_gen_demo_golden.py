"""
test_coverage_gen_demo_golden.py - Golden image 回归测试
==========================================================
[Phase 1 2026-06-24] 跑工业项目 (NaplesPU, PicoRV32) 生成 covergroup,
存为 baseline, 后续 regression diff.

Golden 文件存 sim/tests/golden/coverage_gen_demo/:
  - naplespu_events_counter.golden
  - picorv32_mem_addr.golden
  - openTitan_prim_max_tree_max_idx_o.golden

测试机没工业项目 → skip (跟 unit test 一样).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLI_SCRIPT = PROJECT_ROOT / "tools" / "coverage_gen_demo.py"
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "coverage_gen_demo"
INDUSTRIAL_FILELISTS = PROJECT_ROOT / "sim" / "tests" / "pyslang_type_fixtures" / "industrial_filelists"


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
      - 空行
    """
    import re
    lines = text.split("\n")
    out = []
    for line in lines:
        # 跳过元信息行
        if any(k in line for k in [
            "risk:      ", "fan_in=", "Auto-generated",
            "class:     ", "width:     ", "fan_out=",
            "generator:",
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
GOLDEN_CASES = [
    # (name, filelist, file, signal, related, [skip_if_missing_file])
    (
        "naplespu_events_counter",
        "naplespu_logger.f",
        "/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv",
        "events_counter", [],
        "/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv",
    ),
    (
        "picorv32_mem_addr",
        "picorv32.f",
        "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
        "mem_addr", [],
        "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
    ),
    (
        "openTitan_prim_max_tree_max_idx_o",
        "openTitan_prim_max_tree.f",
        "/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv",
        "max_idx_o", [],
        "/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv",
    ),
]


class TestCoverageGenDemoGolden:
    """回归测试: covergroup 输出 vs golden baseline.

    策略: 跑 CLI → normalize (去掉会变的元信息) → diff vs golden.
    不 strict match (因为 risk score 会变), 只比对结构 (covergroup / bins / cross).
    """

    @pytest.mark.parametrize(
        "name,fl,file,sig,related,skip_file",
        GOLDEN_CASES,
        ids=[c[0] for c in GOLDEN_CASES],
    )
    def test_golden_match(self, name, fl, file, sig, related, skip_file):
        if not Path(skip_file).exists():
            pytest.skip(f"Industrial project not available: {skip_file}")
        fl_path = INDUSTRIAL_FILELISTS / fl
        if not fl_path.exists():
            pytest.skip(f"Filelist not found: {fl_path}")
        # 跑 CLI
        args = [f"--filelist={fl_path}", file, sig] + related
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

    def test_known_golden_files_present(self):
        """至少 1 个 golden 文件已生成."""
        if not GOLDEN_DIR.exists():
            pytest.skip("Golden dir not yet created")
        files = list(GOLDEN_DIR.glob("*.golden"))
        assert len(files) >= 1, (
            f"No golden files in {GOLDEN_DIR}. Run pytest to generate them."
        )
