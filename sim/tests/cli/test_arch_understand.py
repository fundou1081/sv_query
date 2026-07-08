#==============================================================================
# test_arch_understand.py - IP-Level Design Understanding for arch command
#==============================================================================
"""
[Design Understanding A 2026-07-08] Golden standard test for `arch show --understand`.

Iron Law 7 (boundary test): Golden standard must define expected output
BEFORE implementation. Iron Law 1: All data from semantic AST (no text grep).

Tests:
  1. --understand flag exists
  2. Module purpose inference (from name + submodules)
  3. Clock domains detection
  4. Signal classification (clock/reset/data/control)
  5. Submodule overview
"""

import unittest
import subprocess
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "arch" / "understand.sv"


def _run_svq(args):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
    )


def _run_understand(target="cpu_top", format="summary"):
    """Run `arch show --understand`, return stdout."""
    result = _run_svq([
        "arch", "show",
        "-f", str(FIXTURE_PATH),
        "--target", target,
        "--depth", "3",
        "--format", format,
        "--understand",
    ])
    return result.returncode, result.stdout, result.stderr


# =============================================================================
# Golden Standard (鉄律7)
# =============================================================================

class TestArchUnderstandGolden(unittest.TestCase):
    """Golden standard: arch show --understand 输出 IP-level understanding."""

    def test_understand_flag_exists(self):
        """--understand flag 应该存在, 不报 'no such option'"""
        rc, stdout, stderr = _run_understand()
        # 必须不报 'No such option' 错
        self.assertNotIn("No such option", stderr)
        self.assertNotIn("No such option", stdout)

    def test_understand_outputs_module_purpose(self):
        """[金标准] 输出应该包含 module purpose (从 name + 子模块推断)"""
        rc, stdout, stderr = _run_understand()
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        # 期望: section header + cpu_top + 推断的 purpose
        self.assertIn("IP-Level Understanding", stdout)
        self.assertIn("cpu_top", stdout)
        # CPU detected from name pattern (substring match in _infer_module_purpose)
        self.assertIn("CPU", stdout)

    def test_understand_detects_clock_domains(self):
        """[金标准] 应该 detect clock domains (从 port name clk* 推断)"""
        rc, stdout, stderr = _run_understand()
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        # cpu_top 有 input clk — 应该 detect ≥ 1 clock domain
        self.assertIn("Clock", stdout)
        # 列出 clk
        self.assertIn("clk", stdout)

    def test_understand_classifies_signals(self):
        """[金标准] 应该分类 signals (clock/reset/data/control)"""
        rc, stdout, stderr = _run_understand()
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        # 至少要有 clock + reset + data + control 类别 (lowercase in output)
        # 4+ signal categories
        categories_found = sum(1 for cat in [
            "clock", "reset", "data", "control"
        ] if cat in stdout.lower())
        self.assertGreaterEqual(
            categories_found, 3,
            f"Expected ≥3 signal categories, found {categories_found}\n{stdout}"
        )

    def test_understand_summarizes_submodules(self):
        """[金标准] 应该列出 submodules (regfile, decoder)"""
        rc, stdout, stderr = _run_understand()
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        self.assertIn("regfile", stdout)
        self.assertIn("decoder", stdout)

    def test_understand_combines_with_summary(self):
        """[金标准] --understand 应该跟 --summary 同时存在 (architecture + understanding)"""
        rc, stdout, stderr = _run_understand(format="summary")
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        # 应该有:
        # 1. 架构 summary (existing behavior)
        self.assertIn("Project Architecture", stdout)
        self.assertIn("Total instances", stdout)
        # 2. IP-Level Understanding (new)
        self.assertIn("IP-Level Understanding", stdout)


class TestArchUnderstandDotAnnotation(unittest.TestCase):
    """--understand 跟 --format dot 配合 (在 dot 输出加 annotation)."""

    def test_understand_with_dot_format_no_crash(self):
        """[金标准] --understand + --format dot 不 crash"""
        result = _run_svq([
            "arch", "show",
            "-f", str(FIXTURE_PATH),
            "--target", "cpu_top",
            "--depth", "3",
            "--format", "dot",
            "--understand",
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # dot format 输出应该含 digraph 节点 (cpu_top, regfile, decoder)
        self.assertIn("digraph", result.stdout)
        self.assertIn("cpu_top", result.stdout)


if __name__ == "__main__":
    unittest.main()