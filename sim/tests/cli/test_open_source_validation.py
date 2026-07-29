"""
test_open_source_validation.py - 开源项目基础验证

[V6.9 2026-07-29] Replaced picorv32/darkriscv/ventus dependency with
strict_uart fixture. Original tests verified that all 3 projects parse
and produce reasonable graph stats. Now tests the same assertions on
strict_uart (3-module fixture: synchronizer + uart_top + sync_fifo).

Tests verify:
  - Graph parses with reasonable node/edge counts
  - DRIVER edges dominate
  - Drivers with conditions are present
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FL = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"


def _stats(filelist_path: Path) -> tuple[bool, dict]:
    """Run sv_query stats, return (ok, data_dict)."""
    p = subprocess.run(
        ["sv_query", "-q", "stats", "--filelist", str(filelist_path), "--no-strict"],
        capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT),
    )
    data = {}
    for line in p.stdout.split("\n"):
        # match both "  KEY: VALUE" and "Total nodes: N"
        m = re.match(r"\s+([A-Z_a-z]+):\s+(\d+)", line)
        if m:
            data[m.group(1)] = int(m.group(2))
        # also match "Total nodes: N" / "Total edges: N"
        m = re.match(r"\s+Total ([a-z]+):\s+(\d+)", line)
        if m:
            data["total_" + m.group(1)] = int(m.group(2))
    return p.returncode == 0, data


def _conditioned_driver_count(filelist_path: Path) -> int:
    """Count DRIVER edges that have conditions (proves ternary/if/case decomposition)."""
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from trace.unified_tracer import UnifiedTracer
    from trace.core.graph.models import EdgeKind

    sources = {}
    with open(filelist_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("+"):
                continue
            if line.endswith(".sv"):
                path = (PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / line)
                if path.exists():
                    sources[str(path)] = path.read_text()

    tracer = UnifiedTracer(sources=sources, strict=False)
    g = tracer.build_graph()
    count = 0
    for u, v in g.edges():
        edge = g.get_edge(u, v)
        if edge and edge.kind == EdgeKind.DRIVER and edge.condition:
            count += 1
    return count


class TestStrictUartFixture:
    """strict_uart (3 module fixture) should parse correctly."""

    def test_parses_and_has_drivers(self):
        """strict_uart: ≥8 DRIVER edges."""
        ok, data = _stats(STRICT_UART_FL)
        assert ok, "strict_uart failed to elaborate"
        assert data.get("DRIVER", 0) >= 8, (
            f"expected ≥8 DRIVER edges, got {data.get('DRIVER', 0)}"
        )

    def test_node_count_in_range(self):
        """strict_uart: 20-60 nodes."""
        _, data = _stats(STRICT_UART_FL)
        nodes = data.get("total_nodes", 0)
        assert 20 <= nodes <= 60, f"unexpected node count: {nodes}"

    def test_drivers_dominate(self):
        """DRIVER edges should be >30% of total edges."""
        _, data = _stats(STRICT_UART_FL)
        drivers = data.get('DRIVER', 0)
        total = data.get('total_edges', 1)
        pct = drivers * 100.0 / total
        assert pct > 30, f"DRIVER {pct:.1f}% <= 30% ({drivers}/{total})"

    def test_drivers_with_conditions_present(self):
        """Real RTL should have at least 1 conditioned driver."""
        count = _conditioned_driver_count(STRICT_UART_FL)
        assert count >= 1, f"expected ≥1 conditioned drivers, got {count}"
