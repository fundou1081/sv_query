"""
Discipline test: [User constraint 2026-07-09] 不能用 SWAP 来规避 OOM.

The toolchain must not depend on the 4GB-bytearray SWAP-reclaim trick to work
around pyslang's silent OOM failures. Real fixes are:
  1. Smaller filelists (per-module analysis)
  2. Stream processing
  3. Proper OOM error reporting

This test enforces the constraint at the source level.
"""
import os
import subprocess
import unittest


REPO = "/Users/fundou/my_dv_proj/sv_query"


class TestNoSwapReclaimDiscipline(unittest.TestCase):
    """Toolchain must not depend on SWAP tricks to handle memory pressure."""

    def test_conftest_does_not_run_swap_reclaim_subprocess(self):
        """[User 2026-07-09] conftest.py must not invoke the 4GB reclaim trick.
        
        The trick:  python3 -c "import time; a=bytearray(4*1024**3); time.sleep(3); del a"
        pushes inactive pages to SWAP by allocating 4GB, then frees. This is a hack
        that hides pyslang's silent OOM bugs. Real tools should use:
        1. Smaller filelists (per-module analysis)
        2. Stream processing
        3. Explicit OOM errors
        """
        conftest_paths = [
            f"{REPO}/conftest.py",
            f"{REPO}/sim/conftest.py",
            f"{REPO}/sim/tests/conftest.py",
            f"{REPO}/sim/tests/cli/conftest.py",
        ]
        for path in conftest_paths:
            if os.path.exists(path):
                with open(path) as f:
                    content = f.read()
                # Check the 4GB bytearray trick is NOT being used as a reclaim call.
                # (The reclaim definition in a comment-only state is OK; an actual
                # function call that allocates 4GB and waits is NOT.)
                lines = content.splitlines()
                in_doc_or_comment = False
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    # Skip pure docstring/comment lines
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    # Detect ACTIVE 4GB bytearray allocation
                    if "bytearray(4 * 1024**3)" in line or "bytearray(4*1024**3)" in line:
                        # Check if this line is in a function body that does reclaim
                        # Look at surrounding context (5 lines before)
                        ctx = "\n".join(lines[max(0, i-5):i+2])
                        if "reclaim" in ctx.lower() or "swap" in ctx.lower():
                            self.fail(
                                f"{path}:{i+1} contains active 4GB bytearray reclaim:\n"
                                f"  {line}\n"
                                f"This is a SWAP-reclaim trick that hides pyslang OOM bugs. "
                                f"Use proper memory management (smaller filelists, etc)."
                            )

    def test_no_reclaim_memory_in_src_active_calls(self):
        """[User 2026-07-09] src/ must not actively call reclaim_memory_for_pyslang."""
        result = subprocess.run(
            ["grep", "-rn", "reclaim_memory_for_pyslang\\|reclaim_memory_if_needed",
             f"{REPO}/src/", "--include=*.py"],
            capture_output=True, text=True,
        )
        bad_calls = []
        for line in result.stdout.splitlines():
            # Filter:
            # - Definition line (`def reclaim_memory...`)
            # - Backward-compat alias (`_reclaim_memory_for_pyslang = ...`)
            # - Comments (lines starting with #)
            # - Docstring (lines with -> or "→" or "保留")
            if "def " in line:
                continue
            if "_reclaim_memory_for_pyslang = " in line:
                continue  # backward compat alias
            if line.lstrip().startswith("#"):
                continue
            # docstring markers
            if "→" in line or "保留" in line or "保留供" in line or "[C-Flaky" in line:
                continue
            bad_calls.append(line)
        self.assertEqual(
            bad_calls, [],
            "src/ must not actively invoke reclaim_memory_for_pyslang "
            "(SWAP trick). Found:\n" + "\n".join(bad_calls)
        )

    def test_compiler_memory_pressure_warning_does_not_recommend_4gb_trick(self):
        """[User 2026-07-09] SWAP warning message should not recommend the 4GB bytearray trick.

        The user explicitly said don't use SWAP to fix OOM. The recommendation
        to run 'python3 -c "import time; a=bytearray(4*1024**3)..."' is a SWAP trick
        and should be removed from the warning.
        """
        compiler_py = f"{REPO}/src/trace/core/compiler.py"
        if not os.path.exists(compiler_py):
            self.skipTest("compiler.py not found")
        with open(compiler_py) as f:
            content = f.read()
        self.assertNotIn(
            "bytearray(4*1024**3)", content,
            "compiler.py's memory pressure warning recommends the 4GB bytearray trick. "
            "Replace with: close other apps, run on a larger machine, or analyze "
            "the project in smaller chunks (one module at a time)."
        )

    def test_basic_cli_works_without_swap_trick(self):
        """[Smoke] The CLI should work on a small filelist without using SWAP.
        
        If this requires 4GB reclaim to succeed, that's a bug.
        """
        result = subprocess.run(
            ["sv_query", "stats", "-f",
             f"{REPO}/sim/tests/pyslang_type_fixtures/industrial_filelists/picorv32.f",
             "--no-strict"],
            capture_output=True, text=True,
        )
        # Filelist path with .f extension should auto-route to filelist
        # (per the cce4941 fix). Should NOT crash with SIGTRAP.
        self.assertEqual(
            result.returncode, 0,
            f"CLI failed (ec={result.returncode}). SWAP trick dependency?\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )
        self.assertIn("Total nodes:", result.stdout)


if __name__ == "__main__":
    unittest.main()
