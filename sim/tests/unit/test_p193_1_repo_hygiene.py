"""P193.1 — no absolute-path symlinks in a clean checkout."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_repo_hygiene as tool  # noqa: E402


def test_no_absolute_symlinks_in_index():
    assert tool.find_absolute_symlinks(ROOT) == []


def test_removed_test_config_symlink_is_gone():
    assert not (ROOT / "sim/tests/config").exists()
    out = subprocess.run(
        ["git", "ls-files", "sim/tests/config"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out == ""


def test_hygiene_tool_passes():
    assert tool.main(["--root", str(ROOT)]) == 0
