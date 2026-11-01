"""[iter_349 / PLAN P48] 条件 L1 化简（原始保留/4-state 安全）。"""
from __future__ import annotations

from cli.core.semantic.condition_analysis import analyze_condition


def test_boolean_identities():
    assert analyze_condition("!(!rst_n) && rd_en")["simplified"] == "rst_n && rd_en"
    assert analyze_condition("a && a")["simplified"] == "a"
    assert analyze_condition("a && (a || b)")["simplified"] == "a"
    assert analyze_condition("a || (a && b)")["simplified"] == "a"
    assert analyze_condition("!!a")["simplified"] == "a"
    assert analyze_condition("a && 1'b1")["simplified"] == "a"
    assert analyze_condition("a || 1'b0")["simplified"] == "a"


def test_complement_is_not_assumed_in_4state():
    r = analyze_condition("a && !a")
    assert r["simplified"] == "a && !a"
    assert r["four_state_safe"] is True
    assert r["unsat"] is False


def test_parse_failure_is_unknown():
    r = analyze_condition("a && (b")
    assert r["method"] == "parse_failed"
    assert r["analysis_incomplete"] is True
    assert r["confidence"] == "unknown"
    assert r["simplified"] == "a && (b"


def test_atoms_with_comparisons_are_preserved():
    r = analyze_condition("(state == 2'd1) && (a != 0)")
    assert r["simplified"] == "state == 2'd1 && a != 0"
    assert r["analysis_incomplete"] is False


def test_syntactic_mutex_and_conflict():
    from cli.core.semantic.condition_analysis import (
        conditions_mutex, driver_conflict_analysis,
    )
    assert conditions_mutex("sel", "!sel")["mutex"] is True
    assert conditions_mutex("sel", "en")["mutex"] is False
    r = driver_conflict_analysis([{"condition": "sel"}, {"condition": "!sel"}])
    assert r["status"] == "proven_exclusive_2state"
    assert r["four_state_safe"] is False
    assert driver_conflict_analysis([{"condition": "sel"}, {"condition": "en"}])["status"] == "possible"
