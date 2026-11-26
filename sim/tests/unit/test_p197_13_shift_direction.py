"""P197.13 — shift bit mapping across ascending/descending declarations."""
from __future__ import annotations

from pathlib import Path

import pytest


def _tracer(tmp_path: Path, a_range: str, y_range: str, rhs: str):
    from sv_query.trace.unified_tracer import UnifiedTracer

    sv = tmp_path / "shift_dir.sv"
    sv.write_text(
        f"module top(input logic {a_range} a, output logic {y_range} y);\n"
        f"  assign y = {rhs};\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    return tracer, tracer._signal_tracer


def _edge(tracer):
    graph = tracer.get_graph()
    return next(e for s in graph.predecessors("top.y")
                for e in graph.get_edges(s, "top.y") if s == "top.a")


@pytest.mark.parametrize("rhs,expected", [
    ("a << 2", {"top.y[7]": ["top.a[7]"], "top.y[9]": []}),
    ("a >> 2", {"top.y[7]": ["top.a[3]"], "top.y[9]": ["top.a[5]"]}),
    ("a <<< 2", {"top.y[7]": ["top.a[7]"], "top.y[9]": []}),
    ("a >>> 2", {"top.y[7]": ["top.a[3]"], "top.y[9]": ["top.a[5]"]}),
    ("$signed(a) >>> 2", {"top.y[7]": ["top.a[3]"], "top.y[9]": ["top.a[5]"]}),
])
def test_ascending_source_and_destination(tmp_path, rhs, expected):
    tracer, st = _tracer(tmp_path, "[0:7]", "[0:9]", rhs)
    edge = _edge(tracer)
    for out_bit, bits in expected.items():
        assert st._expr_source_bits(edge, "top.y", int(out_bit[6:-1])) == bits


def test_ascending_fanout_uses_lsb_offsets(tmp_path):
    tracer, st = _tracer(tmp_path, "[0:7]", "[0:9]", "a << 2")
    edge = _edge(tracer)
    assert st._expr_dst_bits(edge, 7) == ["top.y[7]"]
    assert st._expr_dst_bits(edge, 5) == ["top.y[5]"]


def test_mixed_declaration_directions(tmp_path):
    tracer, st = _tracer(tmp_path, "[0:7]", "[9:0]", "a << 2")
    edge = _edge(tracer)
    assert st._expr_source_bits(edge, "top.y", 2) == ["top.a[7]"]
    assert st._expr_source_bits(edge, "top.y", 4) == ["top.a[5]"]
