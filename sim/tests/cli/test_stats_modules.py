"""[iter_347 / PLAN P46.1] stats.modules 真实模块清单。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STRUCT = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "struct.sv"
SYNC = ROOT / "sim" / "tests" / "integration" / "dataflow_fixtures" / "sync_fifo.sv"


def _modules(fixture: Path) -> list[str]:
    r = subprocess.run(["sv_query", "stats", "-f", str(fixture), "--json"],
                       capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)["result"]["modules"]


def test_stats_modules_lists_module_types():
    assert _modules(STRUCT) == ["child", "top"]
    assert _modules(SYNC) == ["sync_fifo"]
