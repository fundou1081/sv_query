"""
test_coverage_generate.py - run_cli.py coverage generate 集成测试
====================================================================
[Phase 2 2026-06-24] 测 `svq coverage generate` 子命令 (集成到 run_cli.py).
复用 tools/coverage_gen_demo.py 核心函数.

跟 sim/tests/cli/test_coverage_gen_demo.py 区别:
  - test_coverage_gen_demo.py: 测 tools/coverage_gen_demo.py 独立 CLI
  - test_coverage_generate.py: 测 run_cli.py 集成 (跟其他 svq 子命令一致)
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_CLI = PROJECT_ROOT / "run_cli.py"


def _run_cli(*args, timeout=60):
    """Run run_cli.py <args>, return (rc, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, str(RUN_CLI), *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


# ============================================================================
# Test 1: Help / 子命令注册
# ============================================================================
class TestCoverageGenerateCommand:
    """coverage generate 集成到 run_cli.py."""

    def test_subcommand_registered(self):
        """coverage --help 列出 generate 子命令."""
        rc, out, _ = _run_cli("coverage", "--help")
        assert rc == 0
        assert "generate" in out
        assert "suggest" in out  # 已有
        assert "gap" in out      # 已有

    def test_generate_help(self):
        """coverage generate --help 显示所有 flag."""
        rc, out, _ = _run_cli("coverage", "generate", "--help")
        assert rc == 0
        for flag in ["--file", "-f", "--signal", "-s", "--related", "-r",
                     "--filelist", "--include", "-I", "--module",
                     "--no-strict", "--strict",
                     "--output", "-o", "--no-header"]:
            assert flag in out, f"Missing flag: {flag}"


# ============================================================================
# Test 2: 基本生成 (单文件)
# ============================================================================
class TestCoverageGenerateSingleFile:
    """单文件 mode (跟 tools 入口等价)."""

    def test_state_q_with_related(self):
        """state_q (FSM, 3-bit) + 2 related → covergroup 含 cross."""
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "sim/openTitan_validation.sv",
            "-s", "state_q",
            "-r", "mode_i", "-r", "valid_i",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        assert "covergroup cg_state_q" in out
        assert "coverpoint state_q" in out
        # enum bins (state_e)
        assert "bins idle" in out and "bins sleep" in out
        # cross (mode_i + valid_i)
        assert "cp_mode_i_for_state_q" in out
        assert "cp_valid_i_for_state_q" in out
        assert "cx_state_q_x_mode_i" in out
        assert "cx_state_q_x_valid_i" in out

    def test_data_i_32bit_input(self):
        """data_i (32-bit input port) → no iff, 32-bit DATA bins."""
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "sim/openTitan_validation.sv",
            "-s", "data_i",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        assert "DATA, 32-bit" in out
        assert "Input port" in out
        # 32-bit DATA bins
        assert "bins zero  = {32'h0}" in out
        assert "bins max   = {32'hFFFF_FFFF}" in out


# ============================================================================
# Test 3: 多文件 + filelist
# ============================================================================
class TestCoverageGenerateFilelist:
    """多文件 mode + +incdir+ 路径."""

    def test_filelist_with_include_dir(self):
        """多文件 filelist + -I 路径, 跑出 16-bit 跨文件 data_o."""
        fl = PROJECT_ROOT / "sim/tests/pyslang_type_fixtures/industrial_filelists/picorv32.f"
        if not fl.exists() or not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists():
            pytest.skip("picorv32 not available")
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "--filelist", str(fl),
            "-s", "mem_addr",
            "-r", "mem_valid",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        assert "covergroup cg_mem_addr" in out
        assert "32-bit" in out
        # cross mem_valid
        assert "cp_mem_valid_for_mem_addr" in out

    def test_clog2_derived_param(self):
        """OpenTitan prim_max_tree: $clog2(32) 派生参数 → 5-bit."""
        fl = PROJECT_ROOT / "sim/tests/pyslang_type_fixtures/industrial_filelists/openTitan_prim_max_tree.f"
        if not fl.exists() or not Path("/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv").exists():
            pytest.skip("OpenTitan not available")
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv",
            "--filelist", str(fl),
            "-s", "max_idx_o",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        assert "covergroup cg_max_idx_o" in out
        assert "5-bit" in out  # $clog2(32) 派生
        assert "@(posedge clk_i iff !rst_ni)" in out

    def test_naplespu_4_level_chained_include(self):
        """NaplesPU logger: 4 层链式 include + +incdir+."""
        fl = PROJECT_ROOT / "sim/tests/pyslang_type_fixtures/industrial_filelists/naplespu_logger.f"
        if not fl.exists() or not Path("/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv").exists():
            pytest.skip("NaplesPU not available")
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv",
            "--filelist", str(fl),
            "-I", "/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/include",
            "-s", "events_counter",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        assert "covergroup cg_events_counter" in out
        assert "32-bit" in out
        # Data reg + !rst_n
        assert "iff !rst_n" in out


# ============================================================================
# Test 4: --output 写文件
# ============================================================================
class TestCoverageGenerateOutput:
    """--output 写 .sv 文件."""

    def test_output_writes_sv_file(self, tmp_path):
        """--output writes valid SystemVerilog to file."""
        out_file = tmp_path / "cg_state.sv"
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "sim/openTitan_validation.sv",
            "-s", "state_q",
            "-o", str(out_file),
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        # stderr 提示写文件
        assert "Written" in err, f"Expected 'Written' in stderr, got: {err}"
        # 文件存在 + 内容 valid
        assert out_file.exists()
        content = out_file.read_text()
        assert "covergroup cg_state_q" in content
        # 至少 100 bytes
        assert len(content) > 100

    def test_output_relative_path(self, tmp_path, monkeypatch):
        """--output 相对路径: 用 cwd 解析."""
        # 切到 tmp_path 跑
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", str(PROJECT_ROOT / "sim/openTitan_validation.sv"),
            "-s", "data_i",
            "-o", "cg_data_i.sv",
        )
        assert rc == 0
        # 相对路径文件应写在 cwd (project root)
        expected = PROJECT_ROOT / "cg_data_i.sv"
        assert expected.exists()
        expected.unlink()  # cleanup


# ============================================================================
# Test 5: --no-header (golden image 友好)
# ============================================================================
class TestCoverageGenerateNoHeader:
    """--no-header 去掉元信息 (用于 golden diff)."""

    def test_no_header_strips_meta(self):
        """--no-header → 去掉 risk score / fan_in / generator 行."""
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "sim/openTitan_validation.sv",
            "-s", "state_q",
            "--no-header",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        # 元信息行被去掉
        assert "risk:" not in out, "Header should strip 'risk:' line"
        assert "fan_in=" not in out, "Header should strip 'fan_in=' line"
        assert "Auto-generated" not in out
        assert "generator:" not in out
        # 但 covergroup 本身保留
        assert "covergroup cg_state_q" in out
        assert "coverpoint state_q" in out


# ============================================================================
# Test 6: 错误处理
# ============================================================================
class TestCoverageGenerateErrors:
    """错误处理: 缺 signal, file 不存在, etc."""

    def test_missing_required_signal_arg(self):
        """没 -s → typer 报 missing option."""
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-f", "sim/openTitan_validation.sv",
        )
        assert rc != 0  # typer exit 2
        assert "Missing" in err or "--signal" in err

    def test_missing_file_arg(self):
        """没 -f 也没 --filelist → 报 ERROR."""
        rc, out, err = _run_cli(
            "coverage", "generate",
            "-s", "state_q",
        )
        assert rc != 0
        assert "--file" in err or "filelist" in err or "required" in err.lower()


# ============================================================================
# Test 7: 跨 module signal (Phase 2 #4)
# ============================================================================
class TestCoverageGenerateCrossModule:
    """[Phase 2 2026-06-24] 测 hierarchical signal lookup (e.g. u_sub.data_o)."""

    def test_submodule_1level(self):
        """1 层 submodule: u_middle.pipe_q (32-bit)."""
        rc, out, _ = _run_cli(
            "coverage", "generate",
            "-f", "sim/tests/pyslang_type_fixtures/cross_module_hier.sv",
            "-s", "u_middle.pipe_q",
        )
        assert rc == 0
        assert "covergroup cg_u_middle_pipe_q" in out
        assert "32-bit" in out
        # coverpoint 内部用 hierarchical ref
        assert "coverpoint u_middle.pipe_q" in out

    def test_submodule_2level_nested(self):
        """2 层 nested submodule: u_middle.u_sub.data_o."""
        rc, out, _ = _run_cli(
            "coverage", "generate",
            "-f", "sim/tests/pyslang_type_fixtures/cross_module_hier.sv",
            "-s", "u_middle.u_sub.data_o",
        )
        assert rc == 0
        assert "covergroup cg_u_middle_u_sub_data_o" in out
        assert "32-bit" in out
        assert "coverpoint u_middle.u_sub.data_o" in out

    def test_submodule_clog2_across_modules(self):
        """2 层 nested + $clog2(4)=2-bit: u_middle.u_sub.depth_idx_o."""
        rc, out, _ = _run_cli(
            "coverage", "generate",
            "-f", "sim/tests/pyslang_type_fixtures/cross_module_hier.sv",
            "-s", "u_middle.u_sub.depth_idx_o",
        )
        assert rc == 0
        assert "covergroup cg_u_middle_u_sub_depth_idx_o" in out
        assert "2-bit" in out
        # CONTROL signal
        assert "CONTROL" in out.split("option.comment")[1].split("\n")[0]

    def test_submodule_with_related_filters_data(self):
        """Cross 跨 module: related 含 DATA (din 32-bit) 应被过滤, 只留 CONTROL (enable_i)."""
        rc, out, _ = _run_cli(
            "coverage", "generate",
            "-f", "sim/tests/pyslang_type_fixtures/cross_module_hier.sv",
            "-s", "u_middle.u_sub.depth_idx_o",
            "-r", "enable_i",  # CONTROL 1-bit
            "-r", "din",       # DATA 32-bit → 应被过滤
        )
        assert rc == 0
        # 只有 enable_i 在 cross, din 被过滤
        assert "cp_enable_i" in out
        assert "cp_din" not in out

    def test_nonexistent_submodule_prints_error(self):
        """不存在的 submodule path → 工具 graceful (返回 None width, 1-bit fallback)."""
        rc, out, _ = _run_cli(
            "coverage", "generate",
            "-f", "sim/tests/pyslang_type_fixtures/cross_module_hier.sv",
            "-s", "u_nonexistent.signal",
        )
        # 工具会 fallback (1-bit width), 输出 covergroup 但 width 不对
        assert rc == 0
        # fallback 1-bit CONTROL
        assert "covergroup cg_u_nonexistent_signal" in out


# ============================================================================
# Phase 2 #6: Packed struct field bins in covergroup output
# ============================================================================
class TestPackedStructFieldBins:
    """[Phase 2 #6 2026-06-24] 验证 packed struct 的字段 bins 出现在 covergroup body.

    Fixture: type_taxonomy.sv 的 instr_t 是 packed struct { logic[7:0] opcode; logic[23:0] addr; }
    期望 covergroup body 包含:
      bins opcode = instr_i[7:0];
      bins addr   = instr_i[31:8];
    """

    def test_packed_struct_field_bins_present(self):
        """packed struct 字段 bins 出现在 covergroup body."""
        from pathlib import Path as P
        rc, out, err = _run_cli(
            "coverage", "generate",
            "--filelist", "sim/tests/pyslang_type_fixtures/industrial_filelists/type_taxonomy.f",
            "-f", str(P("sim/tests/pyslang_type_fixtures/type_taxonomy.sv")),
            "-s", "instr_i",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        # 验证 packed struct 字段 bins 出现在 covergroup
        assert "bins opcode = instr_i[7:0];" in out, f"missing opcode bin in:\n{out[:500]}"
        assert "bins addr = instr_i[31:8];" in out, f"missing addr bin in:\n{out[:500]}"
        # 验证 Phase 2 #6 注释
        assert "Packed struct fields (Phase 2 #6)" in out

    def test_packed_union_skips_field_bins(self):
        """packed union 字段重叠, 跳过字段 bins (避免 SV 编译错).

        Fixture: word_u_t 是 packed union { logic[31:0] raw; struct { 4 bytes } bytes; }
        字段重叠, 不应输出字段 bins.
        """
        from pathlib import Path as P
        rc, out, err = _run_cli(
            "coverage", "generate",
            "--filelist", "sim/tests/pyslang_type_fixtures/industrial_filelists/type_taxonomy.f",
            "-f", str(P("sim/tests/pyslang_type_fixtures/type_taxonomy.sv")),
            "-s", "word_u_i",
        )
        assert rc == 0, f"CLI fail: {err[:300]}"
        # union 不应有 packed struct fields 注释
        assert "Packed struct fields (Phase 2 #6)" not in out, "union should skip struct fields"
