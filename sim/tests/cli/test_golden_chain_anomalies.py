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
    anomaly_match = re.search(r"RTL anomalies detected: ({[^}]+})", result.stderr)
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
