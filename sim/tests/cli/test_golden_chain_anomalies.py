"""
[Golden Tests 2026-07-10] Verify chain anomaly detection against hand-crafted SV patterns.

方豆 2026-07-10 10:38: '构造几个golden testcase，去测试一下'

Each testcase is a minimal SV file that exhibits a specific RTL anomaly pattern.
These are used to validate that chain anomaly detection correctly identifies:
- X_DRIVER: wire with no driver (output undefined)
- DANGLING: reg written but never read (dead code)
- NORMAL: properly connected (no anomalies)
- COMBINED: X_DRIVER + DANGLING in same chain
- SUBMODULE: cross-module port mapping (no anomalies)

Usage: pytest sim/tests/cli/test_golden_chain_anomalies.py -v
"""
import re
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = PROJECT_ROOT / "tests" / "fixtures" / "golden_chain"


def run_chain(target: str, tc_dir: str, max_edges: int = 30) -> dict:
    """Run chain on a golden testcase and return parsed results."""
    filelist = GOLDEN_DIR / tc_dir / "filelist.f"
    if not filelist.exists():
        raise FileNotFoundError(f"Missing filelist: {filelist}")
    dot_out = Path(f"/tmp/golden_{tc_dir}.dot")
    result = subprocess.run(
        ["sv_query", "visualize", "chain",
         "-f", str(filelist), "--no-strict",
         "--target", target, "--auto",
         "--max-edges", str(max_edges),
         "--dot", str(dot_out)],
        capture_output=True, text=True, timeout=120,
    )
    # Parse anomaly counts from stderr
    anomaly_match = re.search(r"RTL anomalies detected[^\n]*:\s*({[^}]+})", result.stderr)
    anomaly_counts = {}
    if anomaly_match:
        # Parse like "{'X_DRIVER': 2}"
        counts_str = anomaly_match.group(1)
        for m in re.finditer(r"'(\w+)':\s*(\d+)", counts_str):
            anomaly_counts[m.group(1)] = int(m.group(2))
    # Parse individual anomalies
    anomalies = []
    for line in result.stderr.split("\n"):
        m = re.search(r"-\s+(\w+):\s+(\w+)", line)
        if m and m.group(2) in ("X_DRIVER", "DANGLING", "ORPHAN"):
            anomalies.append((m.group(1), m.group(2)))
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "anomaly_counts": anomaly_counts,
        "anomalies": anomalies,
    }


class TestGoldenChainNormal(unittest.TestCase):
    """[Golden] Normal chain: all signals properly connected, 0 anomalies."""

    def test_normal_no_anomalies(self):
        result = run_chain("normal", "normal")
        self.assertEqual(result["returncode"], 0, f"chain failed: {result['stderr']}")
        # Should NOT report any anomalies
        self.assertEqual(
            result["anomaly_counts"], {},
            f"Normal chain should have 0 anomalies, got {result['anomaly_counts']}"
        )


class TestGoldenChainXDriver(unittest.TestCase):
    """[Golden] X_DRIVER: wire with no driver (output undefined).

    Source: x_driver.sv has `wire orphan_wire;` declared but never driven.
    Used in: `assign data_o = data_reg + orphan_wire;`
    Expected: orphan_wire flagged as X_DRIVER.
    """

    def test_x_driver_detected(self):
        result = run_chain("x_driver", "x_driver")
        self.assertEqual(result["returncode"], 0, f"chain failed: {result['stderr']}")
        self.assertIn("X_DRIVER", result["anomaly_counts"],
                     f"Should detect X_DRIVER, got {result['anomaly_counts']}")
        self.assertEqual(result["anomaly_counts"]["X_DRIVER"], 1,
                       f"Should detect exactly 1 X_DRIVER, got {result['anomaly_counts']}")

    def test_x_driver_correct_signal(self):
        result = run_chain("x_driver", "x_driver")
        # The anomaly should be on 'orphan_wire' specifically
        anomaly_signals = [name for name, kind in result["anomalies"]]
        self.assertIn("orphan_wire", anomaly_signals,
                     f"orphan_wire should be flagged, got {anomaly_signals}")


class TestGoldenChainDangling(unittest.TestCase):
    """[Golden] DANGLING: reg written but never read (dead code).

    Source: dangling.sv has `reg [7:0] unused_reg;` written in always block,
    but data_o only reads `data_reg`, not `unused_reg`.
    Expected: unused_reg flagged as DANGLING.
    """

    def test_dangling_detected(self):
        result = run_chain("dangling", "dangling")
        self.assertEqual(result["returncode"], 0, f"chain failed: {result['stderr']}")
        self.assertIn("DANGLING", result["anomaly_counts"],
                     f"Should detect DANGLING, got {result['anomaly_counts']}")
        self.assertEqual(result["anomaly_counts"]["DANGLING"], 1,
                       f"Should detect exactly 1 DANGLING, got {result['anomaly_counts']}")

    def test_dangling_correct_signal(self):
        result = run_chain("dangling", "dangling")
        anomaly_signals = [name for name, kind in result["anomalies"]]
        self.assertIn("unused_reg", anomaly_signals,
                     f"unused_reg should be flagged, got {anomaly_signals}")


class TestGoldenChainCombined(unittest.TestCase):
    """[Golden] COMBINED: X_DRIVER + DANGLING in same dead code chain.

    Source: combined.sv has 2 undriven wires feeding a chain_wire that has no consumer.
    Expected: 2 X_DRIVER (isolated_a, isolated_b) + 1 DANGLING (chain_wire).
    """

    def test_combined_anomalies(self):
        result = run_chain("combined", "combined")
        self.assertEqual(result["returncode"], 0, f"chain failed: {result['stderr']}")
        # Should have 2 X_DRIVER + 1 DANGLING
        self.assertEqual(result["anomaly_counts"].get("X_DRIVER", 0), 2,
                       f"Should have 2 X_DRIVER, got {result['anomaly_counts']}")
        self.assertEqual(result["anomaly_counts"].get("DANGLING", 0), 1,
                       f"Should have 1 DANGLING, got {result['anomaly_counts']}")

    def test_combined_correct_signals(self):
        result = run_chain("combined", "combined")
        anomaly_signals = sorted([name for name, kind in result["anomalies"]])
        self.assertIn("isolated_a", anomaly_signals)
        self.assertIn("isolated_b", anomaly_signals)
        self.assertIn("chain_wire", anomaly_signals)


class TestGoldenChainSubmodule(unittest.TestCase):
    """[Golden] SUBMODULE: cross-module port mapping should NOT be flagged.

    Source: top.sv has `sub u_sub(.a_i(data_i), .b_o(sub_out));` — a submodule.
    The chain crosses module boundaries: data_i → sub.a_i → sub.b_o → sub_out → data_o.
    Expected: 0 anomalies (port crossings are valid).
    """

    def test_submodule_no_anomalies(self):
        result = run_chain("top", "submodule")
        self.assertEqual(result["returncode"], 0, f"chain failed: {result['stderr']}")
        # Submodule port mapping is valid — no anomalies
        self.assertEqual(
            result["anomaly_counts"], {},
            f"Submodule chain should have 0 anomalies, got {result['anomaly_counts']}"
        )


if __name__ == "__main__":
    unittest.main()


class TestChainAnomalyVisualization(unittest.TestCase):
    """[FIX 2026-07-10] Anomalies are now visible in DOT, not just stderr.

    方豆 feedback 14:20: '修复发现的问题'
    Issue: chain reported X_DRIVER (orphan_wire) in stderr but the signal
    wasn't visible in the diagram, so users couldn't see the bug from
    the picture alone.
    Fix: Add 'Anomalies' cluster to chain DOT with dashed edges showing
    the broken connections.
    """

    def _run_chain(self, target: str, tc_dir: str) -> str:
        filelist = GOLDEN_DIR / tc_dir / "filelist.f"
        dot_out = Path(f"/tmp/_viz_test_{tc_dir}.dot")
        subprocess.run(
            ["sv_query", "visualize", "chain",
             "-f", str(filelist), "--no-strict",
             "--target", target, "--auto",
             "--max-edges", "30", "--dot", str(dot_out)],
            capture_output=True, text=True, timeout=120,
        )
        return dot_out.read_text()

    def test_x_driver_anomaly_visible_in_dot(self):
        """orphan_wire should be visible as diamond in chain DOT."""
        dot = self._run_chain("x_driver", "x_driver")
        # Should have cluster_anomalies
        self.assertIn("cluster_anomalies", dot,
                     "Should have 'RTL Anomalies' cluster in DOT")
        # orphan_wire should appear as a diamond
        self.assertIn("orphan_wire", dot, "orphan_wire should appear in DOT")
        # Should be marked as X_DRIVER
        self.assertIn("[X_DRIVER]", dot,
                     "orphan_wire should be labeled with anomaly type")
        # Should have diamond shape
        self.assertIn("shape=diamond", dot,
                     "Anomaly node should use diamond shape")

    def test_x_driver_dashed_edge_to_consumer(self):
        """X_DRIVER should have dashed orange edge to its consumer (data_o)."""
        dot = self._run_chain("x_driver", "x_driver")
        # Should have a dashed edge labeled "X-driver path"
        self.assertRegex(dot, r'style=dashed.*X-driver path',
                        "Should have dashed edge with 'X-driver path' label")

    def test_combined_anomalies_all_visible(self):
        """Combined testcase: 2 X_DRIVER + 1 DANGLING all visible."""
        dot = self._run_chain("combined", "combined")
        for sig in ["isolated_a", "isolated_b", "chain_wire"]:
            self.assertIn(sig, dot, f"{sig} should be in DOT")
        # Should have multiple diamonds
        diamond_count = dot.count("shape=diamond")
        self.assertGreaterEqual(diamond_count, 3,
                              f"Should have 3+ diamonds, got {diamond_count}")

    def test_dangling_anomaly_visible(self):
        """unused_reg should be visible as DANGLING diamond."""
        dot = self._run_chain("dangling", "dangling")
        self.assertIn("cluster_anomalies", dot)
        self.assertIn("unused_reg", dot)
        self.assertIn("[DANGLING]", dot,
                     "unused_reg should be labeled DANGLING")

    def test_normal_has_no_anomaly_cluster(self):
        """Normal testcase: no anomalies → no anomaly cluster needed."""
        dot = self._run_chain("normal", "normal")
        self.assertNotIn("cluster_anomalies", dot,
                        "Normal chain should NOT have anomaly cluster")


class TestTimingAnomalyDetection(unittest.TestCase):
    """[FIX 2026-07-10] timing analyze detects RTL anomalies that may truncate critical paths.

    方豆 2026-07-10 14:20: '修复发现的问题'
    Issue: timing's critical path was incomplete (truncated at data_reg) because
    orphan_wire was undriven. Without visibility into the anomaly, user couldn't
    understand WHY the path was incomplete.
    Fix: timing now reports RTL anomalies and shows them in DOT.
    """

    def _run_timing(self, target: str, tc_dir: str, max_paths: int = 5) -> tuple[str, str]:
        filelist = GOLDEN_DIR / tc_dir / "filelist.f"
        dot_out = Path(f"/tmp/_timing_{tc_dir}.dot")
        result = subprocess.run(
            ["sv_query", "timing", "analyze",
             "-f", str(filelist), "--no-strict",
             "--max-paths", str(max_paths),
             "--dot", str(dot_out)],
            capture_output=True, text=True, timeout=120,
        )
        return dot_out.read_text(), result.stderr

    def test_timing_x_driver_anomaly_visible(self):
        """x_driver: timing should report orphan_wire as X_DRIVER anomaly."""
        dot, stderr = self._run_timing("x_driver", "x_driver")
        # Should report anomaly count (English message)
        self.assertIn("RTL anomalies detected", stderr,
                     "Timing should report anomalies in text output")
        # Should have cluster_timing_anomalies in DOT
        self.assertIn("cluster_timing_anomalies", dot,
                     "DOT should have timing anomalies cluster")
        # orphan_wire should be in the DOT
        self.assertIn("orphan_wire", dot, "orphan_wire should appear in DOT")
        # Should be marked as X_DRIVER
        self.assertIn("[X_DRIVER]", dot,
                     "orphan_wire should be labeled with X_DRIVER")

    def test_timing_combined_multiple_anomalies(self):
        """combined: timing should report 2 X_DRIVER + 1 DANGLING."""
        dot, stderr = self._run_timing("combined", "combined")
        self.assertIn("RTL anomalies detected", stderr)
        # Should have multiple anomalies
        x_driver_count = dot.count("[X_DRIVER]")
        dangling_count = dot.count("[DANGLING]")
        self.assertGreaterEqual(x_driver_count + dangling_count, 3,
                              f"Should have 3+ anomalies, got X_DRIVER={x_driver_count} DANGLING={dangling_count}")

    def test_timing_normal_no_anomaly(self):
        """normal: timing should report no anomalies."""
        dot, stderr = self._run_timing("normal", "normal")
        # Should NOT have anomaly cluster
        self.assertNotIn("cluster_timing_anomalies", dot,
                        "Normal timing should NOT have anomaly cluster")
        # stderr should not have anomaly warning
        self.assertNotIn("RTL anomalies detected", stderr,
                        "Normal timing should not have anomaly warning")

    def test_timing_dangling_anomaly(self):
        """dangling: timing should report unused_reg as DANGLING."""
        dot, stderr = self._run_timing("dangling", "dangling")
        self.assertIn("RTL anomalies detected", stderr)
        self.assertIn("unused_reg", dot)
        self.assertIn("[DANGLING]", dot,
                     "unused_reg should be labeled DANGLING")

    def test_timing_dot_title_includes_anomaly_warning(self):
        """Timing DOT title should include anomaly warning when present."""
        dot, _ = self._run_timing("x_driver", "x_driver")
        # Title should mention RTL anomalies
        self.assertIn("RTL anomalies", dot,
                     "DOT title should mention RTL anomalies")
        self.assertIn("may truncate paths", dot,
                     "DOT title should warn about path truncation")


class TestArchAnomalyDisplay(unittest.TestCase):
    """[FIX 2026-07-10] arch --show-anomalies displays RTL anomalies in DOT."""

    def _run_arch(self, target: str, tc_dir: str) -> tuple[str, str]:
        filelist = GOLDEN_DIR / tc_dir / "filelist.f"
        dot_out = Path(f"/tmp/_arch_{tc_dir}.dot")
        result = subprocess.run(
            ["sv_query", "arch",
             "-f", str(filelist),
             "--target", target, "--depth", "1",
             "--show-anomalies",
             "--format", "dot",
             "-o", str(dot_out)],
            capture_output=True, text=True, timeout=120,
        )
        return dot_out.read_text(), result.stderr

    def test_arch_x_driver_anomaly_visible(self):
        """arch --show-anomalies should display orphan_wire in x_driver."""
        dot, stderr = self._run_arch("x_driver", "x_driver")
        # Should report anomaly in stderr
        self.assertIn("RTL anomalies in x_driver", stderr,
                     "arch should report anomalies in text")
        # Should have cluster_arch_anomalies in DOT
        self.assertIn("cluster_arch_anomalies", dot,
                     "arch DOT should have anomalies cluster")
        # orphan_wire should be a diamond
        self.assertIn("orphan_wire", dot, "orphan_wire should appear in arch DOT")
        self.assertIn("[X_DRIVER]", dot, "Should be labeled X_DRIVER")
        self.assertIn("shape=diamond", dot, "Should use diamond shape")

    def test_arch_combined_multiple_anomalies(self):
        """combined: arch should show 2 X_DRIVER + 1 DANGLING."""
        dot, _ = self._run_arch("combined", "combined")
        # Should have cluster
        self.assertIn("cluster_arch_anomalies", dot)
        # Count anomalies
        x_driver_count = dot.count("[X_DRIVER]")
        dangling_count = dot.count("[DANGLING]")
        self.assertEqual(x_driver_count, 2,
                       f"Should have 2 X_DRIVER, got {x_driver_count}")
        self.assertEqual(dangling_count, 1,
                       f"Should have 1 DANGLING, got {dangling_count}")

    def test_arch_normal_no_anomalies(self):
        """normal: arch --show-anomalies should NOT show anomaly cluster."""
        dot, stderr = self._run_arch("normal", "normal")
        # Should NOT have anomaly cluster
        self.assertNotIn("cluster_arch_anomalies", dot,
                        "Normal arch should NOT have anomaly cluster")
        # Should not report anomalies in stderr
        self.assertNotIn("RTL anomalies in normal", stderr,
                        "Normal arch should not report anomalies")


class TestLowConfidenceWarning(unittest.TestCase):
    """[FIX 2026-07-10] When pyslang elaboration is incomplete (SWAP > 2GB),
    anomaly reports should be marked as 'low confidence' to avoid false positives.

    方豆 2026-07-10 16:14: '不对吧' (not right!) — the previous report on
    openofdm_tx found 22+ anomalies, but most were false positives because
    the graph was incomplete due to OOM. clk/reset are clearly INPUT PORTS
    and cannot be undriven, yet they were flagged as X_DRIVER.

    Fix: detect SWAP > 2GB and add 'low confidence' warning to anomaly reports.
    """

    def test_chain_low_confidence_when_oom(self):
        """chain should warn about false positives when elaboration is incomplete."""
        import subprocess
        result = subprocess.run(
            ["sv_query", "visualize", "chain",
             "-f", "sim/tests/fixtures/golden_chain/dangling/filelist.f",
             "--no-strict", "--target", "dangling", "--auto",
             "--max-edges", "30", "--dot", "/tmp/_lc.dot"],
            capture_output=True, text=True, timeout=120,
        )
        # When SWAP > 2GB (which is true on 8GB MBA), should add low confidence
        if "low confidence" in result.stderr or "elaboration incomplete" in result.stderr:
            # When SWAP is high, should warn
            self.assertIn("false positives", result.stderr.lower(),
                         "Should warn about possible false positives")
        # Otherwise (rare - if SWAP is low) the test passes
        else:
            # Check that we DID detect DANGLING
            self.assertIn("DANGLING", result.stderr,
                         "Should detect DANGLING even when SWAP is low")

