"""P191.3 — dataflow bus false carries bit-node path hints."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / "docs/validation/p187_cva6_2026-11-19"


def test_c1_bus_false_but_bit_node_path_exists():
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "dataflow", "analyze",
         "p187_mmu_top.u_mmu.lsu_vaddr_i",
         "p187_mmu_top.u_mmu.canonical_addr_check",
         "--filelist", str(BUNDLE / "fl_c1_parent.f"), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr[-300:]
    result = json.loads(proc.stdout)["result"]
    assert result["is_reachable"] is False
    assert result["bit_node_paths_exist"] is True
    assert any("lsu_vaddr_i[" in row["from"] for row in result["bit_node_paths"])
