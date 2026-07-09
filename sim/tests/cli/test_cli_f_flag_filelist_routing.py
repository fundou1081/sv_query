"""
Regression test: [Bug 2026-07-09] `sv_query X -f filelist.f` caused SIGTRAP/exit 133.

Root cause: typer maps `-f` short flag to `--file` (not `--filelist`). When user
passes `-f picorv32.f` (a filelist), typer routes the value to `file`, and pyslang
tries to parse the filelist as Verilog source, causing a C-level crash.

Fix: `_build_tracer()` in src/cli/_common.py auto-detects .f/.fl/.filelist 
extension in the `file` param and promotes it to filelist path.
"""
import unittest
import subprocess

PICORV32_F = "/Users/fundou/my_dv_proj/sv_query/sim/tests/pyslang_type_fixtures/industrial_filelists/picorv32.f"


class TestFFlagFilelistAutoDetect(unittest.TestCase):
    """`-f X.f` should auto-route to filelist path (not crash)."""

    def test_f_with_filelist_extension_routes_to_filelist_path(self):
        """[Bug fix] `sv_query stats -f picorv32.f` should NOT crash.

        Before fix: exit 133 (SIGTRAP), 0 byte output.
        After fix: exit 0, normal stats output.
        """
        result = subprocess.run(
            ["sv_query", "stats", "-f", PICORV32_F, "--no-strict"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Should NOT crash with exit 133 (SIGTRAP). "
            f"actual exit: {result.returncode}\n"
            f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
        )
        self.assertIn("Total nodes:", result.stdout,
                      "Should produce normal stats output")

    def test_filelist_explicit_still_works(self):
        """[Regression] `--filelist <X.f>` still works after auto-detect fix."""
        result = subprocess.run(
            ["sv_query", "stats", "--filelist", PICORV32_F, "--no-strict"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Total nodes:", result.stdout)

    def test_f_with_v_file_still_works(self):
        """[Regression] `-f <X.v>` still works (single-file path unchanged)."""
        result = subprocess.run(
            ["sv_query", "stats", "-f",
             "/Users/fundou/my_dv_proj/picorv32/picorv32.v", "--no-strict"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Total nodes:", result.stdout)

    def test_f_with_fl_extension_works(self):
        """[Bug fix] `.fl` extension also auto-detected as filelist."""
        # Create a temp .fl file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".fl", delete=False, mode="w") as f:
            f.write("/Users/fundou/my_dv_proj/picorv32/picorv32.v\n")
            fl_path = f.name
        try:
            result = subprocess.run(
                ["sv_query", "stats", "-f", fl_path, "--no-strict"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0,
                             f"exit: {result.returncode}, stderr: {result.stderr[:300]}")
            self.assertIn("Total nodes:", result.stdout)
        finally:
            import os
            os.unlink(fl_path)

    def test_f_with_filelist_extension_works(self):
        """[Bug fix] `.filelist` extension also auto-detected."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".filelist", delete=False, mode="w") as f:
            f.write("/Users/fundou/my_dv_proj/picorv32/picorv32.v\n")
            fl_path = f.name
        try:
            result = subprocess.run(
                ["sv_query", "stats", "-f", fl_path, "--no-strict"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0,
                             f"exit: {result.returncode}, stderr: {result.stderr[:300]}")
            self.assertIn("Total nodes:", result.stdout)
        finally:
            import os
            os.unlink(fl_path)


if __name__ == "__main__":
    unittest.main()
