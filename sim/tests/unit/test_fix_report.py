"""
TDD: fix report CLI 命令 (Req-16 续)

[ADD 2026-06-12] 'fix report' 按修复方向分类所有 elaboration 错误
配合 strict=True 默认 (Req-15 后续), 给用户'从哪里开始修'的指引.

测试场景:
1. 多错误分类: MissingTimeScale / UndeclaredIdentifier / TooFewArguments 等
2. 输出: 总数 / 受影响文件数 / 每个 category 详情 / fix command
3. JSON 输出含 by_category / by_code / auto_fixable count
4. 无错时报 'Project is clean'
5. help 文档化
"""
import json
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")
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
# 单元测试
# ----------------------------------------------------------------------------

def test_fix_recommendations_cover_common_codes():
    """FIX_RECOMMENDATIONS 应含常见错误码"""
    from cli.commands.fix import FIX_RECOMMENDATIONS
    expected = {"MissingTimeScale", "UndeclaredIdentifier", "TooFewArguments", "UnknownModule", "CaseTypeMismatch", "DuplicateDefinition", "EmptyMember"}
    for code in expected:
        assert code in FIX_RECOMMENDATIONS, f"缺 {code} 修复建议"
        assert "fix_command" in FIX_RECOMMENDATIONS[code]
        assert "auto_fixable" in FIX_RECOMMENDATIONS[code]
    print(f"✅ FIX_RECOMMENDATIONS 覆盖 {len(FIX_RECOMMENDATIONS)} 常见错误码")


# ----------------------------------------------------------------------------
# CLI 集成测试
# ----------------------------------------------------------------------------

def _setup_three_sv():
    """建 3 个 SV 模拟多种错误:
    - a.sv: 缺 timescale
    - b.sv: 引用未定义类型 (UndeclaredIdentifier)
    - c.sv: 引用 b 但 typedef 顺序错
    """
    tmpdir = tempfile.mkdtemp()
    a = Path(tmpdir) / "a.sv"
    a.write_text("module a (input wire clk, output wire q); other u_other (.clk(clk), .q(q)); endmodule\n")
    b = Path(tmpdir) / "b.sv"
    # b 引用 undeclared type "my_type"
    b.write_text("`timescale 1ns/1ps\nmodule b (input wire clk, output reg q);\n  always_ff @(posedge clk) q <= MY_UNDEFINED_TYPE;\nendmodule\n")
    c = Path(tmpdir) / "c.sv"
    c.write_text("`timescale 1ns/1ps\nmodule c (input wire clk, output reg q);\n  always_ff @(posedge clk) q <= ~q;\nendmodule\n")
    fl = Path(tmpdir) / "test.f"
    fl.write_text(f"{a.absolute()}\n{b.absolute()}\n{c.absolute()}\n")
    return tmpdir, str(fl)


def test_fix_report_lists_categories():
    """fix report 列出错误类别 + 受影响文件数 + 修复建议"""
    tmpdir, fl = _setup_three_sv()
    r = _run("fix", "report", "--filelist", fl, "--log-level", "ERROR")
    assert r.returncode == 0
    # 关键 sections
    assert "Fix Report" in r.stdout
    assert "Total errors" in r.stdout
    assert "Affected files" in r.stdout
    assert "Error Categories" in r.stdout
    assert "Summary" in r.stdout
    # MissingTimeScale 应被分类 (auto-fixable)
    assert "MissingTimeScale" in r.stdout
    assert "UndeclaredIdentifier" in r.stdout
    # auto-fixable 标记
    assert "auto-fixable" in r.stdout or "manual" in r.stdout
    print("✅ fix report: 列出 category + 受影响文件 + 修复建议")


def test_fix_report_json_structure():
    """fix report --json 应含 by_category / by_code / auto_fixable"""
    tmpdir, fl = _setup_three_sv()
    r = _run("fix", "report", "--filelist", fl, "--log-level", "ERROR", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "total_errors" in data
    assert "total_unique_files" in data
    assert "by_category" in data
    assert "by_code" in data
    assert "auto_fixable" in data
    # by_category 应含每个 category 的 count / unique_files / sample_errors
    for cat, info in data["by_category"].items():
        assert "count" in info
        assert "unique_files" in info
        assert "sample_errors" in info
    print("✅ fix report --json: 结构完整 (by_category / by_code / auto_fixable)")


def test_fix_report_clean_project():
    """完整无错 SV 应报 'Project is clean'"""
    tmpdir = tempfile.mkdtemp()
    sv = Path(tmpdir) / "clean.sv"
    sv.write_text("`timescale 1ns/1ps\nmodule clean (input wire clk, output reg q);\n  always_ff @(posedge clk) q <= ~q;\nendmodule\n")
    fl = Path(tmpdir) / "test.f"
    fl.write_text(f"{sv.absolute()}\n")
    r = _run("fix", "report", "--filelist", fl, "--log-level", "ERROR")
    assert r.returncode == 0
    assert "Project is clean" in r.stdout
    print("✅ fix report: 完整无错 SV → 'Project is clean'")


def test_fix_report_counts_auto_vs_manual():
    """fix report 应区分 auto-fixable (MissingTimeScale) vs manual (其他)"""
    tmpdir, fl = _setup_three_sv()
    r = _run("fix", "report", "--filelist", fl, "--log-level", "ERROR")
    assert r.returncode == 0
    # Summary section
    assert "Auto-fixable" in r.stdout
    assert "Manual fix needed" in r.stdout
    print("✅ fix report: 区分 auto-fixable vs manual")


def test_fix_report_suggests_next_step():
    """fix report 应建议下一步 (跑 fix timescale --apply)"""
    tmpdir, fl = _setup_three_sv()
    r = _run("fix", "report", "--filelist", fl, "--log-level", "ERROR")
    assert r.returncode == 0
    # 建议跑 fix timescale --apply
    assert "fix timescale" in r.stdout
    assert "--apply" in r.stdout
    print("✅ fix report: 建议下一步 (fix timescale --apply)")


def test_fix_report_help_documented():
    """fix report --help 文档化"""
    r = _run("fix", "report", "--help")
    assert r.returncode == 0
    assert "--filelist" in r.stdout
    assert "--json" in r.stdout
    print("✅ fix report --help: 文档化")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_fix_recommendations_cover_common_codes,
        test_fix_report_lists_categories,
        test_fix_report_json_structure,
        test_fix_report_clean_project,
        test_fix_report_counts_auto_vs_manual,
        test_fix_report_suggests_next_step,
        test_fix_report_help_documented,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} fix report tests passed!")
