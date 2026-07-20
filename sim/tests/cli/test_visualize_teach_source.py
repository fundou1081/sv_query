"""
test_visualize_teach_source.py - V6.2 2026-07-20: source-location annotations.

After V6.2 wired pyslang's `node.sourceRange.start` (via SourceManager) into
TraceNode.file/line, --show-source should make those visible in DOT output.

Without --show-source, the user sees clean labels. With --show-source,
each node label includes "<file>:<line>" + dot's `tooltip` and `URL`
attributes for click-to-open-in-editor behavior.
"""
import subprocess
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYTHONPATH = str(PROJECT_ROOT / "src") + ":" + str(PROJECT_ROOT / "tools")


def _run(*args, timeout=60):
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH
    cmd = ["python3", "-m", "cli.main", "visualize", "teach"] + list(args)
    p = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    return p.returncode, p.stdout, p.stderr


def _dot_path(name):
    PROJECT_ROOT.joinpath(".tmp").mkdir(exist_ok=True)
    return PROJECT_ROOT / f".tmp/test_teach_source_{name}.dot"


@pytest.fixture(autouse=True)
def ensure_tmp_dir():
    (PROJECT_ROOT / ".tmp").mkdir(exist_ok=True)


def test_show_source_makes_file_line_visible_in_label():
    """--show-source should add "<file>:<line>" suffix to each node label."""
    dot = _dot_path("show_source_label")
    rc, _, err = _run(
        "--file", str(PROJECT_ROOT / "sim/tests/fixtures/golden_mini/if_demo.sv"),
        "--no-strict",
        "--target", "if_demo",
        "--show-source",
        "--dot", str(dot),
    )
    assert rc == 0, err
    content = dot.read_text()
    # if_demo.clk is on line 2 of if_demo.sv
    assert "if_demo.sv:2" in content, f"expected file:line in DOT: {content[:500]}"


def test_show_source_adds_dot_url_attribute():
    """When source location known, DOT URL attribute should set file + line.

    This makes HTML/SVG graphviz output clickable — clicking a node opens
    the file in the editor at that line (vim/VSCode/et al. honor .dot URL).
    """
    dot = _dot_path("show_source_url")
    rc, _, err = _run(
        "--file", str(PROJECT_ROOT / "sim/tests/fixtures/golden_mini/if_demo.sv"),
        "--no-strict",
        "--target", "if_demo",
        "--show-source",
        "--dot", str(dot),
    )
    assert rc == 0, err
    content = dot.read_text()
    # URL should contain file path + # + line, e.g. URL=".../if_demo.sv#2"
    assert 'URL="' in content, f"expected URL= attr in DOT: {content[:500]}"
    assert '#2"' in content, f"expected #2 in URL: {content[:500]}"


def test_no_show_source_no_url_attribute():
    """Without --show-source, DOT should NOT have URL attribute (clean DOT)."""
    dot = _dot_path("no_show_source")
    rc, _, err = _run(
        "--file", str(PROJECT_ROOT / "sim/tests/fixtures/golden_mini/if_demo.sv"),
        "--no-strict",
        "--target", "if_demo",
        "--dot", str(dot),
    )
    assert rc == 0, err
    content = dot.read_text()
    assert 'URL="' not in content, "URL= should not appear without --show-source"


def test_focus_mode_with_show_source():
    """--focus + --show-source should highlight focus + show its source line."""
    dot = _dot_path("focus_source")
    rc, _, err = _run(
        "--file", str(PROJECT_ROOT / "sim/tests/fixtures/golden_mini/case_demo.sv"),
        "--no-strict",
        "--target", "case_demo",
        "--focus", "y",
        "--depth", "2",
        "--show-source",
        "--dot", str(dot),
    )
    assert rc == 0, err
    content = dot.read_text()
    # case_demo.y should be focus (yellow, line 2)
    assert "case_demo.sv:2" in content
    assert 'fillcolor="#ffcc00"' in content, "focus node should be yellow"
