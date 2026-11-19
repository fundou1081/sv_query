"""P191.2 — drivers/loads bus rows expose bit-select hints."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / "docs/validation/p187_cva6_2026-11-19"


def test_c2_bus_drivers_hint_points_at_bit_nodes():
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "drivers",
         "p187_mmu_top.u_mmu.lsu_dtlb_ppn_o",
         "--filelist", str(BUNDLE / "fl_c2_parent.f"), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-300:]
    row = json.loads(proc.stdout)["result"]["signals"][0]
    assert row["has_bit_select_drivers"] is True
    ids = {node["id"] for node in row["bit_nodes"]}
    assert "p187_mmu_top.u_mmu.lsu_dtlb_ppn_o[PPNWMin:12]" in ids


def test_plain_signal_keeps_default_keys():
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "drivers",
         "Scheduler_minimal.clk", "--filelist",
         str(ROOT / "sim/tests/fixtures/scheduler_minimal/filelist.f"),
         "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-300:]
    row = json.loads(proc.stdout)["result"]["signals"][0]
    assert "has_bit_select_drivers" not in row
    assert "bit_nodes" not in row
