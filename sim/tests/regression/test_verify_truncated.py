"""A sampled/truncated consistency result must not be top-level verified."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


class TestVerifyTruncated(unittest.TestCase):
    def test_sample_truncation_forces_verified_false(self):
        lines = ["module top(input logic [7:0] a, output logic [7:0] b);"]
        lines += [f"  logic s{i}; assign s{i} = a[{i % 8}];" for i in range(240)]
        lines += ["  assign b = s0;", "endmodule"]
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "many.sv")
            with open(src, "w") as f:
                f.write("\n".join(lines) + "\n")
            p = subprocess.run(
                [sys.executable, os.path.join(_ROOT, "run_cli.py"),
                 "verify", "consistency", "--checks", "reciprocity",
                 "--max-nodes", "10", "-f", src, "--json"],
                capture_output=True, text=True, cwd=_ROOT)
            self.assertEqual(0, p.returncode, p.stderr[-1000:])
            r = json.loads(p.stdout)['result']
            self.assertFalse(r['verified'])
            self.assertFalse(r['coverage_complete'])
            self.assertEqual(['reciprocity'], r['partial_checks'])
            self.assertTrue(r['checks'][0]['truncated'])


if __name__ == '__main__':
    unittest.main()
