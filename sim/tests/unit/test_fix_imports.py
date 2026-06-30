"""
TDD: fix imports CLI 命令 (Req-18)

[ADD 2026-06-12] 'fix imports' 通过诊断 + 扫项目, 推荐补 filelist 的文件.
设计目标 '使用更方便': 一行命令, 自动找 project_root, 默认 dry-run.

测试场景:
1. UndeclaredIdentifier 错误 → fix imports 报告缺哪个 typedef/module
2. 扫项目找到定义 → 推荐 fix 文件
3. 缺定义时 → 'not in project' 提示
4. --write 写新 filelist
5. --project-root 显式指定扫描目录
6. JSON 输出
7. help 文档化
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
        timeout=120,
    )


def _setup_project_with_missing_typedef():
    """建一个 mini project:
    - lib.sv: 定义 my_typedef_t
    - main.sv: 用 my_typedef_t (应 OK)
    - broken.sv: 用 undefined_typedef_t (应 UndeclaredIdentifier)
    - filelist 只含 main.sv + broken.sv (不含 lib.sv)
    """
    tmpdir = tempfile.mkdtemp()
    proj = Path(tmpdir) / "proj"
    proj.mkdir()
    src = proj / "src"
    src.mkdir()
    # lib 定义 my_typedef_t
    (src / "lib.sv").write_text("`timescale 1ns/1ps\ntypedef logic [7:0] my_typedef_t;\n")
    # main 用 my_typedef_t (OK)
    (src / "main.sv").write_text(
        "`timescale 1ns/1ps\nmodule main (input wire clk, output logic [7:0] q);\n  always_ff @(posedge clk) q <= my_typedef_t'(0);\nendmodule\n"
    )
    # broken 用 undefined_typedef_t (错)
    (src / "broken.sv").write_text(
        "`timescale 1ns/1ps\nmodule broken (input wire clk, output logic [7:0] q);\n  always_ff @(posedge clk) q <= undefined_typedef_t'(0);\nendmodule\n"
    )
    # filelist 只含 main + broken (缺 lib)
    fl = Path(tmpdir) / "test.f"
    fl.write_text(f"{(src / 'main.sv').absolute()}\n{(src / 'broken.sv').absolute()}\n")
    return tmpdir, str(fl), str(proj)


# ----------------------------------------------------------------------------
# 单元测试
# ----------------------------------------------------------------------------

def test_extract_definitions_finds_typedef():
    """_extract_definitions_from_file 应识别 typedef / module / package / define"""
    from cli.commands.fix_imports import _extract_definitions_from_file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".sv", mode="w", delete=False) as f:
        f.write("`timescale 1ns/1ps\nmodule foo (input wire clk); endmodule\ntypedef logic [7:0] my_typedef_t;\npackage my_pkg; endpackage\n`define MY_MACRO 1\n")
        f_path = f.name
    try:
        defs = _extract_definitions_from_file(Path(f_path))
        assert "foo" in defs, f"应含 module foo, got {defs}"
        assert "my_typedef_t" in defs
        assert "my_pkg" in defs
        assert "MY_MACRO" in defs
    finally:
        os.unlink(f_path)
    print("✅ _extract_definitions_from_file: 识别 typedef/module/package/define")


def test_scan_project_finds_identifier():
    """_scan_project_for_identifier 应找到含 identifier 定义的文件"""
    from cli.commands.fix_imports import _scan_project_for_identifier
    tmpdir, fl, proj = _setup_project_with_missing_typedef()
    found = _scan_project_for_identifier(Path(proj), "my_typedef_t")
    assert found is not None, "应找到 my_typedef_t 定义, got None"
    assert "lib.sv" in str(found), f"应指向 lib.sv, got {found}"
    print("✅ _scan_project_for_identifier: 找到 my_typedef_t 在 lib.sv")


def test_scan_project_returns_none_for_missing():
    """_scan_project_for_identifier 找不到时返回 None"""
    from cli.commands.fix_imports import _scan_project_for_identifier
    tmpdir, fl, proj = _setup_project_with_missing_typedef()
    found = _scan_project_for_identifier(Path(proj), "totally_undefined_xyz")
    assert found is None
    print("✅ _scan_project_for_identifier: 找不到返回 None")


# ----------------------------------------------------------------------------
# CLI 集成测试
# ----------------------------------------------------------------------------

def test_fix_imports_lists_undefined_identifiers():
    """fix imports 应列出未定义 identifier (即使项目里没定义, 也列出)"""
    tmpdir, fl, proj = _setup_project_with_missing_typedef()
    r = _run("fix", "imports", "--filelist", fl, "--project-root", proj, "--log-level", "ERROR")
    assert r.returncode == 0, f"stderr={r.stderr[:300]}"
    # 应有 undefined_typedef_t (项目里没定义)
    assert "undefined_typedef_t" in r.stdout, f"应列出 undefined_typedef_t, stdout={r.stdout[:500]}"
    # 应有 summary
    assert "Fix Imports Report" in r.stdout
    assert "Not in project" in r.stdout
    print("✅ fix imports: 列出未定义 identifier")


def test_fix_imports_explicit_project_root():
    """--project-root 显式指定"""
    tmpdir, fl, proj = _setup_project_with_missing_typedef()
    r = _run("fix", "imports", "--filelist", fl, "--project-root", proj, "--log-level", "ERROR")
    assert "Project root:" in r.stdout
    assert proj in r.stdout
    print("✅ fix imports --project-root: 显式指定生效")


def test_fix_imports_json_output():
    """fix imports --json 结构"""
    tmpdir, fl, proj = _setup_project_with_missing_typedef()
    r = _run("fix", "imports", "--filelist", fl, "--project-root", proj, "--log-level", "ERROR", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "identifiers" in data
    assert "fixable_count" in data
    assert "unfixable_count" in data
    # 每个 identifier 含 fixable 字段
    for sug in data["identifiers"]:
        assert "identifier" in sug
        assert "fixable" in sug
        assert "found_in" in sug
    print(f"✅ fix imports --json: {len(data['identifiers'])} identifier(s), {data['fixable_count']} fixable")


def test_fix_imports_write_new_filelist():
    """--write 生成新 filelist"""
    tmpdir, fl, proj = _setup_project_with_missing_typedef()
    new_fl = Path(tmpdir) / "test_fixed.f"
    r = _run("fix", "imports", "--filelist", fl, "--project-root", proj, "--write", str(new_fl), "--log-level", "ERROR")
    assert r.returncode == 0
    # 新 filelist 存在
    assert new_fl.exists(), f"新 filelist 应生成: {new_fl}"
    content = new_fl.read_text()
    # 应含原 filelist 内容
    assert "main.sv" in content
    assert "broken.sv" in content
    # 输出应说明
    assert "Wrote" in r.stdout
    assert "Added" in r.stdout
    print(f"✅ fix imports --write: 生成 {new_fl}")


def test_fix_imports_help_documented():
    """fix imports --help 文档化"""
    r = _run("fix", "imports", "--help")
    assert r.returncode == 0
    assert "--filelist" in r.stdout
    assert "--project-root" in r.stdout
    assert "--write" in r.stdout
    assert "--json" in r.stdout
    print("✅ fix imports --help: 文档化")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_extract_definitions_finds_typedef,
        test_scan_project_finds_identifier,
        test_scan_project_returns_none_for_missing,
        test_fix_imports_lists_undefined_identifiers,
        test_fix_imports_explicit_project_root,
        test_fix_imports_json_output,
        test_fix_imports_write_new_filelist,
        test_fix_imports_help_documented,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} fix imports tests passed!")
