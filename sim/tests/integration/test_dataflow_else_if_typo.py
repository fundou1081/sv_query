# ==============================================================================
# test_dataflow_else_if_typo.py
# [ADD 2026-07-04] Regression tests for !! typo bug fix
#
# Bug 根因: visit_conditional_statement 的 else if 累加逻辑错:
# 1. parent_cond 简单加 !, 累加变 !!X (typo)
# 2. 复合条件 (e.g. !sel_a && sel_b) 不 De Morgan 展开
# 3. 复合条件 || 跟 && 混用缺括号
#
# 修法: 加 _de_morgan_negate (正确 De Morgan) + 字符串判断 + 括号保护
# ==============================================================================

import json
import subprocess
from pathlib import Path

import pytest

# 4 个 else if 测试文件
TYPO4_FILE = "/tmp/cdc_test/typo4.sv"
NESTED_NOT2_FILE = "/tmp/cdc_test/nested_not2.sv"
TYPO3_FILE = "/tmp/cdc_test/typo3.sv"
PRJ_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")


def _run_dataflow(fr, to, f):
    r = subprocess.run(
        ["sv_query", "-q", "dataflow", "analyze", fr, to, "--no-strict",
         "--file", f, "--json"],
        capture_output=True, text=True, timeout=30, cwd=PRJ_ROOT,
    )
    return json.loads(r.stdout)


@pytest.mark.parametrize("test_input,fr,to,f,expected_conditions", [
    # 4 个 else if 链 (typo4)
    ("typo4_in_a", "typo4.in_a", "typo4.out_o", TYPO4_FILE, ["sel_a"]),
    ("typo4_in_b", "typo4.in_b", "typo4.out_o", TYPO4_FILE, ["!sel_a && sel_b"]),
    ("typo4_in_c", "typo4.in_c", "typo4.out_o", TYPO4_FILE, ["sel_a && !sel_b && sel_c"]),
    ("typo4_in_d", "typo4.in_d", "typo4.out_o", TYPO4_FILE, ["(!sel_a || sel_b) && !sel_c && sel_d"]),
    # 3 个 else if + negation (nested_not2)
    ("nested_not2_in_b", "nested_not2.in_b", "nested_not2.out_o", NESTED_NOT2_FILE, ["!rst_n && !sel_a"]),
    ("nested_not2_in_c", "nested_not2.in_c", "nested_not2.out_o", NESTED_NOT2_FILE, ["rst_n && sel_a && sel_b"]),
    # 3 个 else if (typo3, 原始 typo 例子)
    ("typo3_in_a", "typo3.in_a", "typo3.out_o", TYPO3_FILE, ["sel_a"]),
    ("typo3_in_b", "typo3.in_b", "typo3.out_o", TYPO3_FILE, ["!sel_a && sel_b"]),
    ("typo3_in_c", "typo3.in_c", "typo3.out_o", TYPO3_FILE, ["sel_a && !sel_b && sel_c"]),
])
def test_else_if_chain_no_double_negation(test_input, fr, to, f, expected_conditions):
    """[REGRESSION] else if 链必须:
    1. 0 个 !! 双重 negation
    2. De Morgan 正确 (复合条件正确展开)
    3. || 跟 && 混用加括号
    """
    d = _run_dataflow(fr, to, f)
    r = d["result"]
    assert r["is_reachable"], f"{test_input}: should be reachable"
    conds = r.get("all_conditions", [])
    assert len(conds) == len(expected_conditions), (
        f"{test_input}: expected {len(expected_conditions)} conditions, got {len(conds)}"
    )
    for actual, expected in zip(conds, expected_conditions):
        assert actual == expected, (
            f"{test_input}: condition mismatch\n"
            f"  actual:   {actual!r}\n"
            f"  expected: {expected!r}"
        )
    # 显式 0 个 !! typo 检查
    for cond in conds:
        assert "!!" not in cond, (
            f"{test_input}: found !! typo in condition: {cond!r}"
        )
    print(f"✅ {test_input}: {conds[0] if conds else '(empty)'}")


def test_else_if_deep_chain_stability():
    """[REGRESSION] 跑 4 个 else if 5 次, 结果必须稳定"""
    results = []
    for _ in range(5):
        d = _run_dataflow("typo4.in_d", "typo4.out_o", TYPO4_FILE)
        results.append(d["result"]["all_conditions"][0])
    # 5 次必须完全一样
    assert all(r == results[0] for r in results), f"5 runs inconsistent: {results}"
    assert "!!" not in results[0]
    print(f"✅ Deep chain stable across 5 runs: {results[0]}")
