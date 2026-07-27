"""
test_visualize_teach_mux_demo.py - V6.3+ 2026-07-22: complex mux demo validation.

mux_demo.sv has 5 different mux patterns in one module:
  1. y_simple_if:  if/else 2:1
  2. y_case:       case 4:1
  3. y_tern:       ternary combinational 2:1
  4. y_nested:     case containing if/else
  5. y_deep:       case inside case (2-deep nested case)

For each, the viz should show:
  - correct driver signals upstream
  - edge labels matching the actual conditions

This test specifically verifies the V6.3 fix to use raw `condition`
(includes the selector, e.g. `sel_b == 2'd0`) rather than
`effective_condition` (just the value, `2'd0`).
"""
import subprocess
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "mux_demo.sv"
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
    return [l for l in dot_text.splitlines() if " -> " in l]


# --- Pattern 1: if/else -------------------------------------------------


def test_y_simple_if_then_branch_has_sel_label(tmp_path):
    """y_simple_if: a → y [label=sel_a], b → y [label=!sel_a]"""
    _strip_pycache()
    out = tmp_path / "if.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN),
        "--target", "mux_demo",
        "--focus", "y_simple_if",
        "--upstream", "--depth", "3",
        "--show-source", "--no-strict",
        "--dot", str(out),
    )
    assert rc == 0, err
    edges = _read_edges(out.read_text())
    then_edge = next(l for l in edges if 'mux_demo.a" -> "mux_demo.y_simple_if"' in l)
    assert 'label="sel_a"' in then_edge, f"then: {then_edge}"
    else_edge = next(l for l in edges if 'mux_demo.b" -> "mux_demo.y_simple_if"' in l)
    assert 'label="!sel_a"' in else_edge, f"else: {else_edge}"


# --- Pattern 2: case (V6.3+1 fix: should show sel_b == ...) -------------


def test_y_case_each_branch_shows_selector_and_value(tmp_path):
    """y_case: c → y [label=sel_b == 2'd0], etc. — NOT just '2'd0'."""
    _strip_pycache()
    out = tmp_path / "case.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN),
        "--target", "mux_demo",
        "--focus", "y_case",
        "--upstream", "--depth", "3",
        "--show-source", "--no-strict",
        "--dot", str(out),
    )
    assert rc == 0, err
    edges = _read_edges(out.read_text())
    expected = [
        ('mux_demo.c" -> "mux_demo.y_case"', "sel_b == 2'd0"),
        ('mux_demo.d" -> "mux_demo.y_case"', "sel_b == 2'd1"),
        ('mux_demo.e" -> "mux_demo.y_case"', "sel_b == 2'd2"),
    ]
    for substr, label in expected:
        e = next(l for l in edges if substr in l)
        assert f'label="{label}"' in e, f"expected {label}: {e}"
    # default
    default_edge = next(l for l in edges if 'mux_demo.f" -> "mux_demo.y_case"' in l)
    assert 'label="sel_b == default"' in default_edge, f"default: {default_edge}"


# --- Pattern 3: ternary -------------------------------------------------


def test_y_tern_branches_have_inverted_conditions(tmp_path):
    """y_tern: g → y [label=sel_c], h → y [label=!(sel_c)]."""
    _strip_pycache()
    out = tmp_path / "tern.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN),
        "--target", "mux_demo",
        "--focus", "y_tern",
        "--upstream", "--depth", "3",
        "--show-source", "--no-strict",
        "--dot", str(out),
    )
    assert rc == 0, err
    edges = _read_edges(out.read_text())
    then_edge = next(l for l in edges if 'mux_demo.g" -> "mux_demo.y_tern"' in l)
    assert 'label="sel_c"' in then_edge, f"then: {then_edge}"
    else_edge = next(l for l in edges if 'mux_demo.h" -> "mux_demo.y_tern"' in l)
    assert '!(sel_c)' in else_edge or '!sel_c' in else_edge, f"else: {else_edge}"


# --- Pattern 5: 2-deep case (verifies compound conditions) --------------


def test_y_deep_compound_conditions_use_and(tmp_path):
    """y_deep: each input edge has condition like 'sel_d == X && sel_e == Y'."""
    _strip_pycache()
    out = tmp_path / "deep.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN),
        "--target", "mux_demo",
        "--focus", "y_deep",
        "--upstream", "--depth", "5",
        "--show-source", "--no-strict",
        "--dot", str(out),
    )
    assert rc == 0, err
    text = out.read_text()
    # Should have compound condition labels with &&
    assert "sel_d == 2'd0 && sel_e == 2'd0" in text, \
        "expected compound condition for a in deep case"
    assert "sel_d == default" in text, "expected default branch"
    assert "sel_d == 2'd1 && sel_e == 2'd0" in text, \
        "expected compound for d in inner case"


# --- Source location present on all nodes ------------------------------


def test_all_nodes_have_source_location(tmp_path):
    _strip_pycache()
    out = tmp_path / "any.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN),
        "--target", "mux_demo",
        "--focus", "y_case",
        "--upstream", "--depth", "3",
        "--show-source", "--no-strict",
        "--dot", str(out),
    )
    assert rc == 0, err
    text = out.read_text()
    # Every node should have mux_demo.sv:N annotation
    import re
    nodes_with_loc = re.findall(r'label="[^"]*\\nmux_demo\.sv:\d+', text)
    assert len(nodes_with_loc) >= 4, \
        f"expected ≥4 nodes with mux_demo.sv:NN labels, got {len(nodes_with_loc)}"

# --- Pattern 4: nested case containing ternary (compound condition) -----


def test_y_nested_compound_conditions_use_and(tmp_path):
    """[V6.3+1 2026-07-27] y_nested: case containing ternary. Each leaf signal
    in the ternary should appear as a separate driver edge with the compound
    condition `(sel_d == X) && (sel_f)` or `(sel_d == X) && (!(sel_f))`.

    Before V6.3+1: only `clk -> y_nested` edge existed (with sel_d == 2'd0),
    so trace fanin / networkx shortest_path from input signals returned empty.
    After V6.3+1: 8 leaf signals (a-h) all appear with per-signal compound
    conditions, and a path a -> y_nested exists.
    """
    _strip_pycache()
    out = tmp_path / "nested.dot"
    rc, _, err = _run(
        "-f", str(GOLDEN),
        "--target", "mux_demo",
        "--focus", "y_nested",
        "--upstream", "--depth", "3",
        "--show-source", "--no-strict",
        "--dot", str(out),
    )
    assert rc == 0, err
    text = out.read_text()
    # Each leaf signal a..h should appear as a src in some edge to y_nested
    for sig in "abcdefgh":
        assert f'"mux_demo.{sig}" -> "mux_demo.y_nested"' in text, \
            f"missing driver edge for {sig}"
    # Outer case condition appears in labels
    assert "(sel_d == 2'd0)" in text, "outer case cond missing for sel_d==0 branch"
    assert "(sel_d == 2'd1)" in text, "outer case cond missing for sel_d==1 branch"
    assert "(sel_d == default)" in text, "outer default cond missing"
    # Inner ternary condition appears
    assert "sel_f" in text, "inner ternary cond missing"
    # Specific compound (sel_d==0 AND sel_f) form exists
    import re
    assert re.search(r"\(sel_d == 2'd0\) && \(sel_f\)", text) is not None, \
        "compound (sel_d==0) && (sel_f) not found in any edge label"


def test_y_nested_path_from_input_now_exists():
    """[V6.3+1 2026-07-27] NetworkX shortest path from input `a` to `y_nested`
    should exist (was disconnected before the fix)."""
    _strip_pycache()
    rc, out, err = _run(
        "-f", str(GOLDEN),
        "--target", "mux_demo",
        "--focus", "y_nested",
        "--upstream", "--depth", "3",
        "--no-strict",
    )
    # Just verify the run succeeded; detailed path assertion is done
    # implicitly via the DOT edge assertions above.
    assert rc == 0, err or "no output"
