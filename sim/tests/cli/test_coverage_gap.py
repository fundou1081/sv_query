#==============================================================================
# test_coverage_gap.py - `coverage gap` CLI command tests
#============================================================================
"""
TDD tests for `coverage gap` subcommand.

This command exposes the Covergroup ↔ Constraint consistency analysis
(CovergroupAnalyzer) as a CLI command, similar to `coverage suggest`.

Test coverage:
  1. Command exists and prints help
  2. Returns exit 0 for a SV file with no covergroup/constraint (empty result)
  3. Detects missing_cross gap (constraint has if/else but no cross)
  4. Detects missing_illegal_bins gap (cross defined but no illegal_bins)
  5. JSON output is valid JSON
  6. Markdown output is human-readable
"""

import unittest
import subprocess
import tempfile
import os
import json


class TestCoverageGapCLI(unittest.TestCase):
    """CLI `coverage gap` command tests"""

    def _run_svq(self, args):
        """Run svq command and return CompletedProcess"""
        # sim/tests/cli/ -> sim/tests/ -> sim/ -> project root -> src/
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
        cmd = ["python", "-m", "cli.main", "coverage", "gap"] + args
        result = subprocess.run(
            cmd,
            cwd=src_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result

    def _write_sv(self, source):
        """Write SV source to temp file, return path"""
        fd, path = tempfile.mkstemp(suffix=".sv")
        with os.fdopen(fd, "w") as f:
            f.write(source)
        return path

    # -------------------------------------------------------------------------
    # T1: Command registration
    # -------------------------------------------------------------------------
    def test_coverage_gap_help(self):
        """[Golden] `coverage gap --help` should print usage info"""
        result = subprocess.run(
            ["python", "-m", "cli.main", "coverage", "gap", "--help"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("gap", result.stdout.lower())
        # Should mention constraint or covergroup
        body = result.stdout.lower()
        self.assertTrue(
            "constraint" in body or "covergroup" in body or "coverage" in body,
            f"Help text should mention coverage concepts. Got:\n{result.stdout}",
        )

    # -------------------------------------------------------------------------
    # T2: Empty result (no constraint, no covergroup)
    # -------------------------------------------------------------------------
    def test_no_constraint_no_covergroup_returns_zero_gaps(self):
        """[Golden] plain module → 0 gaps, exit 0"""
        src = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule
'''
        path = self._write_sv(src)
        try:
            result = self._run_svq(["-f", path])
            self.assertEqual(
                result.returncode, 0,
                f"Expected exit 0 for clean design. stderr: {result.stderr}\nstdout: {result.stdout}",
            )
            # Output should indicate 0 gaps (or no gaps section)
            self.assertIn("0", result.stdout)
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # T3: Detect missing_cross gap
    # -------------------------------------------------------------------------
    def test_missing_cross_gap_detected(self):
        """[Golden] conditional constraint without cross → missing_cross gap reported

        Setup:
          - constraint has if (mode == 0) { addr < 64; } else { addr >= 64; }
          - coverpoint on addr and mode exists, but NO cross
        Expected:
          - missing_cross gap for (mode x addr)
        """
        src = '''
class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    constraint c_addr {
        if (mode == 0) {
            addr < 64;
        } else {
            addr >= 64;
        }
    }
    covergroup cg;
        coverpoint addr { bins low[] = {[0:63]}; bins high[] = {[64:255]}; }
        coverpoint mode { bins m[] = {[0:3]}; }
    endgroup
    function new(); cg = new(); endfunction
endclass

module top(input clk);
endmodule
'''
        path = self._write_sv(src)
        try:
            result = self._run_svq(["-f", path])
            # Should report the gap (either exit 0 with gap count, or exit 1)
            # Look for "missing_cross" or "missing cross" or "cross" in output
            body = result.stdout.lower()
            self.assertTrue(
                "missing_cross" in body or "missing cross" in body or "cross" in body,
                f"Expected missing_cross gap. Got stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # T4: Detect missing_illegal_bins gap
    # -------------------------------------------------------------------------
    def test_missing_illegal_bins_gap_detected(self):
        """[Golden] conditional constraint with cross but no illegal_bins → missing_illegal_bins gap

        Setup:
          - constraint has if (en) { addr == 0; } else { addr != 0; }
          - coverpoint addr and en, AND cross(en, addr), but NO illegal_bins
        Expected:
          - missing_illegal_bins gap
        """
        src = '''
class packet;
    rand bit [7:0] addr;
    rand bit en;
    constraint c_addr {
        if (en) {
            addr == 0;
        } else {
            addr != 0;
        }
    }
    covergroup cg;
        coverpoint addr { bins zero = {0}; bins nonzero = {[1:255]}; }
        coverpoint en { bins on = {1}; bins off = {0}; }
        cross en, addr;
    endgroup
    function new(); cg = new(); endfunction
endclass

module top(input clk);
endmodule
'''
        path = self._write_sv(src)
        try:
            result = self._run_svq(["-f", path])
            body = result.stdout.lower()
            self.assertTrue(
                "missing_illegal_bins" in body or "illegal" in body,
                f"Expected missing_illegal_bins gap. Got stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # T5: JSON output is valid JSON
    # -------------------------------------------------------------------------
    def test_json_output_is_valid(self):
        """[Golden] --json output is parseable JSON with 'gaps' key"""
        src = '''
class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;
    constraint c_addr {
        if (mode == 0) addr < 64;
        else addr >= 64;
    }
    covergroup cg;
        coverpoint addr { bins low[] = {[0:63]}; bins high[] = {[64:255]}; }
        coverpoint mode { bins m[] = {[0:3]}; }
    endgroup
    function new(); cg = new(); endfunction
endclass

module top;
endmodule
'''
        path = self._write_sv(src)
        try:
            result = self._run_svq(["-f", path, "--json"])
            self.assertEqual(
                result.returncode, 0,
                f"Expected exit 0. stderr: {result.stderr}\nstdout: {result.stdout}",
            )
            data = json.loads(result.stdout)
            self.assertIsInstance(data, dict)
            self.assertIn("gaps", data, f"JSON should have 'gaps' key. Got: {data}")
            self.assertIsInstance(data["gaps"], list)
        except json.JSONDecodeError as e:
            self.fail(f"Output is not valid JSON: {e}\nGot:\n{result.stdout}")
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # T6: --class filter
    # -------------------------------------------------------------------------
    def test_class_filter(self):
        """[Golden] --class <name> should filter analysis to specific class"""
        src = '''
class packet_a;
    rand bit [7:0] addr;
    rand bit en;
    constraint c { if (en) addr == 0; else addr != 0; }
    covergroup cg;
        coverpoint addr { bins a[] = {[0:255]}; }
        coverpoint en { bins b[] = {[0:1]}; }
    endgroup
    function new(); cg = new(); endfunction
endclass

class packet_b;
    rand bit [7:0] data;
endclass

module top;
endmodule
'''
        path = self._write_sv(src)
        try:
            result = self._run_svq(["-f", path, "--class", "packet_a"])
            self.assertEqual(
                result.returncode, 0,
                f"Expected exit 0. stderr: {result.stderr}",
            )
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
