#==============================================================================
# test_randomize_trace.py - `randomize trace` CLI command tests (Phase 2)
#==============================================================================
"""
[Phase 2 Day 3 2026-07-07] TDD tests for `sv_query randomize trace`.

Tests:
  1. help 命令工作
  2. 找到 randomize() calls
  3. 找到 pre/post_randomize hooks
  4. inline constraint 提取
  5. pattern detection (generic / sequence / driver)
  6. JSON output valid
  7. 不存在的 class/method 报错
  8. fork points detection
"""

import unittest
import subprocess
import tempfile
import os
import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "randomize" / "packet.sv"


def _run_svq(args, cwd=None):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestRandomizeTraceCLI(unittest.TestCase):
    """CLI `randomize trace` command tests (Phase 2 Day 3)"""

    def test_randomize_trace_help(self):
        """测试 randomize trace --help 返回 0 + description"""
        result = _run_svq(["randomize", "trace", "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("randomize", result.stdout.lower())

    def test_randomize_trace_finds_calls(self):
        """测试 randomize trace 找到 randomize() calls"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "my_seq",
            "--method", "body",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("req.randomize", result.stdout)
        # 应该 3 个 (1 bare + 2 with constraint)
        self.assertGreaterEqual(result.stdout.count("req.randomize"), 3)

    def test_randomize_trace_finds_hooks(self):
        """测试 randomize trace 找到 pre/post_randomize hooks"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "my_seq",
            "--method", "body",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Pre-randomize", result.stdout)
        self.assertIn("Post-randomize", result.stdout)
        # 至少 packet + my_seq 都有
        self.assertIn("packet", result.stdout)
        self.assertIn("my_seq", result.stdout)

    def test_randomize_trace_extracts_inline_constraint(self):
        """测试 randomize trace 提取 inline constraint"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "my_seq",
            "--method", "body",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # inline constraint 文本
        self.assertIn("addr", result.stdout)
        self.assertIn("mode", result.stdout)
        self.assertIn("data", result.stdout)
        self.assertIn("inline constraint", result.stdout)

    def test_randomize_trace_json_output(self):
        """测试 randomize trace --json 输出 valid JSON"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "my_seq",
            "--method", "body",
            "--json",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("entry", data)
        self.assertIn("pattern", data)
        self.assertIn("randomize_calls", data)
        self.assertEqual(data["entry"], "my_seq.body")

    def test_randomize_trace_json_randomize_calls(self):
        """测试 randomize trace --json randomize_calls 完整"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "my_seq",
            "--method", "body",
            "--json",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(len(data["randomize_calls"]), 3)
        # 第一个是 bare, 后面 2 个有 inline constraint
        calls_with_constraint = [c for c in data["randomize_calls"] if c["inline_constraint"]]
        self.assertEqual(len(calls_with_constraint), 2)

    def test_randomize_trace_unknown_class(self):
        """测试 randomize trace 不存在的 class 不 crash"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "nonexistent",
            "--method", "body",
        ])
        # 应该 exit 非 0 或有 warning/errors
        # 不 crash 就 OK
        self.assertNotEqual(result.returncode, 0, f"stderr: {result.stderr}")

    def test_randomize_trace_no_strict(self):
        """测试 randomize trace --no-strict 工作"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "my_seq",
            "--method", "body",
            "--no-strict",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("req.randomize", result.stdout)

    def test_randomize_trace_summary_line(self):
        """测试 randomize trace 输出有 summary line"""
        result = _run_svq([
            "randomize", "trace",
            "-f", str(FIXTURE_PATH),
            "--class", "my_seq",
            "--method", "body",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Summary:", result.stdout)
        self.assertIn("randomize calls", result.stdout)


class TestRandomizeTraceNoRandomize(unittest.TestCase):
    """`randomize trace` on SV file with no randomize calls"""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False)
        self.tmpfile.write("""
class simple;
    task do_something();
        // no randomize here
    endtask
endclass
""")
        self.tmpfile.close()

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_trace_no_randomize(self):
        """测试 SV file 没 randomize() 时 trace 正常"""
        result = _run_svq([
            "randomize", "trace",
            "-f", self.tmpfile.name,
            "--class", "simple",
            "--method", "do_something",
        ])
        # 应该 exit 0 (没 randomize 是 valid case)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("(no randomize() calls in this call graph)", result.stdout)


if __name__ == "__main__":
    unittest.main()