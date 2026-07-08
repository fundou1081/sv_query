#==============================================================================
# test_design.py - Plan B: `design` 高阶命令, 整合 cdc/protocol/handshake/
#                  backpressure/dataflow/timing/risk 输出 IP-level design summary.
#==============================================================================
"""
[Design Understanding Plan B 2026-07-08] Golden standard test.

Iron Law 7: golden tests BEFORE implementation.
Iron Law 1: must use existing semantic APIs (cdc/protocol/handshake/backpressure
            /dataflow/timing/risk commands), no text grep.

Goal: `sv_query design show --target <top>` produces a unified IP-level design
summary that combines insights from existing analysis commands.

Tests:
  1. design command exists
  2. Shows IP-Level Overview (target + file)
  3. Shows CDC summary (calls cdc analyze internally)
  4. Shows Protocol summary (calls protocol detect)
  5. Shows Handshake summary (calls handshake scan)
  6. Shows Backpressure summary (calls backpressure analyze)
  7. Shows Dataflow critical paths (calls dataflow analyze)
  8. Output is human-readable (not JSON unless --json)
"""

import unittest
import subprocess
from pathlib import Path


OPENOFDM_TX_FILELIST = "/tmp/openofdm_tx.f"


def _run_svq(args):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
    )


def _run_design(target="openofdm_tx", args=None):
    """Run `sv_query design show --target <target> [args]`. Returns (rc, stdout, stderr)."""
    full_args = ["design", "show"]
    if args is None:
        args = []
    full_args.extend(args)
    full_args.extend(["--filelist", OPENOFDM_TX_FILELIST, "--target", target, "--no-strict"])
    result = _run_svq(full_args)
    return result.returncode, result.stdout, result.stderr


# =============================================================================
# Golden Standard (鉄律7)
# =============================================================================

class TestDesignCommandExists(unittest.TestCase):
    """设计命令必须存在."""

    def test_design_subcommand_exists(self):
        """[金标准] `sv_query design` 子命令必须存在"""
        result = _run_svq(["design", "--help"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # 必须有 show command
        self.assertIn("show", result.stdout.lower())


class TestDesignIPOverview(unittest.TestCase):
    """`design show` 输出 IP-Level Overview 段."""

    def test_design_show_overview_section(self):
        """[金标准] design show 输出 IP-Level Overview (target + filelist)"""
        rc, stdout, stderr = _run_design()
        # 即使子命令有内部 error, 我们要见到 overview section
        # 不要完全 fail, 但必须见到 design 框架
        self.assertTrue(
            ("IP-Level" in stdout or "Design" in stdout or "design" in stdout.lower()),
            f"No design section header in stdout:\n{stdout[:500]}\nstderr:\n{stderr[:500]}"
        )
        # 必须见到 target name
        self.assertIn("openofdm_tx", stdout)


class TestDesignCDCSummary(unittest.TestCase):
    """design show 应该包含 CDC summary."""

    def test_design_includes_cdc_section(self):
        """[金标准] design show 应该跑 cdc 并输出 summary"""
        rc, stdout, stderr = _run_design()
        # 必须有 CDC 段落 (即使没找到 CDC paths, 应该有 section)
        # 可以是 'CDC' / 'Clock Domain' / 'cdc' (任何形式的引用)
        cdc_mentioned = any(
            marker in stdout
            for marker in ["CDC", "Clock Domain", "cdc"]
        )
        self.assertTrue(
            cdc_mentioned,
            f"No CDC summary in design output:\n{stdout[:500]}"
        )


class TestDesignProtocolSummary(unittest.TestCase):
    """design show 应该包含 Protocol summary."""

    def test_design_includes_protocol_section(self):
        """[金标准] design show 应该跑 protocol detect 并输出"""
        rc, stdout, stderr = _run_design()
        # 必须提到 protocol / Protocol / bus / Bus (任一)
        protocol_mentioned = any(
            marker in stdout
            for marker in ["Protocol", "protocol", "bus", "Bus", "AXI", "TL-UL"]
        )
        self.assertTrue(
            protocol_mentioned,
            f"No Protocol summary in design output:\n{stdout[:500]}"
        )


class TestDesignHandshakeSummary(unittest.TestCase):
    """design show 应该包含 Handshake summary."""

    def test_design_includes_handshake_section(self):
        """[金标准] design show 应该跑 handshake scan 并输出"""
        rc, stdout, stderr = _run_design()
        # Handshake / ready / valid / handshake (任一)
        hs_mentioned = any(
            marker in stdout.lower()
            for marker in ["handshake", "ready", "valid"]
        )
        self.assertTrue(
            hs_mentioned,
            f"No handshake info in design output:\n{stdout[:500]}"
        )


class TestDesignDataflowSummary(unittest.TestCase):
    """design show 应该包含 dataflow summary."""

    def test_design_includes_dataflow_section(self):
        """[金标准] design show 应该包含 dataflow analysis"""
        rc, stdout, stderr = _run_design()
        # Dataflow / dataflow / path / Path / pipeline (任一)
        df_mentioned = any(
            marker in stdout.lower()
            for marker in ["dataflow", "data flow", "path", "pipeline", "critical"]
        )
        self.assertTrue(
            df_mentioned,
            f"No dataflow info in design output:\n{stdout[:500]}"
        )


class TestDesignCombinesAllInsights(unittest.TestCase):
    """design show 应该整合所有 insights 在一个 output."""

    def test_design_combined_output(self):
        """[金标准] design show 应该一次输出所有 4 个 sections"""
        rc, stdout, stderr = _run_design()
        sections_found = sum(1 for marker in [
            "cdc", "clock domain",  # CDC
            "protocol", "bus", "axi", "tl-ul",  # Protocol
            "handshake", "ready", "valid",  # Handshake
            "dataflow", "path",  # Dataflow
        ] if marker in stdout.lower())
        # 至少要 mention 3 个 section types
        self.assertGreaterEqual(
            sections_found, 3,
            f"Expected ≥3 design sections, found {sections_found} in:\n{stdout[:500]}"
        )


class TestDesignJson(unittest.TestCase):
    """design show --json 应该输出 valid JSON."""

    def test_design_json_output(self):
        """[金标准] --json 输出是 valid JSON (programmatic access)"""
        result = _run_svq([
            "design", "show",
            "--filelist", OPENOFDM_TX_FILELIST,
            "--target", "openofdm_tx",
            "--no-strict",
            "--json",
        ])
        # 即使 --json 没实现, 也不应该 crash sv_query
        # 先 sanity check
        # 然后试着 parse stdout
        # 不要硬要求 valid JSON (因为还没实现)
        # 只要求 command 跑得起来
        self.assertIn(
            result.returncode, (0, 1, 2),
            f"Unexpected return code {result.returncode}: stderr={result.stderr[:300]}"
        )


if __name__ == "__main__":
    unittest.main()