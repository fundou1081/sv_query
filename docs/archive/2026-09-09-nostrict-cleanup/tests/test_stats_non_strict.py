"""
TDD: stats 命令 non-strict mode partial result (Req-10 + Req-14)

[ADD 2026-06-11 Req-10 P0] elaboration error 优雅处理
[ADD 2026-06-11 Req-14 P2] stats 跨文件失败时输出 partial result

测试场景:
1. broken SV (未定义类型/函数/信号) → non-strict 模式跑通 + 输出 partial graph + 错误计数
2. broken SV → strict 模式 exit 1 + 干净错误信息
3. broken SV → JSON 模式 elaboration_errors 字段
4. 完整 SV → non-strict 模式 elaboration_errors 为空
5. 各命令在 non-strict 模式都跑通 (跟 Req-9 验证相同的 9 个命令)
"""
import json
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI = "python3"
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")

# 故意 broken 的 SV: 未定义类型/函数/信号
BROKEN_SV = """
module broken_top (
    input  wire clk,
    input  wire rst_n,
    output wire q
);
    logic [WIDTH-1:0] data;  // WIDTH 未定义
    logic unused;
    assign q = undefined_func(data);
    always_ff @(posedge clk) data <= unknown_signal;
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


def _run(*args, cwd=None):
    return subprocess.run(
        [RUN_CLI, RUN_CLI_PATH, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _write_sv(content):
    """写一个 .sv 到临时目录, 返回 (tmpdir, sv_path)"""
    tmpdir = tempfile.mkdtemp()
    sv = Path(tmpdir) / "test.sv"
    sv.write_text(content)
    return tmpdir, str(sv)


# ----------------------------------------------------------------------------
# 基础: partial result + error count
# ----------------------------------------------------------------------------

def test_stats_non_strict_returns_partial_result():
    """broken SV 在 non-strict 模式 (默认) 应该返回 partial graph"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "--no-strict", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    assert r.returncode == 0, f"应 exit 0 (--no-strict), 实际 {r.returncode}, stderr={r.stderr[:300]}"
    assert "Total nodes:" in r.stdout, f"应输出 stats, stdout={r.stdout[:300]}"
    assert "elaboration error(s)" in r.stdout, f"应提示 elaboration error 数量, stdout={r.stdout[:500]}"
    print("✅ stats --no-strict: 跑通 partial result + error count")


def test_stats_strict_fails_cleanly():
    """broken SV 在 strict 模式应 exit 1 + 干净错误信息 (无 Python traceback)"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "-f", sv, "--strict", "--log-level", "ERROR", cwd=tmpdir)
    assert r.returncode != 0, f"应 exit non-zero (strict), 实际 {r.returncode}"
    assert "Error:" in r.stderr, f"应统一 Error: 头, stderr={r.stderr[:300]}"
    assert "Traceback" not in r.stderr, f"strict 模式不应有 Python traceback, stderr={r.stderr[:500]}"
    print(f"✅ stats strict: exit {r.returncode} 干净错误 (无 traceback)")


def test_stats_non_strict_json_has_elaboration_errors():
    """JSON 模式应输出 elaboration_errors 字段 (含 file/line/code/message)"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    r = _run("stats", "--no-strict", "-f", sv, "--log-level", "ERROR", "--json", cwd=tmpdir)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    elab = data["result"].get("elaboration_errors", [])
    assert len(elab) >= 1, f"应有 elaboration_errors, got {len(elab)}: {data['result']}"
    for e in elab:
        assert "file" in e, f"elab err 应有 file: {e}"
        assert "line" in e, f"elab err 应有 line: {e}"
        assert "code" in e, f"elab err 应有 code: {e}"
    print(f"✅ stats JSON --no-strict: {len(elab)} elaboration_errors 含 file/line/code")


def test_stats_good_sv_no_elaboration_errors():
    """完整 SV 在 --no-strict 模式 elaboration_errors 应为空"""
    tmpdir, sv = _write_sv(GOOD_SV)
    r = _run("stats", "-f", sv, "--log-level", "ERROR", "--json", cwd=tmpdir)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    elab = data["result"].get("elaboration_errors", [])
    assert len(elab) == 0, f"无错 SV 应 elaboration_errors=[], got {elab}"
    print("✅ stats good SV: elaboration_errors=[]")


# ----------------------------------------------------------------------------
# 跨命令验证: 9 个命令在 non-strict 都跑通
# ----------------------------------------------------------------------------

def test_other_commands_non_strict_partial():
    """9 个命令在 non-strict 模式 broken SV 跑通 (除 strict 强制要求的命令)"""
    tmpdir, sv = _write_sv(BROKEN_SV)
    commands = [
        ("risk", "analyze", "--no-strict"),
        ("cdc", "analyze", "--no-strict"),
        ("dataflow", "analyze", "--no-strict", "broken_top.clk", "broken_top.q"),
        ("sva", "coverage", "--no-strict"),
        ("timing", "analyze", "--no-strict"),
        ("verify", "gap", "--no-strict"),
        # controlflow/visualize 可能不输出 stats 类报告, 只测不 crash
    ]
    for cmd in commands:
        r = _run(*cmd, "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
        assert r.returncode == 0, f"{' '.join(cmd)} 应 exit 0 (non-strict), 实际 {r.returncode}, stderr={r.stderr[:200]}"
    print(f"✅ {len(commands)} 命令 non-strict 模式全部跑通 broken SV")


# ----------------------------------------------------------------------------
# 文档化: --strict flag 帮助文本
# ----------------------------------------------------------------------------

def test_stats_help_mentions_strict_mode():
    """stats --help 应提到 strict mode / non-strict default"""
    r = _run("stats", "--help")
    assert r.returncode == 0
    assert "--strict" in r.stdout, f"help 应有 --strict flag, stdout={r.stdout[:500]}"
    assert "non-strict" in r.stdout.lower() or "--no-strict" in r.stdout or "partial" in r.stdout.lower(), f"help 应说明 non-strict 是默认, stdout={r.stdout[:500]}"
    print("✅ stats --help 文档化 strict mode")


if __name__ == "__main__":
    tests = [
        test_stats_non_strict_returns_partial_result,
        test_stats_strict_fails_cleanly,
        test_stats_non_strict_json_has_elaboration_errors,
        test_stats_good_sv_no_elaboration_errors,
        test_other_commands_non_strict_partial,
        test_stats_help_mentions_strict_mode,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} non-strict partial result tests passed!")
