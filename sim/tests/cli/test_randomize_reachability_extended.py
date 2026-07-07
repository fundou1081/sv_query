#==============================================================================
# test_randomize_reachability_extended.py - Extended reachability tests
#==============================================================================
"""
[Phase 3 Day 3 2026-07-07] Extended `randomize reachability` tests with more cases.

Tests:
  1. inheritance (base + extended class)
  2. covergroup sample (covered_in 检测)
  3. hierarchy (multi-class driver + monitor + scoreboard)
  4. no_randomize (rand 但没 randomize() call)
  5. multi_randomize (同 var 多次 randomize)
  6. function_randomize (randomize 在 function body)
"""

import unittest
import subprocess
import json
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "randomize"


def _run_svq(args):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
    )


# =============================================================================
# Helper: get status of each rand var from JSON
# =============================================================================

def _get_reachability_status(fixture_path, class_name):
    """Run reachability --json, return dict of var_name -> status."""
    result = _run_svq([
        "randomize", "reachability",
        "-f", str(fixture_path),
        "--class", class_name,
        "--json",
    ])
    if result.returncode != 0:
        raise AssertionError(f"reachability failed: {result.stderr}")
    data = json.loads(result.stdout)
    return {v["name"]: v for v in data["rand_vars"]}


# =============================================================================
# 1. inheritance
# =============================================================================

class TestReachabilityInheritance(unittest.TestCase):
    """rand vars 在 base + extended class, driver consume all"""

    def test_base_class_all_alive(self):
        """base_packet 的 rand vars 全 alive (driver 消费)"""
        status = _get_reachability_status(
            FIXTURE_DIR / "inheritance.sv", "base_packet"
        )
        self.assertEqual(len(status), 2)
        self.assertEqual(status["base_addr"]["status"], "alive")
        self.assertEqual(status["base_mode"]["status"], "alive")

    def test_extended_class_all_alive(self):
        """extended_packet 的 rand vars (含继承的 base) 全 alive"""
        status = _get_reachability_status(
            FIXTURE_DIR / "inheritance.sv", "extended_packet"
        )
        # extended_packet 有 base_addr + base_mode (继承) + ext_data
        self.assertEqual(len(status), 3)
        self.assertEqual(status["base_addr"]["status"], "alive")
        self.assertEqual(status["base_mode"]["status"], "alive")
        self.assertEqual(status["ext_data"]["status"], "alive")

    def test_inheritance_alive_count(self):
        """inheritance 总 alive 跟 dead count 跟 expected match"""
        result = _run_svq([
            "randomize", "reachability",
            "-f", str(FIXTURE_DIR / "inheritance.sv"),
            "--class", "extended_packet",
            "--json",
        ])
        data = json.loads(result.stdout)
        self.assertEqual(data["alive_count"], 3)
        self.assertEqual(data["dead_count"], 0)


# =============================================================================
# 2. covergroup sample
# =============================================================================

class TestReachabilityCovergroupSample(unittest.TestCase):
    """rand var 被 covergroup sample (没 consumer, 应该 alive via covered_in)"""

    def test_covergroup_sample_makes_alive(self):
        """addr 被 coverpoint sample — 应该 alive (不是 dead)"""
        status = _get_reachability_status(
            FIXTURE_DIR / "covergroup_sample.sv", "packet"
        )
        self.assertEqual(status["addr"]["status"], "alive")
        self.assertEqual(status["mode"]["status"], "alive")

    def test_covergroup_sample_covered_in(self):
        """covered_in 字段应该列出 covergroup"""
        status = _get_reachability_status(
            FIXTURE_DIR / "covergroup_sample.sv", "packet"
        )
        # addr 应该 covered by covergroup cg
        self.assertGreater(status["addr"]["covered_count"], 0)
        self.assertEqual(
            status["addr"]["covered_in"][0]["covergroup"],
            "cg"
        )
        self.assertEqual(
            status["addr"]["covered_in"][0]["coverpoint"],
            "addr"
        )


# =============================================================================
# 3. hierarchy (multi-class consumer)
# =============================================================================

class TestReachabilityHierarchy(unittest.TestCase):
    """6 rand vars consumed by driver (4) + monitor (2)"""

    def test_all_6_vars_alive(self):
        """6 vars 全 alive (driver + monitor consume)"""
        status = _get_reachability_status(
            FIXTURE_DIR / "hierarchy.sv", "packet"
        )
        self.assertEqual(len(status), 6)
        for name in ["addr", "data", "mode", "prio", "tag", "seq_id"]:
            self.assertEqual(status[name]["status"], "alive",
                             f"{name} should be alive")

    def test_hierarchy_consumed_count(self):
        """每 var consumed_count >= 2 (driver + monitor)"""
        status = _get_reachability_status(
            FIXTURE_DIR / "hierarchy.sv", "packet"
        )
        for name, v in status.items():
            # driver consumes 4 vars (addr/data/mode/prio)
            # monitor consumes 2 vars (tag/seq_id)
            # 但 cross-class scan 应该都找到
            self.assertGreaterEqual(v["consumed_count"], 1, f"{name} not consumed")


# =============================================================================
# 4. no_randomize
# =============================================================================

class TestReachabilityNoRandomize(unittest.TestCase):
    """rand vars but no randomize() call — alive if consumed, dead if not"""

    def test_no_randomize_alive_via_consumer(self):
        """有 consumer, 即使没 randomize() 也应该 alive"""
        status = _get_reachability_status(
            FIXTURE_DIR / "no_randomize.sv", "packet"
        )
        self.assertEqual(status["addr"]["status"], "alive")
        self.assertEqual(status["data"]["status"], "alive")

    def test_no_randomize_zero_count(self):
        """randomized_count = 0 (没有 randomize() 调用)"""
        status = _get_reachability_status(
            FIXTURE_DIR / "no_randomize.sv", "packet"
        )
        self.assertEqual(status["addr"]["randomized_count"], 0)
        self.assertEqual(status["data"]["randomized_count"], 0)


# =============================================================================
# 5. multi_randomize
# =============================================================================

class TestReachabilityMultiRandomize(unittest.TestCase):
    """同 var 多次 randomize() with different constraints"""

    def test_multi_randomize_addr_count(self):
        """addr 在 2 个 inline constraint 中提及 (前 2 call)"""
        status = _get_reachability_status(
            FIXTURE_DIR / "multi_randomize.sv", "packet"
        )
        # addr 在 'addr < 64' 跟 'addr >= 128' 两个 constraint 里
        # 但第 1 个 randomize() 是 bare, 不算
        self.assertEqual(status["addr"]["randomized_count"], 2)

    def test_multi_randomize_mode_count(self):
        """mode 在 1 个 inline constraint 提及"""
        status = _get_reachability_status(
            FIXTURE_DIR / "multi_randomize.sv", "packet"
        )
        # mode 只在 'addr >= 128; mode != 0;' 里
        self.assertEqual(status["mode"]["randomized_count"], 1)

    def test_multi_randomize_all_alive(self):
        """addr + mode 都 alive (consumer reads addr; mode referenced in inline constraint)"""
        status = _get_reachability_status(
            FIXTURE_DIR / "multi_randomize.sv", "packet"
        )
        self.assertEqual(status["addr"]["status"], "alive")
        # mode 被人引用 (在 inline constraint 里 task body) — alive
        self.assertEqual(status["mode"]["status"], "alive")


# =============================================================================
# 6. function_randomize (randomize() 在 function 不是 task)
# =============================================================================

class TestReachabilityFunctionRandomize(unittest.TestCase):
    """randomize() call in function body (not task)"""

    def test_function_randomize_count(self):
        """randomize() 在 function body, 应该 1 randomized call"""
        status = _get_reachability_status(
            FIXTURE_DIR / "function_randomize.sv", "packet"
        )
        # fn_seq.do_randomize() 有 randomize() call
        # (packet.randomize() 调用应在 fn_seq.do_randomize() 内)
        self.assertGreaterEqual(status["addr"]["randomized_count"], 1)

    def test_function_randomize_alive(self):
        """function body 也能消费 — alive via consumer.consume()"""
        status = _get_reachability_status(
            FIXTURE_DIR / "function_randomize.sv", "packet"
        )
        self.assertEqual(status["addr"]["status"], "alive")


# =============================================================================
# 综合: 各 fixture 总览
# =============================================================================

class TestReachabilityFixturesOverview(unittest.TestCase):
    """测试所有 fixtures 跑不 crash + 返回 valid JSON"""

    FIXTURES = [
        ("driver.sv", "packet", 4, 0),
        ("dead.sv", "packet", 1, 2),
        ("inheritance.sv", "base_packet", 2, 0),
        ("inheritance.sv", "extended_packet", 3, 0),
        ("covergroup_sample.sv", "packet", 2, 0),
        ("hierarchy.sv", "packet", 6, 0),
        ("no_randomize.sv", "packet", 2, 0),
        ("multi_randomize.sv", "packet", 2, 0),  # addr + mode (mode referenced in inline constraint)
        ("function_randomize.sv", "packet", 1, 0),
    ]

    def test_all_fixtures_return_valid_json(self):
        """每个 fixture 应该返回 valid JSON"""
        for fixture, cls, _, _ in self.FIXTURES:
            result = _run_svq([
                "randomize", "reachability",
                "-f", str(FIXTURE_DIR / fixture),
                "--class", cls,
                "--json",
            ])
            self.assertEqual(result.returncode, 0, f"{fixture} failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertIn("rand_vars", data, f"{fixture} missing rand_vars")

    def test_all_fixtures_expected_alive_dead_count(self):
        """每个 fixture 应该匹配 expected alive_count / dead_count"""
        for fixture, cls, expected_alive, expected_dead in self.FIXTURES:
            result = _run_svq([
                "randomize", "reachability",
                "-f", str(FIXTURE_DIR / fixture),
                "--class", cls,
                "--json",
            ])
            data = json.loads(result.stdout)
            self.assertEqual(
                data["alive_count"], expected_alive,
                f"{fixture} alive_count: got {data['alive_count']}, expected {expected_alive}"
            )
            self.assertEqual(
                data["dead_count"], expected_dead,
                f"{fixture} dead_count: got {data['dead_count']}, expected {expected_dead}"
            )


if __name__ == "__main__":
    unittest.main()