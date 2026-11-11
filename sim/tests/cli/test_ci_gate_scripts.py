"""P158.10: CI must run the same canonical gate, not a weaker/no-op set."""
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class TestCIGates(unittest.TestCase):
    def test_gate_scripts_exist_and_parse(self):
        for rel in ("tools/run_gates.sh", "tools/run_lint.sh"):
            p = ROOT / rel
            self.assertTrue(p.exists(), rel)
            r = subprocess.run(["bash", "-n", str(p)], capture_output=True,
                               text=True)
            self.assertEqual(0, r.returncode, f"{rel}: {r.stderr}")

    def test_workflow_uses_canonical_gate_and_real_lint(self):
        text = (ROOT / ".github/workflows/tests.yml").read_text()
        self.assertIn("bash tools/run_gates.sh", text)
        self.assertIn("bash tools/run_lint.sh", text)
        self.assertNotIn("|| echo", text)
        self.assertNotIn("--ignore=sim/tests/usage", text)
        self.assertIn('python -m pytest sim/tests/ -m "not opensource"', text)
        self.assertIn('python -m pytest sim/tests/ -m "opensource"', text)

    def test_run_lint_is_not_vacuous_when_files_change(self):
        # The script must actually invoke ruff (not print and return 0).
        text = (ROOT / "tools/run_lint.sh").read_text()
        self.assertIn("ruff check", text)
        self.assertIn("git diff --name-only", text)


if __name__ == "__main__":
    unittest.main()
