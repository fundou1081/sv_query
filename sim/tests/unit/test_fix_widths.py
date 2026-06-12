"""
TDD: fix widths CLI 命令 (Req-19)

[ADD 2026-06-12] 用 syntax tree + pyslang.clog2 解析 typedef 真实位宽
回答用户 'macro 展开用语义 AST 不能直接拿到结果吗?':
- 语义 AST 本身不能拿 macro 值 (macro 是 preprocessor 层)
- 但 pyslang 暴露 clog2(SVInt) 跟 SVInt(bits, value, signed)
- 配合 syntax tree, 我们绕过 macro 展开, 直接拿 $clog2(\`MACRO) 的真实位宽

测试场景:
1. 字面 $clog2(常量) → 直接算
2. $clog2(`MACRO) → 解析宏值, 再算
3. macro 解析失败 → 标 unresolved
4. JSON 输出结构
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
        timeout=120,
    )


def _setup_with_clog2_typedefs():
    """建 1 个 SV 含 2 个 $clog2 typedef (1 字面 + 1 宏)"""
    tmpdir = tempfile.mkdtemp()
    sv = Path(tmpdir) / "test.sv"
    sv.write_text("""`timescale 1ns/1ps
`define MY_DEPTH 64

typedef logic [$clog2(8) - 1 : 0] eight_t;
typedef logic [$clog2(`MY_DEPTH) - 1 : 0] deep_t;
""")
    fl = Path(tmpdir) / "test.f"
    fl.write_text(f"{sv.absolute()}\n")
    return tmpdir, str(fl), str(sv)


# ----------------------------------------------------------------------------
# 单元测试
# ----------------------------------------------------------------------------

def test_parse_clog2_literal():
    """_parse_clog2_from_text 应识别字面 $clog2(N)"""
    from cli.commands.fix_widths import _parse_clog2_from_text
    match, value = _parse_clog2_from_text("logic [$clog2(8) - 1 : 0] eight_t;")
    assert match == "$clog2(8)"
    assert value == 8
    print("✅ _parse_clog2_from_text: 识别字面 $clog2(N)")


def test_parse_clog2_macro():
    """_parse_clog2_from_text 应识别 $clog2(`MACRO)"""
    from cli.commands.fix_widths import _parse_clog2_from_text
    match, value = _parse_clog2_from_text("logic [$clog2(`MY_DEPTH) - 1 : 0] deep_t;")
    assert match == "$clog2(`MY_DEPTH)"
    assert value == "MY_DEPTH"
    print("✅ _parse_clog2_from_text: 识别 $clog2(`MACRO)")


def test_resolve_macro_value_literal():
    """_resolve_macro_value 解析字面宏值"""
    from cli.commands.fix_widths import _resolve_macro_value
    sources = {"a.sv": "`define MY_DEPTH 64\n"}
    assert _resolve_macro_value("MY_DEPTH", sources) == 64
    print("✅ _resolve_macro_value: 字面宏值")


def test_resolve_macro_value_indirect():
    """_resolve_macro_value 递归解析嵌套宏"""
    from cli.commands.fix_widths import _resolve_macro_value
    sources = {"a.sv": "`define USER_MY_DEPTH 8\n`define MY_DEPTH `USER_MY_DEPTH\n"}
    assert _resolve_macro_value("MY_DEPTH", sources) == 8
    print("✅ _resolve_macro_value: 嵌套宏 (DCACHE_WAY→USER_DCACHE_WAY→4)")


def test_resolve_macro_value_undefined():
    """_resolve_macro_value 找不到返回 None"""
    from cli.commands.fix_widths import _resolve_macro_value
    sources = {"a.sv": "`define OTHER 5\n"}
    assert _resolve_macro_value("MY_UNKNOWN", sources) is None
    print("✅ _resolve_macro_value: 找不到返回 None")


def test_evaluate_clog2_pyslang():
    """_evaluate_clog2 用 pyslang.clog2 算真实位宽"""
    from cli.commands.fix_widths import _evaluate_clog2
    # 字面常量
    assert _evaluate_clog2(4, {}) == 2  # clog2(4)=2
    assert _evaluate_clog2(8, {}) == 3
    assert _evaluate_clog2(64, {}) == 6
    # macro 名 (sources 没定义, 应 None)
    assert _evaluate_clog2("UNDEFINED", {}) is None
    # macro 名 (sources 有定义)
    assert _evaluate_clog2("MY", {"a.sv": "`define MY 128\n"}) == 7  # clog2(128)=7
    print("✅ _evaluate_clog2: 用 pyslang.clog2 算真实位宽")


# ----------------------------------------------------------------------------
# CLI 集成测试
# ----------------------------------------------------------------------------

def test_fix_widths_resolves_literal_and_macro():
    """fix widths 应解析字面 $clog2(8) → 3, $clog2(`MY_DEPTH) → 6 (因 MY_DEPTH=64)"""
    tmpdir, fl, sv = _setup_with_clog2_typedefs()
    r = _run("fix", "widths", "--filelist", fl, "--log-level", "ERROR")
    assert r.returncode == 0, f"stderr={r.stderr[:300]}"
    # 2 个 typedef, 都应解析
    assert "clog2 = 3" in r.stdout, f"应含 $clog2(8)=3, stdout={r.stdout[:500]}"  # 8→3
    assert "clog2 = 6" in r.stdout, f"应含 $clog2(64)=6, stdout={r.stdout[:500]}"  # 64→6
    assert "13/13" not in r.stdout, "不应是 NaplesPU 数字"  # 我们只测小项目
    print("✅ fix widths: 字面 + macro 都能解析")


def test_fix_widths_json_structure():
    """fix widths --json 结构"""
    tmpdir, fl, sv = _setup_with_clog2_typedefs()
    r = _run("fix", "widths", "--filelist", fl, "--log-level", "ERROR", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "total_typedefs" in data
    assert "with_clog2" in data
    assert "resolved" in data
    assert "results" in data
    for r_item in data["results"]:
        assert "call" in r_item
        assert "value_or_macro" in r_item
        assert "clog2" in r_item
    print(f"✅ fix widths --json: {data['with_clog2']} typedefs, {data['resolved']} resolved")


def test_fix_widths_help_documented():
    """fix widths --help 文档化"""
    r = _run("fix", "widths", "--help")
    assert r.returncode == 0
    assert "--filelist" in r.stdout
    assert "--json" in r.stdout
    print("✅ fix widths --help: 文档化")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_parse_clog2_literal,
        test_parse_clog2_macro,
        test_resolve_macro_value_literal,
        test_resolve_macro_value_indirect,
        test_resolve_macro_value_undefined,
        test_evaluate_clog2_pyslang,
        test_fix_widths_resolves_literal_and_macro,
        test_fix_widths_json_structure,
        test_fix_widths_help_documented,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} fix widths tests passed!")
