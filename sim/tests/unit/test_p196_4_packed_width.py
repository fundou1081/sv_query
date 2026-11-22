"""P196.4 — packed-struct scalar members use canonical width (0,0)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_packed_struct_scalar_member_is_one_bit(tmp_path):
    sv = tmp_path / "packed.sv"
    sv.write_text(
        "module top;\n"
        "  typedef struct packed { logic a; logic [1:0] b; } s_t;\n"
        "  s_t s;\n"
        "  always_comb s.a = 1'b0;\n"
        "endmodule\n")
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "graph", "nodes", "--detail",
         "--file", str(sv), "--json", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    widths = {n["id"]: n["width"] for n in json.loads(proc.stdout)["result"]["nodes"]}
    assert widths["top.s.a"] == [0, 0]
    assert widths["top.s.b"] == [1, 0]


class _Width:
    value = 1


class _FixedFalse:
    hasFixedRange = False


class _DeclaredType:
    type = _FixedFalse()
    width = _Width()


class _Decl:
    declaredType = _DeclaredType()


def test_declared_width_scalar_and_default_fallback():
    from sv_query.trace.core.semantic.exprs_drivers import ExprsDriversMixin

    mixin = ExprsDriversMixin()
    assert mixin.extract_data_width(_Decl()) == (0, 0)
    assert mixin.extract_data_width(type("Empty", (), {})) == (0, 0)
