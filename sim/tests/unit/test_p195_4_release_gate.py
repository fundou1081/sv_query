"""P195.4 — release must not publish without tests and version agreement."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _load_checker():
    path = ROOT / "tools" / "check_release_version.py"
    spec = importlib.util.spec_from_file_location("release_version_check", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_version_checker_accepts_current_tag_and_rejects_mismatch():
    checker = _load_checker()
    version, tag = checker.check_versions(ROOT, "v0.3.4")
    assert version == "0.3.4"
    assert tag == "v0.3.4"
    try:
        checker.check_versions(ROOT, "v9.9.9")
    except ValueError as exc:
        assert "version mismatch" in str(exc)
    else:
        raise AssertionError("mismatched tag must fail")


def test_release_workflow_gates_publish_with_tests():
    data = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    jobs = data["jobs"]
    assert "release-check" in jobs
    assert jobs["build"]["needs"] == "release-check"
    assert jobs["publish"]["needs"] == "build"
    gate_text = (ROOT / ".github/workflows/release.yml").read_text()
    assert "run_gates.sh" in gate_text
    assert "check_release_version.py" in gate_text
    assert "needs: release-check" in gate_text


def test_version_checker_cli_fails_mismatched_tag():
    proc = subprocess.run(
        [sys.executable, "tools/check_release_version.py", "--tag", "v9.9.9"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "version mismatch" in proc.stderr
