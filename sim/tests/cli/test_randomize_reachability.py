#==============================================================================
# test_randomize_reachability.py - `randomize reachability` CLI tests (Phase 3)
#==============================================================================
"""
[Phase 3 Day 1-2 2026-07-07] TDD tests for `sv_query randomize reachability`.

Tests:
  1. help 命令工作
  2. 检测 dead randomize (var 没被消费)
  3. 检测 alive randomize (var 被消费)
  4. randomized_in 显示 randomize() 调用
  5. covered_in 显示 covergroup
  6. JSON output valid
  7. unknown class 报错
"""

import unittest
import subprocess
import tempfile
import os
import json
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "randomize"
DRIVER_FIXTURE = FIXTURE_DIR / "driver.sv"
DEAD_FIXTURE = FIXTURE_DIR / "dead.sv"
PACKET_FIXTURE = FIXTURE_DIR / "packet.sv"


def _run_svq(args, cwd=None):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestRandomizeReachabilityCLI(unittest.TestCase):
    """CLI `randomize reachability` command tests (Phase 3 Day 1-2)"""

    def test_reachability_help(self):
        """测试 reachability --help"""
        result = _run_svq(["randomize", "reachability", "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("reachability", result.stdout.lower())

    def test_reachability_detects_alive(self):
        """测试 reachability 检测 alive rand vars (driver consumes)"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(DRIVER_FIXTURE),
            "--class", "packet",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # driver consumes all 4 rand vars
        self.assertEqual(result.stdout.count("🟢 ALIVE"), 4)
        self.assertEqual(result.stdout.count("🔴 DEAD"), 0)
        self.assertIn("All rand vars are consumed", result.stdout)

    def test_reachability_detects_dead(self):
        """测试 reachability 检测 dead rand vars"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(DEAD_FIXTURE),
            "--class", "packet",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # dead.sv: used_addr alive, unused_data + never_read_mode dead
        self.assertEqual(result.stdout.count("🟢 ALIVE"), 1)
        self.assertEqual(result.stdout.count("🔴 DEAD"), 2)
        self.assertIn("dead randomize(s) detected", result.stdout)

    def test_reachability_randomized_in(self):
        """测试 reachability 显示 randomized_in (哪 randomize call)"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(PACKET_FIXTURE),
            "--class", "packet",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # packet.sv my_seq.body 有 randomize() calls with addr/mode/data
        self.assertIn("req.randomize()", result.stdout)
        # inline constraint 文本 "{ addr < 64" 应该出现
        self.assertIn("addr < 64", result.stdout)
        # "with" 关键词应该出现 (with constraint)
        self.assertIn("with {", result.stdout)

    def test_reachability_json_output(self):
        """测试 reachability --json 输出 valid JSON"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(DEAD_FIXTURE),
            "--class", "packet",
            "--json",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("class", data)
        self.assertIn("total_rand_vars", data)
        self.assertIn("alive_count", data)
        self.assertIn("dead_count", data)
        self.assertIn("rand_vars", data)

    def test_reachability_json_content_dead(self):
        """测试 reachability --json 正确标 dead"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(DEAD_FIXTURE),
            "--class", "packet",
            "--json",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["class"], "packet")
        self.assertEqual(data["total_rand_vars"], 3)
        self.assertEqual(data["alive_count"], 1)
        self.assertEqual(data["dead_count"], 2)

        # 找 used_addr (alive) 跟 unused_data (dead)
        alive_vars = [v for v in data["rand_vars"] if v["status"] == "alive"]
        dead_vars = [v for v in data["rand_vars"] if v["status"] == "dead"]
        self.assertEqual(len(alive_vars), 1)
        self.assertEqual(len(dead_vars), 2)
        self.assertEqual(alive_vars[0]["name"], "used_addr")
        dead_names = {v["name"] for v in dead_vars}
        self.assertEqual(dead_names, {"unused_data", "never_read_mode"})

    def test_reachability_json_content_driver(self):
        """测试 reachability --json 全 alive (driver fixture)"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(DRIVER_FIXTURE),
            "--class", "packet",
            "--json",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["alive_count"], 4)
        self.assertEqual(data["dead_count"], 0)
        # 每 var 应该有 ≥1 consumer
        for v in data["rand_vars"]:
            self.assertGreater(v["consumed_count"], 0, f"{v['name']} has no consumers")

    def test_reachability_unknown_class(self):
        """测试 reachability 不存在的 class exit 1"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(PACKET_FIXTURE),
            "--class", "nonexistent_class_xyz",
        ])
        self.assertNotEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("not found", result.stderr)

    def test_reachability_json_unknown_class(self):
        """测试 reachability --json unknown class 也有 JSON error"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(PACKET_FIXTURE),
            "--class", "nonexistent_class_xyz",
            "--json",
        ])
        self.assertNotEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("error", data)

    def test_reachability_summary(self):
        """测试 reachability 输出 summary"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(DRIVER_FIXTURE),
            "--class", "packet",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Total rand vars", result.stdout)
        self.assertIn("alive:", result.stdout)
        self.assertIn("dead:", result.stdout)


if __name__ == "__main__":
    unittest.main()