"""P193.2 — public repo privacy gate."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_privacy as tool  # noqa: E402


def test_no_private_assets_or_home_paths():
    assert tool.problems(ROOT) == []


def test_privacy_and_hygiene_gates_pass():
    assert tool.main(["--root", str(ROOT)]) == 0
    proc = subprocess.run(
        [sys.executable, "tools/check_repo_hygiene.py", "--root", str(ROOT)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
