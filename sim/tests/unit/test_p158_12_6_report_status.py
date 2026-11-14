"""test_p158_12_6_report_status.py — [P158.12.6 / R-028] 绿色口径统一

锁定 (REVIEW_2026-11-11 §5.5):
  A. 7 类状态必须全部显式分类, 不得把未执行/未知揉进 passed 或 n;
  B. `0 failed` 不构成全绿 (canonical 131 deselected + opensource 17 skip
     都是未执行单元);
  C. false_confident 分母 = answered_n (实际作答数) — 当前默认口径
     (待方豆确认), 未执行/未知不稀释分母;
  D. render 必须打印 7 类 + 明确 VERDICT, 不允许只报 "0 failed";
  E. score_long_range.summary 暴露 statuses + 新分母 (回归咬合)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOOLS = str(PROJECT_ROOT / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from report_status import (  # noqa: E402
    STATUSES, classify_pytest_counts, classify_task, empty_status,
    is_fully_green, render_report, summarize,
)


class TestSevenStatuses:
    def test_all_seven_statuses_classified(self):
        rows = [
            {"parsed": True, "answer": {"path": "a"}, "exact": True},           # passed
            {"parsed": True, "answer": {"path": "b"}, "exact": False,
             "confidence": "high"},                                            # failed
            {"parsed": False, "answer": None},                                   # unknown
            {"parsed": True, "answer": {}, "timeout": True},                     # truncated
            {"task_error": True, "rc": 130},                                     # unexecuted
            {"skipped": True, "skip_reason": "retired exp"},                     # skipped
            {"external_missing": True},                                          # external
        ]
        got = {classify_task(r) for r in rows}
        assert got == set(STATUSES), f"7 类未全覆盖: {set(STATUSES) - got}"

    def test_pytest_counts_expand_to_seven(self):
        st = classify_pytest_counts(
            {"passed": 2710, "failed": 0, "skipped": 0, "deselected": 131})
        assert st["passed"] == 2710
        assert st["unexecuted"] == 0
        assert st["deferred"] == 131
        assert st["failed"] == 0
        assert sum(st[s] for s in STATUSES) == 2710


class TestZeroFailedIsNotGreen:
    def test_canonical_alone_not_green(self):
        st = classify_pytest_counts(
            {"passed": 2710, "failed": 0, "skipped": 0, "deselected": 131})
        assert not is_fully_green(st), "131 unexecuted 不得冒充全绿"

    def test_two_runs_report_not_green_and_visible(self):
        report = {"runs": [
            {"name": "canonical", "passed": 2710, "failed": 0,
             "skipped": 0, "deselected": 131},
            {"name": "opensource", "passed": 114, "failed": 0,
             "skipped": 9, "deselected": 0},
        ]}
        text = render_report(report)
        assert "run=canonical" in text and "run=opensource" in text
        assert "deferred=131" in text and "skipped_with_reason=9" in text
        assert "unexecuted=0" in text
        assert "NOT fully green" in text
        assert "只看 failed 数不代表全绿" in text
        assert all(s in text for s in STATUSES), "7 类字段必须全打印"

    def test_truly_green(self):
        st = empty_status()
        st["passed"] = 10
        assert is_fully_green(st)


class TestDenominatorSemantics:
    def test_unexecuted_does_not_dilute_false_confident_rate(self):
        rows = [
            {"parsed": True, "answer": {"x": 1}, "exact": True},
            {"parsed": True, "answer": {"x": 2}, "exact": False,
             "confidence": "high"},
            {"parsed": False, "answer": None},        # unknown
            {"task_error": True, "rc": 130},          # unexecuted
            {"external_missing": True},               # external not run
        ]
        s = summarize(rows)
        assert s["answered_n"] == 2, "分母只算实际作答"
        assert s["false_confident"] == 1
        assert s["false_confident_rate"] == 0.5
        assert s["unknown"] == 1 and s["unexecuted"] == 1
        assert s["external_not_run"] == 1
        assert s["total"] == 5

    def test_no_answers_rate_is_none_not_zero(self):
        s = summarize([{"parsed": False, "answer": None}])
        assert s["answered_n"] == 0
        assert s["false_confident_rate"] is None, "无作答时不得伪造 0% 风险"


class TestScoreLongRangeIntegration:
    def test_summary_exposes_statuses_and_denominator(self):
        sys.path.insert(0, str(PROJECT_ROOT / "tools" / "benchmark"))
        from score_long_range import score
        data = {
            "tasks": [{"id": "t1"}, {"id": "t2"}],
            "results": [
                {"task_id": "t1", "model": "m", "arm": "a",
                 "answer": {"path": "x"}, "duration_ms": 1000,
                 "parsed": True, "confidence": "high"},
                {"task_id": "t2", "model": "m", "arm": "a",
                 "answer": None, "duration_ms": 1000,
                 "parsed": False, "confidence": "low"},
            ],
        }
        summary = score(data)["summary"]["m / a"]
        assert "statuses" in summary
        assert summary["statuses"]["unknown"] == 1
        assert summary["false_confident_denominator"] == 1
        assert summary["n"] == 2
