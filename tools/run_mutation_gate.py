#!/usr/bin/env python3
"""P171.6.2: run the repo-only mutation corpus as a gate.

Verilator is required. Missing verilator is an explicit gate error (exit 2),
not a pass. External-corpus tasks are excluded from the gate corpus.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tools/agent/task_corpora/mutation_faults_gate.json"
RUNNER = ROOT / "tools/agent/mutation_faults.py"


def main() -> int:
    if shutil.which("verilator") is None:
        print("mutation gate: verilator not installed (gate NOT passed)", file=sys.stderr)
        return 2
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--tasks", str(TASKS), "--json"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    if not proc.stdout.strip():
        print(proc.stderr[-2000:], file=sys.stderr)
        return 2
    data = json.loads(proc.stdout)
    expected = len(json.loads(TASKS.read_text())["tasks"])
    ok = (data.get("total") == expected and data.get("failed") == 0
          and data.get("invalid") == 0 and data.get("other") == 0)
    print(json.dumps({
        "ok": ok, "expected": expected, "total": data.get("total"),
        "passed": data.get("passed"), "failed": data.get("failed"),
        "invalid": data.get("invalid"), "other": data.get("other"),
        "detection_rate": data.get("detection_rate"),
    }, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
