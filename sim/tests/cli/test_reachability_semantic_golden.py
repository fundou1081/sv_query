#==============================================================================
# test_reachability_semantic_golden.py - Golden standard for reachability (TDD)
#==============================================================================
"""
[Phase 3 Day 4 2026-07-07] Golden standard test for `randomize reachability`
semantic compliance (鉄律1 + 鉄律7 + 鉄律28).

This is the TDD golden test (鉄律7): fixed fixture + expected results.

KEY REQUIREMENT: Reachability must NOT use text-based grep on source code
(违反鉄律1 - 严禁将源码转为字符串后用正则分析). Must use semantic AST
(pyslang visitor pattern) instead.

These tests verify the IMPLEMENTATION correctly distinguishes between:
  ✓ Real consumer (req.used_real = ...) — code reference
  ✗ Comment reference (// only_in_comment ...) — text comment
  ✗ String literal ($display("only_in_string...")) — string output

If the implementation is text-grep based, these tests will FAIL because
it will mark 'only_in_comment' / 'only_in_string' / 'unused_real' as ALIVE.
"""

import unittest
import subprocess
import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "randomize" / "text_grep_bugs.sv"


def _run_svq(args):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
    )


def _get_status(fixture, class_name):
    """Run reachability --json, return dict of var_name -> status."""
    result = _run_svq([
        "randomize", "reachability",
        "-f", str(fixture),
        "--class", class_name,
        "--json",
    ])
    if result.returncode != 0:
        raise AssertionError(f"reachability failed: {result.stderr}")
    return json.loads(result.stdout)


# =============================================================================
# Golden Standard (鉄律7: 新功能必须先有边界测试)
# =============================================================================

class TestReachabilitySemanticGolden(unittest.TestCase):
    """Golden standard: reachability must distinguish code vs comment vs string."""

    def test_only_in_comment_is_dead(self):
        """[金标准] 只在 comment 提到的 rand var 应该 DEAD"""
        data = _get_status(FIXTURE_PATH, "packet")
        var = data["rand_vars"][next(
            i for i, v in enumerate(data["rand_vars"])
            if v["name"] == "only_in_comment"
        )]
        self.assertEqual(
            var["status"], "dead",
            f"only_in_comment is ONLY in a comment, must be dead, got: {var['status']}"
        )
        self.assertEqual(
            var["consumed_count"], 0,
            f"only_in_comment must have 0 consumers, got: {var['consumed_count']}"
        )

    def test_only_in_string_is_dead(self):
        """[金标准] 只在 string literal 提到的 rand var 应该 DEAD"""
        data = _get_status(FIXTURE_PATH, "packet")
        var = data["rand_vars"][next(
            i for i, v in enumerate(data["rand_vars"])
            if v["name"] == "only_in_string"
        )]
        self.assertEqual(
            var["status"], "dead",
            f"only_in_string is ONLY in $display string, must be dead, got: {var['status']}"
        )
        self.assertEqual(
            var["consumed_count"], 0,
            f"only_in_string must have 0 consumers, got: {var['consumed_count']}"
        )

    def test_unused_real_is_dead(self):
        """[金标准] 只在 $display() argument 提到的 rand var 应该 DEAD

        $display 是 system task, value 被打印后丢弃, 不算 real consumer.
        Reachability 是验证语意分析, 只看 assignment/load 影响 logic flow.
        """
        data = _get_status(FIXTURE_PATH, "packet")
        var = data["rand_vars"][next(
            i for i, v in enumerate(data["rand_vars"])
            if v["name"] == "unused_real"
        )]
        # 决定: $display("only_in_string = %h", req.unused_real)
        # `req.unused_real` 是 argument to system task, 不是 logic consumer
        # 所以应该 DEAD (跟 only_in_comment / only_in_string 一致)
        self.assertEqual(
            var["status"], "dead",
            f"unused_real is ONLY in $display arg, must be dead, got: {var['status']}"
        )
        self.assertEqual(
            var["consumed_count"], 0,
            f"unused_real must have 0 consumers, got: {var['consumed_count']}"
        )

    def test_used_real_is_alive(self):
        """[金标准] 真 consumer (assign target) 应该 ALIVE"""
        data = _get_status(FIXTURE_PATH, "packet")
        var = data["rand_vars"][next(
            i for i, v in enumerate(data["rand_vars"])
            if v["name"] == "used_real"
        )]
        self.assertEqual(
            var["status"], "alive",
            f"used_real is read into my_other_addr, must be alive, got: {var['status']}"
        )
        self.assertGreater(var["consumed_count"], 0)


class TestReachabilitySemanticGoldenSummary(unittest.TestCase):
    """Golden summary: 1 alive + 3 dead (not 4 alive)"""

    def test_exact_alive_dead_counts(self):
        """[金标准] 总共 1 alive + 3 dead"""
        data = _get_status(FIXTURE_PATH, "packet")
        # Expected (semantic AST + visitor based, no text grep):
        # - used_real: alive (consumed by my_other_addr = req.used_real)
        # - unused_real: dead (only in $display arg, not real consumer)
        # - only_in_comment: dead (only in comment, no code reference)
        # - only_in_string: dead (only in string literal, no code reference)
        self.assertEqual(data["alive_count"], 1,
                         f"Expected 1 alive (used_real), got {data['alive_count']}")
        self.assertEqual(data["dead_count"], 3,
                         f"Expected 3 dead (unused_real/only_in_comment/only_in_string), got {data['dead_count']}")


if __name__ == "__main__":
    unittest.main()