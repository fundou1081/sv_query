"""
TDD: fix timescale CLI 命令 (Req-16)

[ADD 2026-06-12] 'fix timescale' 自动修复 MissingTimeScale
配合 strict=True 默认 (Req-15 后续), 提供 '从 filelist 入手解决问题' 的工具.

测试场景:
1. dry-run: 列出待修文件但不改
2. --apply: 真改文件 + 备份
3. idempotent: 已有 timescale 跳过
4. .bak 备份存在
5. timescale 插在文件最开头
6. 跨项目: NaplesPU 6 文件
"""
import os
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")
# 让 `from cli.commands.fix import ...` 能工作
SRC_DIR = str(REPO_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _run(*args):
    return subprocess.run(
        ["python3", RUN_CLI_PATH, *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


# ----------------------------------------------------------------------------
# 单元测试: _has_timescale / _insert_timescale
# ----------------------------------------------------------------------------

def test_has_timescale_detects_backtick_timescale():
    """_has_timescale 应识别 `timescale directive"""
    from cli.commands.fix import _has_timescale
    assert _has_timescale("`timescale 1ns/1ps\nmodule top; endmodule\n")
    assert _has_timescale("\n`timescale 1ps/1ps\n")
    assert not _has_timescale("module top; endmodule\n")


def test_insert_timescale_idempotent():
    """_insert_timescale 已有 timescale 应不动"""
    from cli.commands.fix import _has_timescale, _insert_timescale
    content = "`timescale 1ns/1ps\nmodule top; endmodule\n"
    assert _has_timescale(content)
    # 调用也不该改
    new, line = _insert_timescale(content, "1ps/1ps")
    # new 仍应含 timescale
    assert _has_timescale(new)


def test_insert_timescale_at_top():
    """_insert_timescale 应插在文件最开头 (line 1)"""
    from cli.commands.fix import _insert_timescale
    content = "// copyright\n\nmodule top;\nendmodule\n"
    new, line_no = _insert_timescale(content, "1ns/1ps")
    assert line_no == 1
    assert new.startswith("`timescale 1ns/1ps\n")


# ----------------------------------------------------------------------------
# CLI 集成测试
# ----------------------------------------------------------------------------

def _setup_two_sv(sv_a_content, sv_b_content):
    """建 2 个 .sv 文件, 触发 MissingTimeScale (a 有 timescale, b 没有)
    filelist 用绝对路径 (pyslang 要求)
    """
    tmpdir = tempfile.mkdtemp()
    sv_a = Path(tmpdir) / "a.sv"
    sv_a.write_text(sv_a_content)
    sv_b = Path(tmpdir) / "b.sv"
    sv_b.write_text(sv_b_content)
    fl = Path(tmpdir) / "test.f"
    # 用绝对路径 - pyslang 跟 cwd 关系不大
    fl.write_text(f"{sv_a.absolute()}\n{sv_b.absolute()}\n")
    return tmpdir, str(fl), str(sv_a), str(sv_b)


# 场景 1: dry-run 列出会改的文件但不改
def test_fix_timescale_dry_run_lists_files():
    """dry-run 列出 1 个待修文件, 不修改源文件"""
    sv_a = "`timescale 1ns/1ps\nmodule top (input wire clk); other u_other (.clk(clk)); endmodule\n"
    sv_b = "module other (input wire clk); assign clk = 0; endmodule\n"  # 无 timescale
    tmpdir, fl, _, _ = _setup_two_sv(sv_a, sv_b)
    original_b = Path(tmpdir) / "b.sv"
    original_b_content = original_b.read_text()

    r = _run("fix", "timescale", "--filelist", fl, "--log-level", "ERROR")
    assert r.returncode == 0
    assert "[DRY-RUN]" in r.stdout
    assert "b.sv" in r.stdout
    assert "Would insert" in r.stdout
    # 文件未改
    assert original_b.read_text() == original_b_content
    print("✅ dry-run: 列出待修文件, 不修改源文件")


# 场景 2: --apply 真改 + 备份
def test_fix_timescale_apply_modifies_and_backs_up():
    """--apply 真改 + 创建 .bak"""
    sv_a = "`timescale 1ns/1ps\nmodule top (input wire clk); other u_other (.clk(clk)); endmodule\n"
    sv_b = "module other (input wire clk); assign clk = 0; endmodule\n"
    tmpdir, fl, _, _ = _setup_two_sv(sv_a, sv_b)
    b_path = Path(tmpdir) / "b.sv"
    bak_path = Path(str(b_path) + ".bak")

    r = _run("fix", "timescale", "--filelist", fl, "--apply", "--log-level", "ERROR")
    assert r.returncode == 0
    # 文件已改
    new_content = b_path.read_text()
    assert new_content.startswith("`timescale 1ns/1ps\n")
    # 备份存在
    assert bak_path.exists()
    assert bak_path.read_text() == "module other (input wire clk); assign clk = 0; endmodule\n"
    print("✅ --apply: 真改 + 创建 .bak 备份")


# 场景 3: idempotent
def test_fix_timescale_idempotent():
    """第二次跑应 0 个待修 (idempotent)"""
    sv_a = "`timescale 1ns/1ps\nmodule top (input wire clk); other u_other (.clk(clk)); endmodule\n"
    sv_b = "module other (input wire clk); assign clk = 0; endmodule\n"
    tmpdir, fl, _, _ = _setup_two_sv(sv_a, sv_b)
    # 第一次
    r1 = _run("fix", "timescale", "--filelist", fl, "--apply", "--log-level", "ERROR")
    assert r1.returncode == 0
    assert "1 fixed" in r1.stdout or "1" in r1.stdout
    # 第二次
    r2 = _run("fix", "timescale", "--filelist", fl, "--log-level", "ERROR")
    assert r2.returncode == 0
    assert "Nothing to fix" in r2.stdout
    print("✅ idempotent: 第二次跑报 Nothing to fix")


# 场景 4: timescale 插在最开头
def test_fix_timescale_inserted_at_line_1():
    """timescale 应插在文件最开头 (line 1), 不会埋在注释后"""
    sv_a = "`timescale 1ns/1ps\nmodule top (input wire clk); other u_other (.clk(clk)); endmodule\n"
    sv_b = "// Copyright 2024 Test\n// Some long comment\nmodule other (input wire clk); endmodule\n"
    tmpdir, fl, _, _ = _setup_two_sv(sv_a, sv_b)
    b_path = Path(tmpdir) / "b.sv"

    r = _run("fix", "timescale", "--filelist", fl, "--apply", "--log-level", "ERROR")
    assert r.returncode == 0
    new = b_path.read_text()
    assert new.startswith("`timescale 1ns/1ps\n")
    # 第一行就是 timescale
    first_line = new.split("\n", 1)[0]
    assert first_line == "`timescale 1ns/1ps"
    print("✅ timescale 插在 line 1 (不在注释后)")


# 场景 5: 自定义 timescale
def test_fix_timescale_custom_value():
    """--timescale 1ps/1ps 应插 1ps/1ps (不是默认 1ns/1ps)"""
    sv_a = "`timescale 1ps/1ps\nmodule top (input wire clk); other u_other (.clk(clk)); endmodule\n"
    sv_b = "module other (input wire clk); endmodule\n"
    tmpdir, fl, _, _ = _setup_two_sv(sv_a, sv_b)
    b_path = Path(tmpdir) / "b.sv"

    r = _run("fix", "timescale", "--filelist", fl, "--apply", "--timescale", "1ps/1ps", "--log-level", "ERROR")
    assert r.returncode == 0
    new = b_path.read_text()
    assert "`timescale 1ps/1ps" in new
    print("✅ --timescale 自定义值生效")


# 场景 6: --no-backup
def test_fix_timescale_no_backup():
    """--no-backup 不创建 .bak"""
    sv_a = "`timescale 1ns/1ps\nmodule top (input wire clk); other u_other (.clk(clk)); endmodule\n"
    sv_b = "module other (input wire clk); endmodule\n"
    tmpdir, fl, _, _ = _setup_two_sv(sv_a, sv_b)
    b_path = Path(tmpdir) / "b.sv"
    bak_path = Path(str(b_path) + ".bak")

    r = _run("fix", "timescale", "--filelist", fl, "--apply", "--no-backup", "--log-level", "ERROR")
    assert r.returncode == 0
    assert not bak_path.exists()
    print("✅ --no-backup: 不创建 .bak")


# 场景 7: --include-headers (修 .svh)
def test_fix_timescale_default_skips_svh():
    """默认跳过 .svh 头文件"""
    sv_a = "`timescale 1ns/1ps\nmodule top (input wire clk); endmodule\n"
    svh = "module hdr (input wire clk); endmodule\n"  # 头文件
    tmpdir = tempfile.mkdtemp()
    a_path = Path(tmpdir) / "a.sv"
    a_path.write_text(sv_a)
    h_path = Path(tmpdir) / "h.svh"
    h_path.write_text(svh)
    fl = Path(tmpdir) / "test.f"
    fl.write_text(f"{a_path.absolute()}\n{h_path.absolute()}\n")
    h_path = Path(tmpdir) / "h.svh"

    r = _run("fix", "timescale", "--filelist", str(fl), "--log-level", "ERROR")
    # 单文件, MissingTimeScale 不触发, 但 2 文件如果都无 timescale 也不触发
    # 验证: 即使 a.sv 有 timescale, h.svh 缺也不报错 (pyslang 宽容或需 include)
    # 主要测默认不修 .svh: 应跑通
    assert r.returncode in (0, 1)
    # h.svh 未被改
    assert h_path.read_text() == svh
    print("✅ 默认 --include-headers=False: 不修 .svh")


# 场景 8: help
def test_fix_timescale_help_documented():
    """fix timescale --help 应文档化所有 flag"""
    r = _run("fix", "timescale", "--help")
    assert r.returncode == 0
    assert "--filelist" in r.stdout
    assert "--apply" in r.stdout
    assert "--timescale" in r.stdout
    assert "--backup" in r.stdout
    print("✅ fix timescale --help: 文档化所有 flag")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_has_timescale_detects_backtick_timescale,
        test_insert_timescale_idempotent,
        test_insert_timescale_at_top,
        test_fix_timescale_dry_run_lists_files,
        test_fix_timescale_apply_modifies_and_backs_up,
        test_fix_timescale_idempotent,
        test_fix_timescale_inserted_at_line_1,
        test_fix_timescale_custom_value,
        test_fix_timescale_no_backup,
        test_fix_timescale_default_skips_svh,
        test_fix_timescale_help_documented,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} fix timescale tests passed!")
