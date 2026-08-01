"""
test_visualize_teach_binary_ops.py - V6.3+5 2026-07-28: binary operator
decomposition in driver extraction.

Tests that `_handle_normal_assign` and `_create_always_edges`
correctly decompose RHS expressions containing binary operators
(arithmetic, bitwise, shift, comparison) into leaf signal drivers.

Patterns:
  1. y_arith:    y = a + b;           ← simple addition
  2. y_shift:    y = a << b[4:0];     ← shift with range select
  3. y_signed:   y = $signed(a) >>> b;  ← $signed wrapping
  4. y_signed_concat: y = $signed({instr_sra ? a[31] : 1'b0, a}) >>> b[4:0];
     ← picorv32 alu_shr pattern (without generate-if)
  5. y_mixed:    y = (a + b) & mask;  ← nested binary
  6. y_pipe:     y = ((a | b) & c) | d;  ← deep nested

Why this matters:
  In picorv32.v line 1236:
      alu_shr <= $signed({instr_sra || instr_srai ? reg_op1[31] : 1'b0,
                          reg_op1}) >>> reg_op2[4:0];
  This is a typical RTL pattern: $signed wrapping a {ternary, signal}
  concatenation, then shift. Driver extraction should produce:
    reg_op1, reg_op1[31], reg_op2[4:0], instr_sra, instr_srai
  as drivers of alu_shr.

  In isolation (no generate-if), this fixture proves the decomposition
  works. The picorv32 alu_shr itself has no drivers because of a
  pyslang generate-if limitation (the always block isn't enumerated
  at the module level) — that's a separate issue.
"""
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "binary_ops.sv"
PYTHONPATH = str(PROJECT_ROOT / "src") + ":" + str(PROJECT_ROOT / "tools")


def _strip_pycache():
    import shutil
    for p in (PROJECT_ROOT / "src").rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


def _render_focus(target_signal: str, depth: int = 5) -> str:
    _strip_pycache()
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
        out_path = f.name
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH
    cmd = ["python3", "-m", "cli.main", "visualize", "teach",
           "-f", str(GOLDEN),
           "--target", "binary_ops_test",
           "--focus", target_signal,
           "--upstream",
           "--depth", str(depth),
           "--show-source", "--no-strict",
           "--dot", out_path]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       cwd=str(PROJECT_ROOT), env=env)
    assert p.returncode == 0, p.stderr
    return Path(out_path).read_text()


# --- Pattern 1: simple addition --------------------------------------


def test_y_arith_drivers():
    """y = a + b; — both a and b should be drivers."""
    text = _render_focus("y_arith")
    assert '"binary_ops_test.a"' in text
    assert '"binary_ops_test.b"' in text


# --- Pattern 2: shift with range select -----------------------------


def test_y_shift_drivers():
    """y = a << shift_amount; — both `a` and the shift amount are drivers."""
    text = _render_focus("y_shift")
    assert '"binary_ops_test.a"' in text
    assert '"binary_ops_test.shift_amount"' in text


# --- Pattern 3: $signed wrapping -------------------------------------


def test_y_signed_drivers():
    """y = $signed(a) >>> b; — $signed is a transparent type-cast."""
    text = _render_focus("y_signed")
    assert '"binary_ops_test.a"' in text
    assert '"binary_ops_test.b"' in text


# --- Pattern 4: picorv32 alu_shr pattern (without generate-if) -----


def test_y_signed_concat_drivers():
    """y = $signed({instr_sra ? a[7] : 1'b0, a}) >>> b[4:0];

    This is the picorv32 alu_shr pattern, reproduced without the
    generate-if wrapper. Driver extraction should yield:
    a, a[7], b[4:0], instr_sra as drivers.
    """
    text = _render_focus("y_signed_concat")
    assert '"binary_ops_test.a"' in text
    assert '"binary_ops_test.a[7]"' in text
    assert '"binary_ops_test.b[4:0]"' in text
    assert '"binary_ops_test.instr_sra"' in text


# --- Pattern 5: nested binary ----------------------------------------


def test_y_mixed_drivers():
    """y = (a + b) & mask; — leaf signals from both sub-expressions."""
    text = _render_focus("y_mixed")
    assert '"binary_ops_test.a"' in text
    assert '"binary_ops_test.b"' in text
    assert '"binary_ops_test.mask"' in text


# --- Pattern 6: deep nested binary -----------------------------------


def test_y_pipe_drivers():
    """y = ((a | b) & c) | d; — all 4 leaf signals as drivers."""
    text = _render_focus("y_pipe")
    for sig in ['a', 'b', 'c', 'd']:
        assert f'"binary_ops_test.{sig}"' in text, f"missing {sig}"
