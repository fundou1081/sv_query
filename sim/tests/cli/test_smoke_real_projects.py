"""[iter_317 / PLAN P21] 真实工程 smoke 工具（仓库内 strict_uart；外部工程可选）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOOL = PROJECT_ROOT / "tools" / "smoke_real_projects.py"


def test_smoke_strict_uart():
    r = subprocess.run(
        [sys.executable, str(TOOL), "--project", "uart", "--json"],
        capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-500:]
    d = json.loads(r.stdout)
    assert d["ok"] is True
    uart = d["projects"]["uart"]
    assert uart["status"] == "ok"
    assert uart["dynamic_nodes"] > 0
    assert uart["nodes"] >= 20
    assert all(not c["failures"] for c in uart["checks"])
    # 动态 memory 读：bus / bit / fanout 都应 unknown + dynamic
    assert all(c["precision"] == "unknown" and c["dynamic_index"] is True
               for c in uart["checks"])
