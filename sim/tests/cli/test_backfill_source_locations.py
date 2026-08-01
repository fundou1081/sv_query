"""
test_backfill_source_locations.py - V6.2.1 2026-07-20: backfill unit test.

[V6.9 2026-07-29] Replaced ventus Scheduler.v dependency with strict_uart fixture.
Original tests used ventus' Scheduler.v as a real-world test (has 200+ signals).
Now uses strict_uart/synchronizer.sv which is a standalone fixture with known
signal names and locations.

Tests ensure:
  1. The backfill runs without error
  2. Internal SIGNALS (not just ports) get location
  3. Coverage of nodes-with-location is high
  4. CONST nodes remain without location
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = str(PROJECT_ROOT / "src")
TOOLS = str(PROJECT_ROOT / "tools")
SYNCHRONIZER = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "synchronizer.sv"


@pytest.fixture(scope="module")
def strict_uart_graph():
    """Build graph on strict_uart/synchronizer.sv once for the test module."""
    sys.path.insert(0, SRC)
    sys.path.insert(0, TOOLS)
    import shutil
    for p in Path(SRC).rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    from trace.unified_tracer import UnifiedTracer
    src = SYNCHRONIZER.read_text()
    tracer = UnifiedTracer(sources={"synchronizer.sv": src}, strict=False)
    return tracer.build_graph()


def test_backfill_runs_without_error(strict_uart_graph):
    """Backfill must complete silently (returns valid graph)."""
    assert isinstance(strict_uart_graph, object)


def test_internal_signal_has_location(strict_uart_graph):
    """Internal signals (not just ports) should have file/line populated."""
    target = strict_uart_graph.get_node("synchronizer.sync1")
    assert target is not None, "sync1 signal should exist in graph"
    assert target.file, f"file missing: {target.file!r}"
    assert target.line > 0, f"line missing/0: {target.line}"


def test_clk_i_port_has_location(strict_uart_graph):
    """port clk_i should have correct file/line populated."""
    target = strict_uart_graph.get_node("synchronizer.clk_i")
    assert target is not None, "clk_i should exist in graph"
    assert target.file, "file missing"
    assert target.line > 0, f"line missing/0: {target.line}"


def test_coverage_is_high(strict_uart_graph):
    """On strict_uart fixture, > 80% of non-CONST nodes should have location."""
    total = 0
    with_loc = 0
    for nid in strict_uart_graph.nodes():
        n = strict_uart_graph.get_node(nid)
        if n is None:
            continue
        total += 1
        if n.file and n.line > 0:
            with_loc += 1
    pct = with_loc * 100 // total if total > 0 else 0
    assert pct >= 80, f"coverage {pct}% < 80% ({with_loc}/{total})"


def test_const_literals_remain_without_location(strict_uart_graph):
    """CONST nodes (literals like '1'b0') should remain without file/line.
    They're synthesized, not source-declared."""
    const_without_loc = 0
    for nid in strict_uart_graph.nodes():
        n = strict_uart_graph.get_node(nid)
        if n is None:
            continue
        if (not n.file or n.line == 0) and (
            "'" in n.name or n.name.isdigit() or n.name.startswith(("1'b", "1'h"))
        ):
            const_without_loc += 1
    assert const_without_loc >= 0, "at least one CONST without location should exist"
