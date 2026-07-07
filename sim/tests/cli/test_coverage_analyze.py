#==============================================================================
# test_coverage_analyze.py - `coverage analyze` CLI command tests (Phase 2)
#==============================================================================
"""
[Phase 2 Day 4 2026-07-07] TDD tests for `sv_query coverage analyze`.

Tests:
  1. help 命令工作
  2. 找到 covergroup (1)
  3. 列出 coverpoints
  4. 列出 bins (含 illegal_bins)
  5. 列出 crosses
  6. --class filter
  7. JSON output valid
"""

import unittest
import subprocess
import tempfile
import os
import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "covergroup" / "cg_pkg.sv"


def _run_svq(args, cwd=None):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestCoverageAnalyzeCLI(unittest.TestCase):
    """CLI `coverage analyze` command tests (Phase 2 Day 4)"""

    def test_coverage_analyze_help(self):
        """测试 coverage analyze --help"""
        result = _run_svq(["coverage", "analyze", "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("covergroup", result.stdout.lower())

    def test_coverage_analyze_finds_covergroup(self):
        """测试 coverage analyze 找到 covergroup"""
        result = _run_svq(["coverage", "analyze", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # 应该至少 1 个 covergroup
        self.assertIn("Covergroup:", result.stdout)
        self.assertIn("cg", result.stdout)

    def test_coverage_analyze_lists_coverpoints(self):
        """测试 coverage analyze 列出 coverpoints"""
        result = _run_svq(["coverage", "analyze", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # coverpoint 信号名
        self.assertIn("addr", result.stdout)
        self.assertIn("mode", result.stdout)
        self.assertIn("Coverpoints", result.stdout)

    def test_coverage_analyze_lists_bins(self):
        """测试 coverage analyze 列出 bins (含 illegal_bins)"""
        result = _run_svq(["coverage", "analyze", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # bins name
        self.assertIn("low", result.stdout)
        self.assertIn("high", result.stdout)
        self.assertIn("mid", result.stdout)
        # illegal_bins
        self.assertIn("illegal_bins", result.stdout)
        self.assertIn("bad", result.stdout)

    def test_coverage_analyze_lists_crosses(self):
        """测试 coverage analyze 列出 crosses"""
        result = _run_svq(["coverage", "analyze", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Crosses", result.stdout)

    def test_coverage_analyze_summary(self):
        """测试 coverage analyze 输出 summary line"""
        result = _run_svq(["coverage", "analyze", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Summary:", result.stdout)

    def test_coverage_analyze_json(self):
        """测试 coverage analyze --json 输出 valid JSON"""
        result = _run_svq(["coverage", "analyze", "-f", str(FIXTURE_PATH), "--json"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("total_covergroups", data)
        self.assertIn("covergroups", data)
        self.assertGreaterEqual(data["total_covergroups"], 1)

    def test_coverage_analyze_json_content(self):
        """测试 coverage analyze --json 内容正确"""
        result = _run_svq(["coverage", "analyze", "-f", str(FIXTURE_PATH), "--json"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        cg = data["covergroups"][0]
        self.assertIn("name", cg)
        self.assertIn("coverpoints", cg)
        self.assertIn("crosses", cg)

    def test_coverage_analyze_empty_file(self):
        """测试空 SV file 不 crash"""
        tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False)
        tmpfile.write("module empty; endmodule\n")
        tmpfile.close()
        try:
            result = _run_svq(["coverage", "analyze", "-f", tmpfile.name])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            self.assertIn("(no covergroup found)", result.stdout)
        finally:
            os.unlink(tmpfile.name)


if __name__ == "__main__":
    unittest.main()
