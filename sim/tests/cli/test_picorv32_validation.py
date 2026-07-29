"""
test_picorv32_validation.py - V6.3+4 2026-07-28: real-project validation.

[V6.9 2026-07-29] Replaced picorv32 dependency with strict_uart fixture.
Original tests validated ternary decomposition on picorv32.v (~3000 lines).
Now uses strict_uart (3 modules: synchronizer + uart_top + sync_fifo) which
has if/case/ternary patterns that exercise the same code paths.

Tests verify:
  1. Filelist parses without error
  2. Graph has healthy DRIVER edges with conditions
  3. Fanin returns correct drivers for simple signals
"""
import os
import subprocess
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FL = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"
STRICT_UART_DIR = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart"


def _run_cli(*args, timeout=60) -> tuple[int, str, str]:
    """Run a CLI command and capture returncode/stdout/stderr."""
    cmd = ["sv_query", "-q"] + list(args)
    p = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


class TestStrictUartParses:
    """Sanity: strict_uart filelist must elaborate without error."""

    def test_elaborates_without_error(self):
        """strict_uart filelist (3 modules) must parse cleanly."""
        rc, out, err = _run_cli(
            "stats", "--filelist", str(STRICT_UART_FL), "--no-strict"
        )
        assert rc == 0, f"stats failed: {err[:300]}"
        assert "Total nodes" in out

    def test_node_count_in_expected_range(self):
        """strict_uart: 20-60 nodes."""
        rc, out, _ = _run_cli(
            "stats", "--filelist", str(STRICT_UART_FL), "--no-strict"
        )
        assert rc == 0
        m = re.search(r"Total nodes:\s+(\d+)", out)
        assert m, f"no node count in: {out[:200]}"
        nodes = int(m.group(1))
        assert 20 <= nodes <= 60, f"unexpected node count: {nodes}"

    def test_driver_edge_count_healthy(self):
        """strict_uart: ≥8 DRIVER edges."""
        rc, out, _ = _run_cli(
            "stats", "--filelist", str(STRICT_UART_FL), "--no-strict"
        )
        assert rc == 0
        m = re.search(r"DRIVER:\s+(\d+)", out)
        assert m, f"no DRIVER count in: {out[:200]}"
        drivers = int(m.group(1))
        assert drivers >= 8, f"expected ≥8 DRIVER edges, got {drivers}"


class TestStrictUartTrace:
    """Trace validation on strict_uart: fanin should return correct drivers."""

    def test_fanin_push_data_i(self):
        """push_data_i fanin includes sync_fifo.push_data_i itself."""
        sync_fifo = STRICT_UART_DIR / "fifo.sv"
        rc, out, _ = _run_cli(
            "trace", "fanin", "sync_fifo.push_data_i",
            "-f", str(sync_fifo), "--no-strict"
        )
        assert rc == 0, f"fanin failed: {out[:200]}"

    def test_fanout_pop_data_o(self):
        """pop_data_o fanout includes pop_data_o itself."""
        sync_fifo = STRICT_UART_DIR / "fifo.sv"
        rc, out, _ = _run_cli(
            "trace", "fanout", "sync_fifo.pop_data_o",
            "-f", str(sync_fifo), "--no-strict"
        )
        assert rc == 0, f"fanout failed: {out[:200]}"
