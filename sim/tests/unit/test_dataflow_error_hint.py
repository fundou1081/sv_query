"""
TDD: dataflow analyze 错误信息加 hint (Req-11 P1)

[ADD 2026-06-11 Req-11] 修复 Issue 20
现状: 报 'node X is not in the digraph' + Python traceback
建议: 报 'Signal X not found in graph' + 'Hint: hierarchical name' + available signals

测试场景:
1. 裸信号名 (无 module. 前缀) → 提示用 hierarchical name
2. 完全不存在的信号 → 列出 available signals
3. 部分存在 (from 存在 to 不存在) → 错误只提到不存在的
4. 有效 hierarchical name → 正常输出
5. Python traceback 不出现
"""
import subprocess
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")


def _run(*args):
    return subprocess.run(
        ["python3", RUN_CLI_PATH, *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_dataflow_bare_signal_suggests_hierarchical():
    """裸信号名应提示用 hierarchical name"""
    r = _run("dataflow", "analyze", "data_i", "data_o", "-f", "sim/test_simple.sv", "--log-level", "ERROR")
    assert r.returncode == 1
    assert "Signal 'data_i' not found in graph" in r.stderr
    assert "Hint: signal name should be hierarchical" in r.stderr
    assert "top.data_i" in r.stderr  # 具体 hint
    assert "Traceback" not in r.stderr, f"不应有 Python traceback, stderr={r.stderr[:500]}"
    print("✅ dataflow 裸信号名: 提示用 hierarchical name")


def test_dataflow_lists_available_signals():
    """错误信息列出可用信号"""
    r = _run("dataflow", "analyze", "data_i", "data_o", "-f", "sim/test_simple.sv", "--log-level", "ERROR")
    assert r.returncode == 1
    assert "Available signals" in r.stderr
    # 至少包含 top.clk/top.data (test_simple 里有)
    assert "top.clk" in r.stderr
    print("✅ dataflow 错误信息: 列出 available signals")


def test_dataflow_only_first_invalid_signal_reported():
    """from 存在 to 不存在时, 只报 to 不存在"""
    r = _run("dataflow", "analyze", "top.clk", "nonexistent", "-f", "sim/test_simple.sv", "--log-level", "ERROR")
    assert r.returncode == 1
    assert "Signal 'nonexistent' not found" in r.stderr
    # from 是有效信号, 不应报错
    assert "top.clk not found" not in r.stderr
    print("✅ dataflow 部分存在: 只报不存在的")


def test_dataflow_valid_hierarchical_works():
    """有效 hierarchical name 正常工作"""
    r = _run("dataflow", "analyze", "top.clk", "top.dout", "-f", "sim/test_simple.sv", "--log-level", "ERROR")
    assert r.returncode == 0
    assert "Reachable: True" in r.stdout
    print("✅ dataflow valid: 正常输出")


if __name__ == "__main__":
    tests = [
        test_dataflow_bare_signal_suggests_hierarchical,
        test_dataflow_lists_available_signals,
        test_dataflow_only_first_invalid_signal_reported,
        test_dataflow_valid_hierarchical_works,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} dataflow error hint tests passed!")
