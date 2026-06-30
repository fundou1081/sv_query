#==============================================================================
# test_trace.py - trace command tests
#============================================================================

import unittest
import subprocess
import tempfile
import os


class TestTraceCLI(unittest.TestCase):
    """CLI trace command tests"""

    def _run_svq(self, args):
        """Run svq command and return output"""
        # From sim/tests/cli/test_trace.py:
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

    def test_fanin_basic(self):
        """[Golden] trace fanin returns drivers"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanin", "top.a", "--file", path])
            self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")
            self.assertIn("top.q", result.stdout)
            self.assertIn("Fanin", result.stdout)
        finally:
            os.unlink(path)

    def test_fanout_basic(self):
        """[Golden] trace fanout returns loads"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanout", "top.q", "--file", path])
            self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")
            self.assertIn("top.a", result.stdout)
            self.assertIn("Fanout", result.stdout)
        finally:
            os.unlink(path)

    def test_fanin_json(self):
        """[Golden] trace fanin --json outputs valid JSON"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanin", "top.a", "--file", path, "--json"])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            import json
            data = json.loads(result.stdout)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("command"), "trace_fanin")
            self.assertIn("drivers", data.get("result", {}))
        finally:
            os.unlink(path)

    def test_fanout_json(self):
        """[Golden] trace fanout --json outputs valid JSON"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanout", "top.q", "--file", path, "--json"])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            import json
            data = json.loads(result.stdout)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("command"), "trace_fanout")
            self.assertIn("loads", data.get("result", {}))
        finally:
            os.unlink(path)

    def test_fanin_not_found(self):
        """[Golden] trace fanin for non-existent signal returns empty"""
        source = '''
module top(input clk);
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanin", "top.nonexistent", "--file", path])
            self.assertEqual(result.returncode, 0)
            self.assertIn("(no drivers)", result.stdout)
        finally:
            os.unlink(path)

    def test_trace_help(self):
        """[Golden] trace --help shows subcommands"""
        result = self._run_svq(["trace", "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("fanin", result.stdout)
        self.assertIn("fanout", result.stdout)


if __name__ == "__main__":
    unittest.main()
