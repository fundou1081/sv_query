#==============================================================================
# test_diff.py - diff command tests
#============================================================================

import unittest
import subprocess
import tempfile
import os
import json


class TestDiffCLI(unittest.TestCase):
    """CLI diff command tests"""

    def _run_svq(self, args):
        """Run svq command and return output"""
        # From sim/tests/cli/test_diff.py:
        # sim/tests/cli/ -> sim/tests/ -> sim/ -> project root -> src/
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
        cmd = ["python", "-m", "cli.main"] + args
        result = subprocess.run(
            cmd,
            cwd=src_dir,
            capture_output=True,
            text=True,
        )
        return result

    def _write_sv(self, source):
        """Write SV source to temp file"""
        fd, path = tempfile.mkstemp(suffix=".sv")
        with os.fdopen(fd, "w") as f:
            f.write(source)
        return path

    def test_diff_added_node(self):
        """[Golden] diff detects added nodes"""
        old = self._write_sv('''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule
''')
        new = self._write_sv('''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
''')
        try:
            result = self._run_svq(["diff", "compare", old, new])
            self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")
            self.assertIn("top.b", result.stdout)
            self.assertIn("Added", result.stdout)
        finally:
            os.unlink(old)
            os.unlink(new)

    def test_diff_removed_node(self):
        """[Golden] diff detects removed nodes"""
        old = self._write_sv('''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
''')
        new = self._write_sv('''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule
''')
        try:
            result = self._run_svq(["diff", "compare", old, new])
            self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")
            self.assertIn("top.b", result.stdout)
            self.assertIn("Removed", result.stdout)
        finally:
            os.unlink(old)
            os.unlink(new)

    def test_diff_identical(self):
        """[Golden] diff detects identical graphs"""
        source = self._write_sv('''
module top(input clk);
    logic a;
    always_ff @(posedge clk) a <= 1'b0;
endmodule
''')
        try:
            result = self._run_svq(["diff", "compare", source, source])
            self.assertEqual(result.returncode, 0)
            self.assertIn("identical", result.stdout.lower())
        finally:
            os.unlink(source)

    def test_diff_json(self):
        """[Golden] diff --json outputs valid JSON"""
        old = self._write_sv('''
module top(output logic q);
    logic a;
    assign q = a;
endmodule
''')
        new = self._write_sv('''
module top(output logic q);
    logic a, b;
    assign q = a;
    assign b = a;
endmodule
''')
        try:
            result = self._run_svq(["diff", "compare", old, new, "--json"])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("command"), "diff_compare")
            self.assertIn("graph_diff", data.get("result", {}))
        finally:
            os.unlink(old)
            os.unlink(new)


if __name__ == "__main__":
    unittest.main()