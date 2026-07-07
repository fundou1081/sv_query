#==============================================================================
# test_randomize.py - `randomize list/extract` CLI command tests
#==============================================================================
"""
[Phase 1 Day 2 2026-07-07] TDD tests for `sv_query randomize` CLI command.

Tests:
  1. `randomize list` returns exit 0 for SV file with rand vars + randomize calls
  2. `randomize list` correctly identifies rand/randc/none variables
  3. `randomize list` finds pre_randomize / post_randomize hooks
  4. `randomize list` finds randomize() calls in task bodies
  5. `randomize list --class` filter works
  6. `randomize list --json` outputs valid JSON
  7. `randomize extract` finds inline constraint expressions
  8. `randomize extract --class` filter works
  9. `randomize extract --json` outputs valid JSON
 10. Non-existent class filter returns empty
"""

import unittest
import subprocess
import tempfile
import os
import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "randomize" / "packet.sv"


def _run_svq(args, cwd=None):
    """Run svq command and return CompletedProcess"""
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestRandomizeListCLI(unittest.TestCase):
    """CLI `randomize list` command tests"""

    def test_randomize_list_help(self):
        """测试 randomize list --help 返回 0 + 含 description"""
        result = _run_svq(["randomize", "list", "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("randomize", result.stdout.lower())

    def test_randomize_list_finds_rand_vars(self):
        """测试 randomize list 找到 rand/randc 变量"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("addr", result.stdout)
        self.assertIn("mode", result.stdout)
        self.assertIn("data", result.stdout)
        # not_rand 应该被排除
        self.assertNotIn("not_rand", result.stdout)

    def test_randomize_list_distinguishes_rand_randc(self):
        """测试 randomize list 区分 rand / randc"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # mode 是 randc
        self.assertIn("randc", result.stdout)
        # addr 是 rand
        self.assertIn("rand", result.stdout)

    def test_randomize_list_finds_hooks(self):
        """测试 randomize list 找到 pre_randomize / post_randomize"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("pre_randomize", result.stdout)
        self.assertIn("post_randomize", result.stdout)

    def test_randomize_list_finds_calls(self):
        """测试 randomize list 找到 randomize() 调用"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("req.randomize", result.stdout)
        # 应该有 inline constraint
        self.assertIn("addr", result.stdout)
        self.assertIn("data", result.stdout)

    def test_randomize_list_class_filter(self):
        """测试 randomize list --class filter"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH), "--class", "my_seq"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # my_seq 没 rand var, 但有 hook + call
        self.assertIn("my_seq", result.stdout)
        # packet 没出现在 output (被 filter)
        # 但 rand_vars section 应该 (none)
        self.assertIn("Hooks", result.stdout)
        # addr/data 应该在 (因为 constraint 引用)
        self.assertIn("req.randomize", result.stdout)

    def test_randomize_list_class_filter_empty(self):
        """测试 randomize list --class 不存在的 class 返回 (none)"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH), "--class", "nonexistent"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # 应该没东西
        self.assertIn("(none found)", result.stdout)

    def test_randomize_list_json_output(self):
        """测试 randomize list --json 输出 valid JSON"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH), "--json"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("rand_variables", data)
        self.assertIn("randomize_calls", data)
        self.assertIn("pre_randomize", data)
        self.assertIn("post_randomize", data)

    def test_randomize_list_json_content(self):
        """测试 randomize list --json 内容正确"""
        result = _run_svq(["randomize", "list", "-f", str(FIXTURE_PATH), "--json"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)

        # rand vars
        rand_addrs = [v for v in data["rand_variables"] if v["name"] == "addr"]
        self.assertEqual(len(rand_addrs), 1)
        self.assertEqual(rand_addrs[0]["kind"], "rand")
        self.assertEqual(rand_addrs[0]["class"], "packet")

        # not_rand 不应该在
        not_rand = [v for v in data["rand_variables"] if v["name"] == "not_rand"]
        self.assertEqual(len(not_rand), 0)

        # randomize calls
        calls_with_constraint = [c for c in data["randomize_calls"] if c["kind"] == "randomize_with_constraint"]
        self.assertGreaterEqual(len(calls_with_constraint), 2)

        # hooks
        pre_hooks = [h for h in data["pre_randomize"] if h["class"] == "packet"]
        self.assertEqual(len(pre_hooks), 1)


class TestRandomizeExtractCLI(unittest.TestCase):
    """CLI `randomize extract` command tests"""

    def test_randomize_extract_help(self):
        """测试 randomize extract --help"""
        result = _run_svq(["randomize", "extract", "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("constraint", result.stdout.lower())

    def test_randomize_extract_finds_inline_constraints(self):
        """测试 randomize extract 找到 inline constraint"""
        result = _run_svq(["randomize", "extract", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # constraint 表达式
        self.assertIn("addr", result.stdout)
        self.assertIn("mode", result.stdout)
        self.assertIn("data", result.stdout)
        # 应该有 ≥2 个 constraint
        self.assertGreaterEqual(result.stdout.count("constraint"), 2)

    def test_randomize_extract_target(self):
        """测试 randomize extract 显示 target receiver"""
        result = _run_svq(["randomize", "extract", "-f", str(FIXTURE_PATH)])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # target 应该是 req
        self.assertIn("req", result.stdout)

    def test_randomize_extract_class_filter(self):
        """测试 randomize extract --class filter"""
        result = _run_svq(["randomize", "extract", "-f", str(FIXTURE_PATH), "--class", "my_seq"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # 应该能看到 constraint
        self.assertIn("addr", result.stdout)

    def test_randomize_extract_json_output(self):
        """测试 randomize extract --json 输出 valid JSON"""
        result = _run_svq(["randomize", "extract", "-f", str(FIXTURE_PATH), "--json"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        # 每项有 has_inline_constraint + inline_constraint
        for item in data:
            self.assertIn("class", item)
            self.assertIn("target", item)
            self.assertIn("inline_constraint", item)


class TestRandomizeEmptyFile(unittest.TestCase):
    """`randomize list/extract` on SV file with no randomize"""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False)
        self.tmpfile.write("""
// Empty module with no rand/randomize
module empty;
endmodule
""")
        self.tmpfile.close()

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_randomize_list_on_empty(self):
        """测试空 SV file 不 crash"""
        result = _run_svq(["randomize", "list", "-f", self.tmpfile.name])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("(none found)", result.stdout)

    def test_randomize_extract_on_empty(self):
        """测试空 SV file 不 crash"""
        result = _run_svq(["randomize", "extract", "-f", self.tmpfile.name])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("(no", result.stdout)


if __name__ == "__main__":
    unittest.main()