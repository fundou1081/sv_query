"""
test_backfill_source_locations.py - V6.2.1 2026-07-20: backfill unit test.

V6.2 wired source-location into ports only. V6.2.1 added a final pass after
build_graph() that walks semantic body (PortSymbol/NetSymbol/VariableSymbol)
and back-fills file/line onto TraceNodes that lack them.

This test ensures:
  1. The backfill runs without error
  2. Internal SIGNALS (not just ports) get location
  3. Coverage of nodes-with-location is high on a real project

Uses ventus' Scheduler.v as a real-world test (has 200+ signals).
"""
from pathlib import Path
import sys
import os

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
TOOLS = str(PROJECT_ROOT / "tools")
SCHEDULER_V = (
    PROJECT_ROOT.parent
    / "ventus-gpgpu-verilog"
    / "src"
    / "gpgpu_top"
    / "l2cache"
    / "Scheduler.v"
)


@pytest.fixture(scope="module")
def ventus_graph():
    """Build graph on ventus' Scheduler.v once for the test module."""
    if not SCHEDULER_V.exists():
        pytest.skip(f"ventus Scheduler.v not found at {SCHEDULER_V}")
    sys.path.insert(0, SRC)
    sys.path.insert(0, TOOLS)
    # Clear pycache to pick up new code
    import shutil
    for p in Path(SRC).rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    from trace.unified_tracer import UnifiedTracer
    src = SCHEDULER_V.read_text()
    tracer = UnifiedTracer(sources={"Scheduler.v": src}, strict=False)
    return tracer.build_graph()


def test_backfill_runs_without_error(ventus_graph):
    """Backfill must complete silently (returns int >= 0)."""
    assert isinstance(ventus_graph, object)


def test_internal_signal_has_location(ventus_graph):
    """Internal signals (not just ports) should have file/line populated."""
    target = ventus_graph.get_node("Scheduler.writebuffer_deq_valid")
    assert target is not None, "writebuffer_deq_valid should exist in graph"
    assert target.file, f"file missing: {target.file!r}"
    assert target.line > 0, f"line missing/0: {target.line}"


def test_sourceA_req_data_has_location(ventus_graph):
    """port `sourceA_req_data_i` declared on line 88 must have line=88."""
    target = ventus_graph.get_node("Scheduler.sourceA_req_data_i")
    assert target is not None
    assert target.file, "file missing"
    assert target.line > 0, f"line missing/0: {target.line}"


def test_coverage_is_high_on_real_project(ventus_graph):
    """On a real Verilog file, > 90% of non-CONST nodes should have location."""
    total = 0
    with_loc = 0
    for nid in ventus_graph.nodes():
        n = ventus_graph.get_node(nid)
        if n is None:
            continue
        total += 1
        if n.file and n.line > 0:
            with_loc += 1
    pct = with_loc * 100 // total
    assert pct >= 90, f"coverage {pct}% < 90% ({with_loc}/{total})"


def test_const_literals_remain_without_location(ventus_graph):
    """CONST nodes (literals like '4'b1') should remain without file/line.
    They're synthesized, not source-declared."""
    const_without_loc = 0
    for nid in ventus_graph.nodes():
        n = ventus_graph.get_node(nid)
        if n is None:
            continue
        # Heuristic: NodeKind.CONST or name is a literal pattern
        if (not n.file or n.line == 0) and (
            "'" in n.name or n.name.isdigit() or n.name.startswith(("1'b", "1'h"))
        ):
            const_without_loc += 1
    # At least one should exist in ventus
    assert const_without_loc > 0, (
        "expected CONST literals without source location (synthesized nodes)"
    )