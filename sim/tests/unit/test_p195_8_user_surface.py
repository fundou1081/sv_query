"""P195.8 — discoverable version/quiet options and documented cache/error semantics."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _run(*args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
        env={**os.environ, **(env or {})},
    )


def test_version_and_help_expose_global_options():
    from sv_query.session import PACKAGE_VERSION
    version = _run("--version")
    assert version.returncode == 0
    assert version.stdout.strip() == PACKAGE_VERSION
    help_text = _run("--help").stdout
    assert "--version" in help_text
    assert "--quiet" in help_text


def test_quiet_suppresses_cold_build_stderr(tmp_path):
    proc = _run(
        "drivers", "Scheduler_minimal.s0_reg", "--filelist", FIXTURE,
        "--json", "--quiet", env={"SVQ_CACHE_DIR": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert json.loads(proc.stdout)["ok"] is True
    assert proc.stderr == ""


def test_user_guide_documents_cache_and_error_semantics():
    guide = (ROOT / "docs/USER_GUIDE_EN.md").read_text(encoding="utf-8")
    assert "SVQ_CACHE_DIR" in guide
    assert "SVQ_CACHE_MAX_MB" in guide
    assert "--no-cache" in guide
    assert "errors[].error_code" in guide
    assert "params.cache" in guide
