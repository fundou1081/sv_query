"""
test_coverage_gen_sv_compile.py — Phase 3 #C

测试 tools/coverage_gen_sv_compile.py 工具:
  1. 用 coverage_gen_demo 生成 covergroup
  2. 用 pyslang driver 编译 covergroup
  3. 验证 SV 语法正确 (PASS) 或报告 errors (FAIL)

[Phase 3 #C 2026-06-24] 这套测试是 Phase 2 #1-#6 完成的 covergroup 生成能力
**真实 SV 编译验证**的最后一步.

发现过的 bug:
  - bins byte/word/dword 是 SV 系统类型关键字 → slang 拒绝 (fixed in tools/coverage_gen_demo.py)
  - wrapper module clk/rst name 必须从 generated CG 解析 → 不能 hardcode (fixed in tools/coverage_gen_sv_compile.py)
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLI_SCRIPT = PROJECT_ROOT / "tools" / "coverage_gen_sv_compile.py"


def _run_compile_tool(*args, timeout=120) -> tuple[int, str, str]:
    """Run coverage_gen_sv_compile.py, return (rc, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


# ============================================================================
# Test 1: 单文件 DATA 信号 (openTitan validation)
# ============================================================================
class TestSingleFileDataCompile:
    """单文件 DATA 信号 covergroup 应该 PASS."""

    def test_data_o_simple_pipe_passes(self):
        """simple_pipe.data_o (32-bit DATA) → PASS."""
        rc, out, err = _run_compile_tool(
            "-f", "sim/openTitan_validation.sv",
            "-s", "data_o",
            "-m", "simple_pipe",
            "-r", "valid_i",
        )
        assert rc == 0, f"FAIL (rc={rc}):\nstdout: {out}\nstderr: {err[:500]}"
        assert "PASS" in out, f"missing PASS: {out[:300]}"
        assert "0 errors" in out, f"missing '0 errors': {out[:300]}"

    def test_state_q_fsm_passes(self):
        """openTitan_validation.sv 的 state_q (FSM) → PASS."""
        rc, out, err = _run_compile_tool(
            "-f", "sim/openTitan_validation.sv",
            "-s", "state_q",
        )
        assert rc == 0, f"FAIL (rc={rc}):\nstdout: {out}\nstderr: {err[:500]}"
        assert "PASS" in out


# ============================================================================
# Test 2: 工业项目 + filelist (PicoRV32, OpenTitan, NaplesPU)
# ============================================================================
class TestIndustrialProjectCompile:
    """工业项目生成的 covergroup 应该 PASS.

    跟 test_coverage_gen_demo_golden.py 同样的 3 个项目,
    但加上 SV 编译验证.
    """

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists(),
        reason="picorv32 not available",
    )
    def test_picorv32_mem_addr_passes(self):
        """picorv32 mem_addr (32-bit DATA) → PASS."""
        rc, out, err = _run_compile_tool(
            "--filelist", "sim/tests/pyslang_type_fixtures/industrial_filelists/picorv32.f",
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "-s", "mem_addr",
        )
        assert rc == 0, f"FAIL:\nstdout: {out}\nstderr: {err[:500]}"
        assert "PASS" in out

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv").exists(),
        reason="OpenTitan not available",
    )
    def test_opentitan_max_idx_o_passes(self):
        """OpenTitan prim_max_tree max_idx_o ($clog2(32)=5-bit CONTROL) → PASS."""
        rc, out, err = _run_compile_tool(
            "--filelist", "sim/tests/pyslang_type_fixtures/industrial_filelists/openTitan_prim_max_tree.f",
            "-f", "/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv",
            "-s", "max_idx_o",
        )
        assert rc == 0, f"FAIL:\nstdout: {out}\nstderr: {err[:500]}"
        assert "PASS" in out

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv").exists(),
        reason="NaplesPU not available",
    )
    def test_naplespu_events_counter_passes(self):
        """NaplesPU logger events_counter (32-bit DATA) → PASS."""
        rc, out, err = _run_compile_tool(
            "--filelist", "sim/tests/pyslang_type_fixtures/industrial_filelists/naplespu_logger.f",
            "-f", "/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv",
            "-s", "events_counter",
        )
        assert rc == 0, f"FAIL:\nstdout: {out}\nstderr: {err[:500]}"
        assert "PASS" in out


# ============================================================================
# Test 3: 内部 helper 函数 (parse_signal_decl, _extract_width_from_cg)
# ============================================================================
class TestInternalHelpers:
    """工具内部 helper 函数单元测试."""

    def test_extract_width_from_cg_primary(self):
        """主 coverpoint width 从 option.comment 提取."""
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        from coverage_gen_sv_compile import _extract_width_from_cg
        cg = '''
covergroup cg @(posedge clk);
  option.comment = "data_o (DATA, 16-bit, risk=23.3)";
  cp_data_o: coverpoint data_o {
    bins zero = {0};
  }
endgroup'''
        assert _extract_width_from_cg(cg, "data_o") == 16

    def test_extract_width_from_cg_returns_none_for_missing(self):
        """找不到 signal 返回 None."""
        from coverage_gen_sv_compile import _extract_width_from_cg
        cg = '''
covergroup cg @(posedge clk);
  option.comment = "data_o (DATA, 16-bit, risk=23.3)";
  cp_data_o: coverpoint data_o { bins zero = {0}; }
endgroup'''
        assert _extract_width_from_cg(cg, "nonexistent") is None

    def test_extract_width_from_cg_cross_cp(self):
        """cross coverpoint width 从 cp_<sig>_for_<main> 提取."""
        from coverage_gen_sv_compile import _extract_width_from_cg
        cg = '''
covergroup cg @(posedge clk);
  cp_valid_i_for_data_o: coverpoint valid_i {
    option.comment = "valid_i (CONTROL, 1-bit)";
  }
  cx_data_o_x_valid_i: cross cp_data_o, cp_valid_i_for_data_o;
endgroup'''
        assert _extract_width_from_cg(cg, "valid_i") == 1

    def test_build_wrapper_uses_correct_clk_rst(self):
        """wrapper 必须用 covergroup 里的 clk/rst 名 (不是 hardcoded)."""
        from coverage_gen_sv_compile import build_wrapper
        cg = "covergroup cg_foo @(posedge clk_i iff !rst_ni);\n  cp: coverpoint data { bins x = {0}; }\nendgroup: cg_foo"
        wrapper = build_wrapper(cg, ["logic [7:0] data;"])
        assert "logic clk_i;" in wrapper, f"clk_i missing:\n{wrapper}"
        assert "logic rst_ni;" in wrapper, f"rst_ni missing:\n{wrapper}"
        # 默认 fallback (no iff)
        cg_no_iff = "covergroup cg_bar @(posedge custom_clk);\n  cp: coverpoint x { bins z = {0}; }\nendgroup: cg_bar"
        wrapper2 = build_wrapper(cg_no_iff, ["logic x;"])
        assert "logic custom_clk;" in wrapper2
        # 默认 rst (没 iff 时 fallback 到 rst_n)
        assert "logic rst_n;" in wrapper2


# ============================================================================
# Test 4: 修复的 bug (regression)
# ============================================================================
class TestBugfixRegression:
    """回归测试: 之前发现的 bug 修了, 不能复现."""

    def test_no_sv_keyword_in_bin_names(self):
        """bin 名字不能是 SV 系统类型关键字 (byte/word/dword/shortint/int/logic/bit)."""
        # 跑 compile tool, 检查生成的 cg 文本里没有这种命名
        from coverage_gen_demo import generate_covergroup
        cg = generate_covergroup(
            target_signal="data_o",
            file="sim/openTitan_validation.sv",
            module_name="simple_pipe",
        )
        # bins <NAME> = ... 形式的 NAME 不能是 SV 关键字
        import re
        bin_names = re.findall(r"bins\s+(\w+)", cg)
        sv_keywords = {
            "byte", "shortint", "int", "longint", "logic", "bit", "reg",
            "word", "dword", "qword",  # slang 把它当 type modifier
            "wire", "supply0", "supply1",
            "input", "output", "inout",
        }
        bad = [n for n in bin_names if n in sv_keywords]
        assert not bad, f"bin name 用 SV 关键字: {bad}"