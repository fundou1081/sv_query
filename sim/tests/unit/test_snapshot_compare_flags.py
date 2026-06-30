"""
TDD: snapshot compare 加 --top/--show-edges/--pretty flag (Req-17)

[ADD 2026-06-12] B 改进: snapshot compare 输出更详细
- --top N: 控制 added/removed nodes/edges 显示数量
- --show-edges: 列出 added/removed edges 的具体内容 (e.g. 'top.clk → top.dout')
- --pretty: JSON 格式化 (indent=2)

测试场景:
1. --top N: 控制节点显示
2. --show-edges: 列出具体 edge
3. --pretty: JSON 格式化
4. default: 跟之前兼容
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


def _run(*args):
    return subprocess.run(
        ["python3", RUN_CLI_PATH, *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _setup_two_sv():
    """建 v1/v2 两个 SV, 触发 added nodes/edges"""
    tmpdir = tempfile.mkdtemp()
    v1 = Path(tmpdir) / "v1.sv"
    v1.write_text("""module top (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] din,
    output reg  [7:0] dout
);
    always_ff @(posedge clk) dout <= din;
endmodule
""")
    v2 = Path(tmpdir) / "v2.sv"
    v2.write_text("""module top (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] din,
    input  wire en,
    output reg  [7:0] dout
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) dout <= 0;
        else if (en) dout <= din;
    end
endmodule
""")
    return tmpdir, str(v1), str(v2)


def _save_snapshot(path, tag):
    """用唯一 tag 存 snapshot, 避免冲突"""
    r = _run("snapshot", "save", path, "--tag", tag)
    return r


# ----------------------------------------------------------------------------
# 主测试
# ----------------------------------------------------------------------------

def test_snapshot_compare_top_flag():
    """--top N 控制 added nodes 显示数量"""
    tmpdir, v1, v2 = _setup_two_sv()
    tag1 = f"top_test_v1_{os.path.basename(tmpdir)}"
    tag2 = f"top_test_v2_{os.path.basename(tmpdir)}"
    _save_snapshot(v1, tag1)
    _save_snapshot(v2, tag2)
    r = _run("snapshot", "compare", tag1, tag2, "--top", "1")
    assert r.returncode == 0, f"应 exit 0, got {r.returncode}, stderr={r.stderr[:300]}"
    # Added nodes (2) 但只显示 1: 应有 "more" 标注
    assert "Added nodes" in r.stdout
    assert "more" in r.stdout, f"应有 '(N more)' 标注, stdout={r.stdout[:500]}"
    print("✅ --top 1: added nodes 限制显示, 标注 more")


def test_snapshot_compare_show_edges():
    """--show-edges 列出 added edges 的具体内容"""
    tmpdir, v1, v2 = _setup_two_sv()
    tag1 = f"show_edges_v1_{os.path.basename(tmpdir)}"
    tag2 = f"show_edges_v2_{os.path.basename(tmpdir)}"
    _save_snapshot(v1, tag1)
    _save_snapshot(v2, tag2)
    r = _run("snapshot", "compare", tag1, tag2, "--show-edges")
    assert r.returncode == 0
    # 应有 + 0 → top.dout 格式
    assert "→" in r.stdout, f"应含箭头格式, stdout={r.stdout[:500]}"
    assert "+" in r.stdout, f"应有 + 前缀, stdout={r.stdout[:500]}"
    print("✅ --show-edges: 显示具体 edge 变化")


def test_snapshot_compare_pretty():
    """--pretty JSON 格式化 (indent=2)"""
    tmpdir, v1, v2 = _setup_two_sv()
    tag1 = f"pretty_v1_{os.path.basename(tmpdir)}"
    tag2 = f"pretty_v2_{os.path.basename(tmpdir)}"
    _save_snapshot(v1, tag1)
    _save_snapshot(v2, tag2)
    r_pretty = _run("snapshot", "compare", tag1, tag2, "--json", "--pretty")
    r_normal = _run("snapshot", "compare", tag1, tag2, "--json")
    # pretty 应有换行 + 缩进
    assert "\n" in r_pretty.stdout
    assert "  " in r_pretty.stdout, "应含缩进空格"
    # pretty 应能正常解析 JSON
    data_pretty = json.loads(r_pretty.stdout)
    data_normal = json.loads(r_normal.stdout)
    # 内容应一致
    assert data_pretty == data_normal, "pretty / normal 输出不一致"
    print("✅ --pretty: JSON 格式化, 内容一致")


def test_snapshot_compare_default_backward_compat():
    """默认 (不传新 flag) 行为兼容 (top=10, 不显示 edges)"""
    tmpdir, v1, v2 = _setup_two_sv()
    tag1 = f"compat_v1_{os.path.basename(tmpdir)}"
    tag2 = f"compat_v2_{os.path.basename(tmpdir)}"
    _save_snapshot(v1, tag1)
    _save_snapshot(v2, tag2)
    r = _run("snapshot", "compare", tag1, tag2)
    assert r.returncode == 0
    # 默认不显示 '→' 箭头
    assert "→" not in r.stdout, f"默认不应显示 edges 详情, stdout={r.stdout[:500]}"
    # 但应有 Added edges 计数
    assert "Added edges" in r.stdout
    print("✅ default: 跟之前兼容 (top=10, 不显示 edges)")


def test_snapshot_compare_help_documented():
    """snapshot compare --help 文档化新 flag"""
    r = _run("snapshot", "compare", "--help")
    assert r.returncode == 0
    assert "--top" in r.stdout
    assert "--show-edges" in r.stdout
    assert "--pretty" in r.stdout
    print("✅ snapshot compare --help: 文档化新 flag")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_snapshot_compare_top_flag,
        test_snapshot_compare_show_edges,
        test_snapshot_compare_pretty,
        test_snapshot_compare_default_backward_compat,
        test_snapshot_compare_help_documented,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} snapshot compare flag tests passed!")
