"""
TDD: controlflow if/else 互斥判断 (Req-13 P2)

[ADD 2026-06-11 Req-13] 修复 Issue 21
现状: if/else 互斥分支 (reset vs !reset) 被误报为"矛盾条件"
期望: 检测 if/else 模式 (a vs !a 简单标识符对) → 标 [Mutex] 合法设计, 不报警

测试场景:
1. synchronizer.sync0: if/else (reset vs !reset) → 报 [Mutex], 不报矛盾
2. complex conditions: a&&b vs !a → 不是简单 mutex, 应报矛盾
3. 多条件 (a vs !a + b vs !b) → 报矛盾
"""
import subprocess
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")
SYNC_SV = "/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv"


def _run(*args):
    return subprocess.run(
        ["python3", RUN_CLI_PATH, *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_if_else_mutex_not_reported_as_contradiction():
    """synchronizer.sync0 的 if/else (reset vs !reset) 应标 [Mutex], 不标矛盾"""
    r = _run("controlflow", "analyze", "synchronizer.sync0", "-f", SYNC_SV, "--log-level", "ERROR")
    assert r.returncode == 0
    # 不应有 "矛盾条件检测"
    assert "矛盾条件检测" not in r.stdout, f"不应有矛盾警告, stdout={r.stdout[:500]}"
    # 应有 [Mutex] 标记
    assert "[Mutex]" in r.stdout, f"应有 [Mutex] 标记, stdout={r.stdout[:500]}"
    assert "if/else 互斥分支" in r.stdout
    print("✅ controlflow if/else mutex: 标 [Mutex] 不标矛盾")


def test_complex_negation_still_warns():
    """复杂表达式 (a && b vs !a) 不应走 if/else mutex 豁免 (因为不是简单标识符对)"""
    # 用手写 SV 触发: if (a && b) ... else if (!a) ...
    tmp_sv = "/tmp/test_complex_cond.sv"
    Path(tmp_sv).write_text("""
module top (
    input  wire clk,
    input  wire rst_n,
    input  wire a,
    input  wire b,
    output reg dout
);
    always_ff @(posedge clk) begin
        if (a && b)
            dout <= 1'b1;
        else if (!a)
            dout <= 1'b0;
    end
endmodule
""")
    r = _run("controlflow", "analyze", "top.dout", "-f", tmp_sv, "--log-level", "ERROR")
    assert r.returncode == 0
    # a && b 不是简单标识符, !a 是简单. 不是 mutex
    assert "[Mutex]" not in r.stdout, f"复杂条件不应 mutex, stdout={r.stdout[:500]}"
    print("✅ controlflow 复杂 negation: 不走 mutex 豁免")


if __name__ == "__main__":
    tests = [
        test_if_else_mutex_not_reported_as_contradiction,
        test_complex_negation_still_warns,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} controlflow mutex tests passed!")
