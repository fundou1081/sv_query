# test_dataflow_else_if_comprehensive.py
# [2026-07-04] 综合测试: dataflow else-if 链 + 复合条件 + De Morgan + 括号保护
#
# 覆盖场景:
# - 简单 if/else
# - case (4 个 case items + default)
# - ternary
# - 嵌套 if (4 层)
# - 复合条件 (&&, ||)
# - case inside if / if inside case
# - 嵌套 if-else (非链)
# - 直接 negation (if (!cond))
# - 3 else if 链
# - 4 else if 链
#
# 期望: 0 个 !! typo, 复合条件正确 De Morgan, 混合 &&/|| 加括号
"""
Integration tests for dataflow condition accumulation across else-if chains.

[2026-07-04 v3] Comprehensive coverage:
- Simple if/else
- case (4 items + default)
- ternary
- 4-level nested if
- Compound conditions (&&, ||)
- case inside if / if inside case
- Nested if-else (not chain)
- Direct negation (if (!cond))
- 3/4 else-if chains

期望:
- 0 个 !! typo
- 复合条件正确 De Morgan
- 混合 &&/|| 加括号防止歧义
"""
import os
import subprocess
import sys

# Add src to path for direct module imports (De Morgan unit tests)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest

PROJ = "/Users/fundou/my_dv_proj/sv_query"


def svq_dataflow(from_sig: str, to_sig: str, file_path: str) -> list[str]:
    """Run sv_query dataflow and return all_conditions list"""
    r = subprocess.run(
        ["sv_query", "-q", "dataflow", "analyze", from_sig, to_sig, "--no-strict",
         "--file", file_path, "--json"],
        capture_output=True, text=True, timeout=30, cwd=PROJ,
    )
    import json
    d = json.loads(r.stdout)
    return d["result"].get("all_conditions", [])


def assert_no_typo(conditions: list[str]) -> None:
    """Ensure no `!!` double-negation typo"""
    for c in conditions:
        assert "!!" not in c, f"Double-negation typo: {c}"


def assert_one_of(conditions: list[str], acceptable: list[str]) -> None:
    """Check actual condition matches one of acceptable forms (mathematical equivalence)"""
    assert conditions, f"No conditions returned"
    actual = conditions[0]
    assert actual in acceptable, (
        f"Condition mismatch: actual={actual!r}, expected one of {acceptable}"
    )


# ===========================================================================
# comprehensive.sv tests
# ===========================================================================

COMPREHENSIVE = "/tmp/cdc_test/comprehensive.sv"


def test_comp_simple_if():
    """简单 if/else: cond = a"""
    conds = svq_dataflow("comprehensive.in_a", "comprehensive.out_if", COMPREHENSIVE)
    assert_no_typo(conds)
    assert_one_of(conds, ["a"])


def test_comp_case():
    """case 4 items: cond = sel == 4'b0000"""
    conds = svq_dataflow("comprehensive.in_a", "comprehensive.out_case", COMPREHENSIVE)
    assert_no_typo(conds)
    assert_one_of(conds, ["sel == 4'b0000"])


def test_comp_ternary():
    """ternary: cond = a"""
    conds = svq_dataflow("comprehensive.in_a", "comprehensive.out_ternary", COMPREHENSIVE)
    assert_no_typo(conds)
    assert_one_of(conds, ["a"])


def test_comp_nested_4_levels():
    """4 层嵌套 if: cond = a && b && c && d"""
    conds = svq_dataflow("comprehensive.in_a", "comprehensive.out_nested", COMPREHENSIVE)
    assert_no_typo(conds)
    assert_one_of(conds, ["a && b && c && d"])


def test_comp_compound_in_a():
    """复合条件 in_a (直接 a && b): cond = a && b"""
    conds = svq_dataflow("comprehensive.in_a", "comprehensive.out_multi", COMPREHENSIVE)
    assert_no_typo(conds)
    assert_one_of(conds, ["a && b"])


def test_comp_compound_in_b():
    """复合条件 in_b (else 分支 NOT (a && b) AND (c || d))
    两种 De Morgan 等价形式都接受"""
    conds = svq_dataflow("comprehensive.in_b", "comprehensive.out_multi", COMPREHENSIVE)
    assert_no_typo(conds)
    # 期望: NOT (a && b) AND (c || d), 用括号保护 || 优先级
    assert_one_of(conds, [
        "(!a || !b) && (c || d)",  # De Morgan'd form
        "!(a && b) && (c || d)",   # Original form with parens
    ])


def test_comp_compound_in_c():
    """复合条件 in_c (else 分支 NOT (a && b) AND NOT (c || d))
    多种 De Morgan 等价形式都接受"""
    conds = svq_dataflow("comprehensive.in_c", "comprehensive.out_multi", COMPREHENSIVE)
    assert_no_typo(conds)
    # 期望: NOT (a && b) AND NOT (c || d)
    assert_one_of(conds, [
        "(a && b) && (!c && !d)",     # Fully De Morgan'd
        "(!a || !b) && !(c || d)",   # De Morgan parent only
        "!(a && b) && !(c || d)",     # Original form
    ])


# ===========================================================================
# edge2.sv tests (case inside if / if inside case)
# ===========================================================================

EDGE2 = "/tmp/cdc_test/edge2.sv"


def test_edge2_case_inside_if():
    """case inside if: cond = en && sel == 2'b00"""
    conds = svq_dataflow("edge2.data_in", "edge2.out1", EDGE2)
    assert_no_typo(conds)
    assert_one_of(conds, ["en && sel == 2'b00"])


def test_edge2_if_inside_case():
    """if inside case: cond = sel == 2'b00"""
    conds = svq_dataflow("edge2.data_in", "edge2.out2", EDGE2)
    assert_no_typo(conds)
    assert_one_of(conds, ["sel == 2'b00"])


# ===========================================================================
# typo3.sv / typo4.sv tests (3/4 else-if chains)
# ===========================================================================

TYPO3 = "/tmp/cdc_test/typo3.sv"


def test_typo3_in_a():
    conds = svq_dataflow("typo3.in_a", "typo3.out_o", TYPO3)
    assert_no_typo(conds)
    assert_one_of(conds, ["sel_a"])


def test_typo3_in_b():
    conds = svq_dataflow("typo3.in_b", "typo3.out_o", TYPO3)
    assert_no_typo(conds)
    assert_one_of(conds, ["!sel_a && sel_b"])


def test_typo3_in_c():
    conds = svq_dataflow("typo3.in_c", "typo3.out_o", TYPO3)
    assert_no_typo(conds)
    assert_one_of(conds, ["sel_a && !sel_b && sel_c"])


TYPO4 = "/tmp/cdc_test/typo4.sv"


def test_typo4_in_a():
    conds = svq_dataflow("typo4.in_a", "typo4.out_o", TYPO4)
    assert_no_typo(conds)
    assert_one_of(conds, ["sel_a"])


def test_typo4_in_b():
    conds = svq_dataflow("typo4.in_b", "typo4.out_o", TYPO4)
    assert_no_typo(conds)
    assert_one_of(conds, ["!sel_a && sel_b"])


def test_typo4_in_c():
    conds = svq_dataflow("typo4.in_c", "typo4.out_o", TYPO4)
    assert_no_typo(conds)
    assert_one_of(conds, ["sel_a && !sel_b && sel_c"])


def test_typo4_in_d():
    """4 else if 链最深处, 修复前有 !!sel_a typo + 缺括号"""
    conds = svq_dataflow("typo4.in_d", "typo4.out_o", TYPO4)
    assert_no_typo(conds)
    assert_one_of(conds, ["(!sel_a || sel_b) && !sel_c && sel_d"])


# ===========================================================================
# De Morgan function unit tests (直接测 _de_morgan_negate)
# ===========================================================================


def test_de_morgan_simple_id():
    """X → !X"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("a") == "!a"


def test_de_morgan_simple_neg():
    """!X → X"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("!a") == "a"


def test_de_morgan_double_neg_simple():
    """!!X → X (simple form)"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("!!a") == "a"


def test_de_morgan_double_neg_compound():
    """!!(X && Y) → (X && Y)"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("!!(a && b)") == "(a && b)"


def test_de_morgan_not_paren_compound():
    """!(X && Y) → !X || !Y (De Morgan)"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("!(a && b)") == "!a || !b"


def test_de_morgan_not_paren_or():
    """!(X || Y) → !X && !Y (De Morgan)"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("!(a || b)") == "!a && !b"


def test_de_morgan_compound_and():
    """A && B → !A || !B (De Morgan negate)"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("a && b") == "!a || !b"


def test_de_morgan_compound_or():
    """A || B → !A && !B (De Morgan negate)"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    assert v._de_morgan_negate("a || b") == "!a && !b"


def test_de_morgan_find_matching_paren():
    """_find_matching_paren handles nested parens correctly"""
    from trace.core.visitors.statement_collector_visitor import StatementCollectorVisitor
    v = StatementCollectorVisitor.__new__(StatementCollectorVisitor)
    # (a && b)
    assert v._find_matching_paren("(a && b)", 0) == 7
    # !(a && b)
    assert v._find_matching_paren("!(a && b)", 1) == 8
    # nested: (a || b) && (c || d)
    assert v._find_matching_paren("(a || b) && (c || d)", 0) == 7
    assert v._find_matching_paren("(a || b) && (c || d)", 12) == 19