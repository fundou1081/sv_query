"""
test_visualize_graph_source.py - V6.2.1 2026-07-20: --show-source for graph viz.

After V6.2.1, the shared --show-source flag should also work for
`visualize graph` (not just `visualize teach`). This file verifies:
  - Without --show-source: no source annotation in DOT
  - With --show-source: file:line in label + tooltip + URL attributes
"""
import subprocess
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DARKRISCV_V = PROJECT_ROOT.parent / "darkriscv" / "rtl" / "darkriscv.v"
PYTHONPATH = str(PROJECT_ROOT / "src") + ":" + str(PROJECT_ROOT / "tools")


def _run(*args, timeout=60):
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH
    cmd = ["python3", "-m", "cli.main", "visualize", "graph"] + list(args)
    p = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    return p.returncode, p.stdout, p.stderr


def _strip_pycache():
    import shutil
    for p in (PROJECT_ROOT / "src").rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


def test_graph_show_source_adds_file_line_to_label(tmp_path):
    _strip_pycache()
    out = tmp_path / "g.dot"
    rc, _, err = _run(
        "-f", str(DARKRISCV_V),
        "--no-strict",
        "--module-only",
        "--show-source",
        "--dot", str(out),
    )
    assert rc == 0, err
    text = out.read_text()
    # Expect CLK port to have source line annotation
    assert "darkriscv.v:63" in text, "expected source annotation in label"


def test_graph_show_source_adds_url_attribute(tmp_path):
    _strip_pycache()
    out = tmp_path / "g.dot"
    rc, _, err = _run(
        "-f", str(DARKRISCV_V),
        "--no-strict",
        "--module-only",
        "--show-source",
        "--dot", str(out),
    )
    assert rc == 0, err
    text = out.read_text()
    # URL is full path (tooling-friendly), line is appended as fragment
    assert "URL=" in text and "#63" in text, "expected click-to-open URL attribute"
    assert "tooltip=" in text and ":63" in text, "expected tooltip attribute"


def test_graph_without_show_source_has_no_url(tmp_path):
    _strip_pycache()
    out = tmp_path / "g.dot"
    rc, _, err = _run(
        "-f", str(DARKRISCV_V),
        "--no-strict",
        "--module-only",
        "--dot", str(out),
    )
    assert rc == 0, err
    text = out.read_text()
    # Without --show-source, no URL attribute should be emitted
    assert "URL=" not in text, "URL should not be emitted without --show-source"
    assert "tooltip=" not in text, "tooltip should not be emitted without --show-source"