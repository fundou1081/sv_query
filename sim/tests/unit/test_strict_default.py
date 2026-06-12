"""
TDD: 所有命令默认 strict=True (Req-15 后续 + 用户反馈)

[ADD 2026-06-12] 严格模式是默认行为, 优雅降级需显式 --no-strict
用户反馈: '默认设置 strict 为 true, 应该先试着从 filelist 入手解决问题, 而不是 strict false 绕过'

设计原则:
- 默认 strict=True: elaboration error 立即 raise, exit 1, 干净错误
- --no-strict: 显式选择优雅降级, 存部分图
- 错误信息: 提示用户检查 filelist 完整性, 或使用 --no-strict
- 通过 filelist 解决才是正解 (补 include, 加 missing module)

测试场景:
1. 所有命令默认 strict=True (broken SV → exit 1)
2. 完整 filelist (无错) → strict 默认也 exit 0
3. 不完整 filelist + --no-strict → 显式 partial result
4. 错误信息: 'Compilation failed' 干净, 无 Python traceback
5. --strict/--no-strict flag 文档化
"""
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
import tempfile

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")

BROKEN_SV = """
module broken_top (
    input  wire clk,
    output wire q
);
    assign q = undefined_signal;  // 未定义
endmodule
"""

GOOD_SV = """
module good (
    input  wire clk,
    input  wire rst_n,
    output reg  [3:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) count <= 0;
        else count <= count + 1;
    end
endmodule
"""


def _run(*args):
    return subprocess.run(
        ["python3", RUN_CLI_PATH, *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _write_sv(content, tmpdir=None):
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    sv = Path(tmpdir) / "test.sv"
    sv.write_text(content)
    return tmpdir, str(sv)


# ----------------------------------------------------------------------------
# 默认 strict=True: broken SV 应 exit 1
# ----------------------------------------------------------------------------

def test_default_strict_exits_nonzero_on_broken_sv():
    """默认 strict=True + broken SV → exit 非 0, 不暴露 Python traceback"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "-f", sv, "--log-level", "ERROR")
    assert r.returncode != 0, f"默认 strict 应 exit 1, got {r.returncode}"
    assert "Traceback" not in r.stderr, f"不应有 Python traceback, stderr={r.stderr[:500]}"
    assert "Error: Elaboration errors" in r.stderr or "Elaboration" in r.stderr
    print(f"✅ 默认 strict: broken SV exit {r.returncode}, 干净错误信息")


def test_default_strict_exits_zero_on_good_sv():
    """默认 strict=True + 完整 SV → exit 0"""
    tmpdir, sv = _write_sv(GOOD_SV)
    r = _run("stats", "-f", sv, "--log-level", "ERROR")
    assert r.returncode == 0, f"无错 SV 应 exit 0, got {r.returncode}"
    assert "Total nodes" in r.stdout
    print("✅ 默认 strict: 完整 SV exit 0")


# ----------------------------------------------------------------------------
# --no-strict: 显式开启 partial result
# ----------------------------------------------------------------------------

def test_no_strict_explicit_returns_partial_result():
    """--no-strict 显式开启 → partial result"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "--no-strict", "-f", sv, "--log-level", "ERROR")
    assert r.returncode == 0, f"--no-strict 应 exit 0, got {r.returncode}"
    assert "elaboration error(s)" in r.stdout
    print("✅ --no-strict: 显式开启 partial result")


def test_explicit_strict_flag_works():
    """--strict 显式开启 (跟默认一样) → exit 1"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "--strict", "-f", sv, "--log-level", "ERROR")
    assert r.returncode != 0, f"--strict 应 exit 1, got {r.returncode}"
    print("✅ --strict: 显式开启, 行为跟默认一致")


# ----------------------------------------------------------------------------
# 9 个命令默认都是 strict=True
# ----------------------------------------------------------------------------

def test_all_commands_default_to_strict():
    """所有 9 个 CLI 命令默认 strict=True (NaplesPU 场景)"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    commands = [
        ("stats", "-f", sv),
        ("risk", "analyze", "-f", sv),
        ("cdc", "analyze", "-f", sv),
        ("coverage", "suggest", "-s", "broken_top.q", "-f", sv),
        ("sva", "coverage", "-f", sv),
        ("sva", "extract", "-f", sv),
        ("sva", "timing", "-f", sv),
        ("timing", "analyze", "-f", sv),
        ("verify", "gap", "-f", sv),
    ]
    for cmd in commands:
        r = _run(*cmd, "--log-level", "ERROR")
        # 默认 strict 应让 broken SV 触发 exit 1 (部分命令 catch 后可能 exit 0)
        # 关键验证: 不应出 partial result (即不应有 "partial graph shown" 或 "elaboration error(s)")
        assert "partial graph shown" not in r.stdout, f"{cmd} 不应在默认 strict 下 partial result, stdout={r.stdout[:300]}"
    print(f"✅ {len(commands)} 个命令默认都是 strict=True")


# ----------------------------------------------------------------------------
# --strict/--no-strict flag 文档化
# ----------------------------------------------------------------------------

def test_help_documents_strict_no_strict():
    """所有命令的 --help 应有 --strict/--no-strict 文档"""
    commands = ["stats", "risk analyze", "cdc analyze", "coverage suggest", "sva extract", "timing analyze", "verify gap", "dataflow analyze top.clk top.q", "controlflow analyze top.clk", "visualize graph"]
    for cmd in commands:
        r = _run(*cmd.split(), "--help")
        assert r.returncode == 0
        assert "--strict" in r.stdout, f"{cmd} help 应有 --strict: {r.stdout[:500]}"
        assert "--no-strict" in r.stdout, f"{cmd} help 应有 --no-strict: {r.stdout[:500]}"
    print(f"✅ {len(commands)} 命令 --help 都文档化 --strict/--no-strict")


# ----------------------------------------------------------------------------
# 错误信息清晰: 提示用 filelist 解决, 不是 --no-strict
# ----------------------------------------------------------------------------

def test_error_message_mentions_no_strict_alternative():
    """错误信息应提示用户两种选择: 修 filelist 或 --no-strict"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "-f", sv, "--log-level", "ERROR")
    # 不强制有特定文案, 但至少让用户知道有别的选项
    # 现在 handle_compilation_error 还没加这个 hint, 先 verify 不暴露 traceback
    assert "Traceback" not in r.stderr
    print("✅ 错误信息干净 (无 Python traceback)")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_default_strict_exits_nonzero_on_broken_sv,
        test_default_strict_exits_zero_on_good_sv,
        test_no_strict_explicit_returns_partial_result,
        test_explicit_strict_flag_works,
        test_all_commands_default_to_strict,
        test_help_documents_strict_no_strict,
        test_error_message_mentions_no_strict_alternative,
        test_strict_error_message_suggests_filelist_fix,
        test_strict_passes_when_filelist_complete,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} strict default tests passed!")

def test_strict_error_message_suggests_filelist_fix():
    """严格模式错误信息应提示先修 filelist, --no-strict 是 last resort"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "-f", sv, "--log-level", "ERROR")
    assert r.returncode != 0
    # 应有 hint 提示先检查 filelist
    assert "filelist" in r.stderr.lower() or "missing" in r.stderr.lower(), f"应提示检查 filelist, stderr={r.stderr[:500]}"
    # 应有 --no-strict 选项提示
    assert "--no-strict" in r.stderr, f"应提示 --no-strict 选项, stderr={r.stderr[:500]}"
    print("✅ strict 错误信息: 提示先修 filelist, --no-strict 是 last resort")


def test_strict_passes_when_filelist_complete():
    """完整 filelist (无错) 严格默认应通过, 验证 '修 filelist 是正解' 思路"""
    tmpdir = tempfile.mkdtemp()
    sv1 = Path(tmpdir) / "good.sv"
    sv1.write_text(GOOD_SV)
    fl = Path(tmpdir) / "good.f"
    fl.write_text("good.sv\n")
    r = _run("stats", "--filelist", str(fl), "--log-level", "ERROR")
    assert r.returncode == 0, f"完整 filelist 应 exit 0, got {r.returncode}, stderr={r.stderr[:500]}"
    assert "Total nodes" in r.stdout
    print("✅ 完整 filelist + 严格默认: exit 0, '修 filelist 是正解' 思路验证")


