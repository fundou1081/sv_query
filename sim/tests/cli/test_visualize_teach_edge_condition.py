"""
test_visualize_teach_edge_condition.py - V6.3 2026-07-22: edge condition labels.

After V6.3, when teach --focus renders edges, each DRIVER edge should
carry a label that shows the guarding condition (e.g. `sel` for the if-branch,
`2'd0` for case branches, `!(sel)` for ternary else-branch).

CLOCK/ENABLE/RESET edges should NOT have condition labels (those are
always-block guards, not per-edge conditions).
"""
import subprocess
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"
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


def _strip_pycache():
    import shutil
    for p in (PROJECT_ROOT / "src").rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


def _read_edges(dot_text: str) -> list[str]:
    """Return all ` -> ` edge lines from DOT output."""
    return [l for l in dot_text.splitlines() if " -> " in l]


# --- if_demo --------------------------------------------------------------


def test_if_demo_then_branch_has_sel_condition(tmp_path):
    _strip_pycache()
    out = tmp_path / "if.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN / "if_demo.sv"),
        "--target", "if_demo",
        "--focus", "if_demo.y",
        "--upstream",
        "--depth", "2",
        "--dot", str(out),
    )
    assert rc == 0, err
    edges = _read_edges(out.read_text())
    # then branch: a -> y  should have label="sel"
    then_edge = next(l for l in edges if 'if_demo.a" -> "if_demo.y"' in l)
    assert 'label="sel"' in then_edge, f"expected sel condition on then branch: {then_edge}"
    # else branch: b -> y  should have label="!sel"
    else_edge = next(l for l in edges if 'if_demo.b" -> "if_demo.y"' in l)
    assert 'label="!sel"' in else_edge, f"expected !sel condition on else branch: {else_edge}"


def test_if_demo_clock_edge_has_no_condition_label(tmp_path):
    """CLOCK edges should not have condition labels (those are guards, not per-edge)."""
    _strip_pycache()
    out = tmp_path / "if.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN / "if_demo.sv"),
        "--target", "if_demo",
        "--focus", "if_demo.y",
        "--upstream",
        "--depth", "2",
        "--dot", str(out),
    )
    assert rc == 0, err
    edges = _read_edges(out.read_text())
    clk_edge = next(l for l in edges if 'if_demo.clk" -> "if_demo.y"' in l)
    assert 'label=' not in clk_edge, f"clock edge should have no condition label: {clk_edge}"


# --- case_demo ------------------------------------------------------------


def test_case_demo_each_branch_has_op_eq_value(tmp_path):
    """[V6.3 fix 2026-07-22] Case edges should show `op == 2'd0` not just `2'd0`."""
    _strip_pycache()
    out = tmp_path / "case.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN / "case_demo.sv"),
        "--target", "case_demo",
        "--focus", "case_demo.y",
        "--upstream",
        "--depth", "2",
        "--dot", str(out),
    )
    assert rc == 0, err
    edges = _read_edges(out.read_text())
    expected = {
        'case_demo.d0" -> "case_demo.y"': "op == 2'd0",
        'case_demo.d1" -> "case_demo.y"': "op == 2'd1",
        'case_demo.d2" -> "case_demo.y"': "op == 2'd2",
    }
    for substr, label in expected.items():
        e = next(l for l in edges if substr in l)
        assert f'label="{label}"' in e, f"expected {label} on {substr}: {e}"
    # default branch
    default_edge = next(l for l in edges if 'case_demo.d3" -> "case_demo.y"' in l)
    assert 'label="op == default"' in default_edge, f"expected op == default: {default_edge}"


# --- ternary_demo ---------------------------------------------------------


def test_ternary_demo_branches_have_inverted_conditions(tmp_path):
    _strip_pycache()
    out = tmp_path / "tern.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN / "ternary_demo.sv"),
        "--target", "ternary_demo",
        "--focus", "ternary_demo.y",
        "--upstream",
        "--depth", "2",
        "--dot", str(out),
    )
    assert rc == 0, err
    edges = _read_edges(out.read_text())
    then_edge = next(l for l in edges if 'ternary_demo.a" -> "ternary_demo.y"' in l)
    assert 'label="sel"' in then_edge, f"then branch should have sel: {then_edge}"
    else_edge = next(l for l in edges if 'ternary_demo.b" -> "ternary_demo.y"' in l)
    # ternary: condition may be `!sel` or `!(sel)` depending on extractor
    assert ('!sel' in else_edge or '!(sel)' in else_edge), \
        f"else branch should have inverted sel: {else_edge}"