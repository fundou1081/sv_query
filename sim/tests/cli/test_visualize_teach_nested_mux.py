"""
test_visualize_teach_nested_mux.py - V6.3+1 2026-07-27: nested mux patterns.

Tests 8 different deeply-nested mux patterns:
  1. y_case_in_case: case inside case
  2. y_case_with_if: case containing if/else
  3. y_if_with_case: if containing case
  4. y_nested_if:    if containing if
  5. y_tern_in_tern: ternary containing ternary (3 levels)
  6. y_tern_both_branches: ternary with ternaries on both sides
  7. y_case_in_if_in_case: case > if > case (3-level nested)
  8. y_full_zoo: case > ternary > ternary (case nested ternary nested ternary)

Each verifies that edge labels show the full compound guarding
condition after the V6.3+1 fixes to driver_extractor and the
expression visitor (which now unwraps ParenthesizedExpression).
"""
import re
import subprocess
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "nested_mux_demo.sv"
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


def _render_focus(target_signal: str, depth: int = 5) -> str:
    """Render the DOT for `target_signal --upstream --depth` and return text."""
    _strip_pycache()
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
        out_path = f.name
    rc, _, err = _run(
        "-f", str(GOLDEN),
        "--target", "nested_mux_demo",
        "--focus", target_signal,
        "--upstream",
        "--depth", str(depth),
        "--show-source", "--no-strict",
        "--dot", out_path,
    )
    assert rc == 0, err
    return Path(out_path).read_text()


# --- Pattern 1: case 套 case -------------------------------------------


def test_case_in_case():
    """y_case_in_case: case (a) { case (b) { ... } }. Each leaf edge should
    have compound condition combining outer a and inner b."""
    text = _render_focus("y_case_in_case")
    # x0 is the (a==0, b==0) path
    assert "a == 2'd0 && b == 2'd0" in text
    assert "a == 2'd0 && b == 2'd1" in text
    assert "a == 2'd0 && b == default" in text
    assert "a == 2'd1 && b == 2'd0" in text
    assert "a == 2'd1 && b == default" in text
    # default case at outer level
    assert "a == default" in text


# --- Pattern 2: case 套 if ---------------------------------------------


def test_case_with_if():
    """y_case_with_if: case (a) { if (g/h/i) ... else ... }."""
    text = _render_focus("y_case_with_if")
    assert "a == 2'd0 && g" in text
    assert "a == 2'd0 && !g" in text
    assert "a == 2'd1 && h" in text
    assert "a == 2'd1 && !h" in text
    assert "a == default && i" in text
    assert "a == default && !i" in text


# --- Pattern 3: if 套 case ---------------------------------------------


def test_if_with_case():
    """y_if_with_case: if (g) { case (a) { ... } } else { case (a) { ... } }."""
    text = _render_focus("y_if_with_case")
    assert "g && a == 2'd0" in text
    assert "g && a == 2'd1" in text
    assert "g && a == default" in text
    assert "!g && a == 2'd0" in text
    assert "!g && a == 2'd1" in text
    assert "!g && a == default" in text


# --- Pattern 4: nested if ----------------------------------------------


def test_nested_if():
    """y_nested_if: if (g) { if (h) ... else ... } else ..."""
    text = _render_focus("y_nested_if")
    assert "g && h" in text
    assert "g && !h" in text
    assert "!g" in text


# --- Pattern 5: ternary 套 ternary -------------------------------------


def test_tern_in_tern():
    """y_tern_in_tern: g ? (h ? x0 : x1) : x2 — 3-level ternary."""
    text = _render_focus("y_tern_in_tern")
    assert "g && h" in text
    assert "g && !(h)" in text
    assert "!(g)" in text


# --- Pattern 6: ternary 两边都是 ternary -----------------------------


def test_tern_both_branches():
    """y_tern_both_branches: g ? (h ? x0 : x1) : (i ? x2 : x3)."""
    text = _render_focus("y_tern_both_branches")
    assert "g && h" in text
    assert "g && !(h)" in text
    assert "!(g) && i" in text
    assert "!(g) && !(i)" in text


# --- Pattern 7: case 套 if 套 case (3-level nested) -------------------


def test_case_in_if_in_case():
    """y_case_in_if_in_case: outer case by a, then if g, then inner case by c."""
    text = _render_focus("y_case_in_if_in_case")
    assert "a == 2'd0 && g && c == 2'd0" in text
    assert "a == 2'd0 && g && c == default" in text
    assert "a == 2'd0 && !g && c == 2'd0" in text
    assert "a == 2'd0 && !g && c == default" in text
    assert "a == default" in text


# --- Pattern 8: case 套 ternary 套 ternary (the full zoo) -----------


def test_full_zoo_case_tern_tern():
    """y_full_zoo: case (a) { ternary { ternary { ... } } }. Most complex pattern.

    Before V6.3+1: only case selectors g/j/m visible.
    After V6.3+1: all 12 data signals (x0-x11) visible with compound
    conditions combining outer case + outer ternary.
    """
    text = _render_focus("y_full_zoo", depth=5)
    # Outer case selectors
    assert "a == 2'd0" in text
    assert "a == 2'd1" in text
    assert "a == default" in text
    # Inner ternary operators also appear
    assert "g" in text
    assert "j" in text
    assert "m" in text
    # All 12 data signals appear as drivers
    for i in range(12):
        assert f'"nested_mux_demo.x{i}"' in text, f"missing x{i} as driver"
    # Compound (outer && inner) conditions present
    assert "(a == 2'd0) && (g)" in text
    assert "(a == 2'd0) && (!(g))" in text
    assert "(a == 2'd1) && (j)" in text
    assert "(a == default) && (m)" in text